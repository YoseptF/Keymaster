"use strict";

var fs = require("fs");
var argsLib = require("./args");
var paths = require("./paths");
var runner = require("./runner");
var errors = require("./errors");
var progress = require("./progress");

function outputSummary(output) {
  return {
    kind: output.kind,
    type: output.type,
    path: output.path,
    firstFile: paths.firstFrameFile(output),
    firstFrame: output.first_frame || 0,
    frames: output.frames || 0
  };
}

function removeDir(dir, f) {
  try {
    if (f.rmSync) f.rmSync(dir, { recursive: true, force: true });
    else f.rmdirSync(dir, { recursive: true });
  } catch (e) {}
}

function startKeyJob(ctx) {
  var platform = ctx.platform || process.platform;
  var f = ctx.fs || fs;
  var run = ctx.runCore || runner.runCore;
  var options = ctx.options || {};
  var tracker = new progress.ProgressTracker();
  var state = { cancelled: false, active: null, phase: "selection" };
  var notify = ctx.onUpdate || function () {};

  function step(phase, extra) {
    state.phase = phase;
    notify(Object.assign({ phase: phase, tracker: tracker }, extra || {}));
  }

  var promise = (async function () {
    var settings = ctx.settings || {};
    if (!settings.python || !settings.core) {
      throw errors.KeymasterError({ message_key: "adobe.error.not_configured", detail: "python or core missing from settings" });
    }
    if (!f.existsSync(settings.core)) {
      throw errors.KeymasterError({ message_key: "adobe.error.core_missing", params: { path: settings.core }, detail: settings.core });
    }
    step("selection");
    var selection = await ctx.bridge.call("keymaster_getSelection", {});
    var source = selection.source;
    if (state.cancelled) return { status: "cancelled" };
    if (!source || !source.path || !f.existsSync(source.path)) {
      throw errors.KeymasterError({ message_key: "adobe.error.source_missing", detail: source ? source.path : "" });
    }
    var resolved = paths.resolveInput(source, platform, f);
    if (resolved.mixed) {
      throw errors.KeymasterError({ message_key: "adobe.error.mixed_sequence", detail: resolved.input });
    }
    var outputDir = paths.defaultOutputDir(source.path, options.outputRoot, ctx.now ? ctx.now() : new Date(), platform);
    var existed = f.existsSync(outputDir);
    var args = argsLib.buildKeyArgs({
      input: resolved.input,
      outputDir: outputDir,
      hintFirstFrame: options.hintFirstFrame,
      hintQuality: options.hintQuality,
      despill: options.despill,
      format: options.format,
      outputs: options.outputs,
      lowVram: options.lowVram
    }, platform);
    step("keying", { source: source, outputDir: outputDir });
    var handle = run({
      python: settings.python,
      core: settings.core,
      args: args,
      platform: platform,
      env: ctx.env,
      onEvent: function (event) {
        if (event.event === "progress") {
          tracker.update(event);
          step("keying", { source: source, outputDir: outputDir });
        } else if (event.event === "start") {
          step("keying", { source: source, outputDir: outputDir, start: event });
        }
      }
    });
    state.active = handle;
    if (state.cancelled) handle.cancel();
    var result = await handle.promise;
    state.active = null;
    if (result.status === "cancelled") {
      if (!existed) removeDir(outputDir, f);
      return { status: "cancelled", outputDir: outputDir };
    }
    if (result.status !== "done") {
      result.error.stderr = result.stderr;
      throw result.error;
    }
    var outputs = (result.done.outputs && result.done.outputs.length ? result.done.outputs : result.outputs).map(outputSummary);
    step("importing", { source: source, outputDir: outputDir });
    var fps = Number(source.fps) > 0 ? Number(source.fps) : (result.start && Number(result.start.fps)) || 0;
    var imported = await ctx.bridge.call("keymaster_importResult", {
      ref: source.ref,
      outputs: outputs,
      fps: fps,
      disableSource: !!options.disableSource,
      folder: "Keymaster"
    });
    return {
      status: "done",
      source: source,
      outputDir: outputDir,
      outputs: outputs,
      seconds: Number(result.done.seconds) || 0,
      imported: imported,
      commandLine: handle.commandLine
    };
  })().catch(function (err) {
    return { status: "error", error: err };
  });

  return {
    promise: promise,
    cancel: function () {
      state.cancelled = true;
      if (state.active) state.active.cancel();
    },
    phase: function () {
      return state.phase;
    }
  };
}

function runDoctor(ctx) {
  var run = ctx.runCore || runner.runCore;
  var settings = ctx.settings || {};
  var handle = run({
    python: settings.python,
    core: settings.core,
    args: argsLib.buildDoctorArgs(),
    platform: ctx.platform || process.platform,
    env: ctx.env,
    expectDone: false
  });
  return handle.promise.then(function (result) {
    var report = null;
    for (var i = 0; i < result.events.length; i++) {
      if (result.events[i].event === "doctor") report = result.events[i];
    }
    if (report) return { status: "done", report: report, stderr: result.stderr };
    return { status: "error", error: result.error || errors.KeymasterError({ message_key: "adobe.error.no_result", detail: result.stderr }), stderr: result.stderr };
  });
}

module.exports = { startKeyJob: startKeyJob, runDoctor: runDoctor, outputSummary: outputSummary };
