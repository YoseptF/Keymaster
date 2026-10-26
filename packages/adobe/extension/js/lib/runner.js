"use strict";

var childProcess = require("child_process");
var events = require("./events");
var argsLib = require("./args");
var errors = require("./errors");

var STDERR_LIMIT = 16384;

function killTree(child, platform, spawnFn) {
  var spawn = spawnFn || childProcess.spawn;
  if (!child || !child.pid) return;
  if (platform === "win32") {
    try {
      var killer = spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
      killer.on("error", function () {
        try { child.kill(); } catch (e) {}
      });
    } catch (e) {
      try { child.kill(); } catch (e2) {}
    }
    return;
  }
  try {
    process.kill(-child.pid, "SIGTERM");
  } catch (e) {
    try { child.kill("SIGTERM"); } catch (e2) {}
  }
  var timer = setTimeout(function () {
    try { process.kill(-child.pid, "SIGKILL"); } catch (e) {}
  }, 5000);
  if (timer.unref) timer.unref();
  child.once("close", function () { clearTimeout(timer); });
}

function runCore(options) {
  var o = options || {};
  var platform = o.platform || process.platform;
  var spawn = o.spawn || childProcess.spawn;
  var onEvent = o.onEvent || function () {};
  var env = Object.assign({}, process.env, o.env || {}, { PYTHONIOENCODING: "utf-8", PYTHONUNBUFFERED: "1" });
  var spec = argsLib.spawnSpec(o.python, o.args, platform, env);
  var state = { cancelled: false, child: null, finished: false };
  var result = { status: "error", code: null, start: null, outputs: [], done: null, error: null, stderr: "", events: [] };

  var promise = new Promise(function (resolve) {
    function finish() {
      if (state.finished) return;
      state.finished = true;
      resolve(result);
    }
    if (!o.python || !o.core) {
      result.error = errors.KeymasterError({ message_key: "adobe.error.not_configured", detail: "python or core missing from settings" });
      finish();
      return;
    }
    var child;
    try {
      child = spawn(spec.command, spec.args, {
        cwd: o.core,
        env: env,
        windowsHide: true,
        windowsVerbatimArguments: spec.windowsVerbatimArguments,
        detached: platform !== "win32",
        stdio: ["ignore", "pipe", "pipe"]
      });
    } catch (err) {
      result.error = errors.fromSpawnError(err, o.python);
      finish();
      return;
    }
    state.child = child;
    var stream = new events.EventStream(function (event) {
      result.events.push(event);
      if (event.event === "start") result.start = event;
      else if (event.event === "output") result.outputs.push(event);
      else if (event.event === "done") result.done = event;
      else if (event.event === "error") result.error = errors.fromCoreEvent(event);
      try { onEvent(event); } catch (e) {}
    });
    child.stdout.on("data", function (chunk) { stream.write(chunk); });
    child.stderr.on("data", function (chunk) {
      result.stderr = (result.stderr + chunk.toString("utf8")).slice(-STDERR_LIMIT);
    });
    child.on("error", function (err) {
      result.error = errors.fromSpawnError(err, o.python);
      result.status = "error";
      finish();
    });
    child.on("close", function (code, signal) {
      stream.end();
      result.code = code;
      if (state.cancelled || code === 130) {
        result.status = "cancelled";
        result.error = null;
      } else if (code === 0 && (result.done || o.expectDone === false)) {
        result.status = "done";
      } else {
        result.status = "error";
        if (!result.error) {
          result.error = code === 0
            ? errors.KeymasterError({ message_key: "adobe.error.no_result", detail: result.stderr })
            : errors.KeymasterError({ message_key: "adobe.error.exit", params: { code: code === null ? String(signal) : code }, detail: result.stderr });
        }
      }
      finish();
    });
  });

  return {
    promise: promise,
    cancel: function () {
      if (state.finished || state.cancelled) return;
      state.cancelled = true;
      killTree(state.child, platform, o.killSpawn);
    },
    commandLine: argsLib.displayCommand([o.python].concat(o.args || []), platform)
  };
}

module.exports = { runCore: runCore, killTree: killTree };
