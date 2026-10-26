"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const { lib, FAKE_CORE, tmpDir, python } = require("./helpers");
const runner = lib("runner");
const args = lib("args");
const job = lib("job");
const paths = lib("paths");

const PLATFORM = process.platform;

function keyArgs(dir, extra) {
  return args.buildKeyArgs(Object.assign({ input: path.join(dir, "take 01.mov"), outputDir: path.join(dir, "out dir"), outputs: ["alpha", "cutout"] }, extra), PLATFORM);
}

function run(argv, env) {
  const seen = [];
  const handle = runner.runCore({ python: python(), core: FAKE_CORE, args: argv, env: env || {}, onEvent: (e) => seen.push(e) });
  return { handle, seen };
}

test("a key run streams events and writes image sequences", async () => {
  const dir = tmpDir("run-");
  const { handle, seen } = run(keyArgs(dir, { frames: 3 }));
  const result = await handle.promise;
  assert.strictEqual(result.status, "done", JSON.stringify(result.error));
  assert.strictEqual(result.code, 0);
  assert.deepStrictEqual(seen.map((e) => e.event), ["start", "progress", "progress", "progress", "progress", "progress", "output", "output", "progress", "done"]);
  assert.strictEqual(result.start.frames, 3);
  const fractions = seen.filter((e) => e.event === "progress").map((e) => e.fraction);
  for (let i = 1; i < fractions.length; i++) assert.ok(fractions[i] >= fractions[i - 1]);
  assert.deepStrictEqual(result.outputs.map((o) => o.kind), ["alpha", "cutout"]);
  for (const out of result.outputs) {
    assert.strictEqual(out.type, "image_sequence");
    const first = paths.firstFrameFile(out);
    assert.ok(fs.existsSync(first), first);
    assert.strictEqual(fs.readdirSync(out.path).length, 3);
  }
  assert.deepStrictEqual(result.done.outputs.map((o) => o.path), result.outputs.map((o) => o.path));
});

test("video format writes one file per output", async () => {
  const dir = tmpDir("run-");
  const { handle } = run(keyArgs(dir, { format: "video" }));
  const result = await handle.promise;
  assert.strictEqual(result.status, "done");
  const cutout = result.outputs.find((o) => o.kind === "cutout");
  assert.strictEqual(cutout.type, "video");
  assert.ok(cutout.path.endsWith("take 01_cutout.mov"));
  assert.ok(fs.statSync(cutout.path).isFile());
});

test("a core error ends with a translatable error and exit code 1", async () => {
  const dir = tmpDir("run-");
  const { handle } = run(keyArgs(dir), { KEYMASTER_FAKE_FAIL: "no_gpu" });
  const result = await handle.promise;
  assert.strictEqual(result.status, "error");
  assert.strictEqual(result.code, 1);
  assert.strictEqual(result.error.message_key, "core.error.no_gpu");
  assert.strictEqual(result.error.detail, "fake failure no_gpu");
});

test("cancel kills the run quickly and reports cancelled", async () => {
  const dir = tmpDir("run-");
  const { handle, seen } = run(keyArgs(dir), { KEYMASTER_FAKE_DELAY: "5" });
  while (!seen.length) await new Promise((r) => setTimeout(r, 20));
  const t0 = Date.now();
  handle.cancel();
  handle.cancel();
  const result = await handle.promise;
  assert.strictEqual(result.status, "cancelled");
  assert.strictEqual(result.error, null);
  assert.ok(Date.now() - t0 < 4000, "took " + (Date.now() - t0));
});

test("a missing interpreter is reported as such", async () => {
  const handle = runner.runCore({ python: path.join(tmpDir("nopy-"), "python.exe"), core: FAKE_CORE, args: args.buildDoctorArgs() });
  const result = await handle.promise;
  assert.strictEqual(result.status, "error");
  assert.strictEqual(result.error.message_key, "adobe.error.python_missing");
});

test("an unconfigured core is reported before spawning", async () => {
  const result = await runner.runCore({ python: "", core: "", args: [] }).promise;
  assert.strictEqual(result.error.message_key, "adobe.error.not_configured");
});

test("a crash without an error event is reported with stderr", async () => {
  const fake = tmpDir("crash-");
  fs.mkdirSync(path.join(fake, "keymaster"));
  fs.writeFileSync(path.join(fake, "keymaster", "__init__.py"), "");
  fs.writeFileSync(path.join(fake, "keymaster", "__main__.py"), "import sys\nprint('{\"event\": \"start\"}')\nsys.stderr.write('Traceback: boom\\n')\nsys.exit(3)\n");
  const result = await runner.runCore({ python: python(), core: fake, args: ["-m", "keymaster", "key", "--json"] }).promise;
  assert.strictEqual(result.status, "error");
  assert.strictEqual(result.error.message_key, "adobe.error.exit");
  assert.strictEqual(result.error.params.code, 3);
  assert.match(result.stderr, /Traceback: boom/);
});

test("the doctor report comes through", async () => {
  const res = await job.runDoctor({ settings: { python: python(), core: FAKE_CORE } });
  assert.strictEqual(res.status, "done");
  assert.strictEqual(res.report.ok, true);
  assert.deepStrictEqual(res.report.checks.map((c) => c.id), ["gpu", "ffmpeg", "weights", "torch"]);
});

function fakeBridge(source, calls) {
  return {
    call(name, payload) {
      calls.push({ name, payload });
      if (name === "keymaster_getSelection") return Promise.resolve({ ok: true, host: "AEFT", source });
      if (name === "keymaster_importResult") return Promise.resolve({ ok: true, imported: [], placed: { index: 1 } });
      return Promise.reject(new Error(name));
    }
  };
}

test("a full key job: selection, core run, import with first frames", async () => {
  const dir = tmpDir("job-");
  const clip = path.join(dir, "green plate.mov");
  fs.writeFileSync(clip, "x");
  const calls = [];
  const updates = [];
  const handle = job.startKeyJob({
    settings: { python: python(), core: FAKE_CORE },
    bridge: fakeBridge({ path: clip, name: "Actor", fps: 23.976, ref: { compId: 7 } }, calls),
    options: { outputs: ["cutout", "alpha"], format: "exr", despill: 0.4, disableSource: true },
    now: () => new Date(2026, 0, 2, 3, 4, 5),
    onUpdate: (u) => updates.push(u.phase + ":" + u.tracker.percent())
  });
  const result = await handle.promise;
  assert.strictEqual(result.status, "done", result.error && result.error.stack);
  assert.strictEqual(result.outputDir, path.join(dir, "Keymaster", "green plate_20260102-030405"));
  assert.deepStrictEqual(calls.map((c) => c.name), ["keymaster_getSelection", "keymaster_importResult"]);
  const imp = calls[1].payload;
  assert.deepStrictEqual(imp.ref, { compId: 7 });
  assert.strictEqual(imp.fps, 23.976);
  assert.strictEqual(imp.disableSource, true);
  assert.strictEqual(imp.folder, "Keymaster");
  assert.deepStrictEqual(imp.outputs.map((o) => o.kind), ["alpha", "cutout"]);
  for (const o of imp.outputs) assert.ok(fs.existsSync(o.firstFile), o.firstFile);
  assert.strictEqual(updates[0], "selection:0");
  assert.strictEqual(updates[updates.length - 1], "importing:100");
  const percents = updates.filter((u) => u.startsWith("keying")).map((u) => Number(u.split(":")[1]));
  for (let i = 1; i < percents.length; i++) assert.ok(percents[i] >= percents[i - 1]);
});

test("a key job on an image sequence passes the folder", async () => {
  const dir = tmpDir("jobseq-");
  const plates = path.join(dir, "plates");
  fs.mkdirSync(plates);
  for (let i = 1; i <= 3; i++) fs.writeFileSync(path.join(plates, "p." + i + ".png"), "");
  const calls = [];
  let seenArgs = null;
  const handle = job.startKeyJob({
    settings: { python: python(), core: FAKE_CORE },
    bridge: fakeBridge({ path: path.join(plates, "p.1.png"), isSequence: true, fps: 24, ref: {} }, calls),
    options: { outputs: ["cutout"], format: "video" },
    runCore: (o) => { seenArgs = o.args; return runner.runCore(o); }
  });
  const result = await handle.promise;
  assert.strictEqual(result.status, "done");
  assert.strictEqual(seenArgs[seenArgs.indexOf("--input") + 1], plates);
  assert.strictEqual(calls[1].payload.outputs[0].type, "video");
});

test("cancelling a key job removes its output folder and skips the import", async () => {
  const dir = tmpDir("jobcancel-");
  const clip = path.join(dir, "a.mov");
  fs.writeFileSync(clip, "x");
  const calls = [];
  let outputDir = null;
  const handle = job.startKeyJob({
    settings: { python: python(), core: FAKE_CORE },
    bridge: fakeBridge({ path: clip, fps: 24, ref: {} }, calls),
    options: { outputs: ["cutout"] },
    env: { KEYMASTER_FAKE_DELAY: "0.2" },
    onUpdate: (u) => { if (u.outputDir) outputDir = u.outputDir; }
  });
  const deadline = Date.now() + 10000;
  while (!(outputDir && fs.existsSync(outputDir)) && Date.now() < deadline) await new Promise((r) => setTimeout(r, 20));
  assert.ok(fs.existsSync(outputDir), "output folder never appeared");
  handle.cancel();
  const result = await handle.promise;
  assert.strictEqual(result.status, "cancelled");
  assert.ok(!fs.existsSync(result.outputDir));
  assert.deepStrictEqual(calls.map((c) => c.name), ["keymaster_getSelection"]);
});

test("job failures resolve with translatable errors", async () => {
  const dir = tmpDir("jobfail-");
  const clip = path.join(dir, "a.mov");
  fs.writeFileSync(clip, "x");
  const base = { settings: { python: python(), core: FAKE_CORE }, options: { outputs: ["cutout"] } };
  const nocfg = await job.startKeyJob(Object.assign({}, base, { settings: {}, bridge: fakeBridge({}, []) })).promise;
  assert.strictEqual(nocfg.error.message_key, "adobe.error.not_configured");
  const nocore = await job.startKeyJob(Object.assign({}, base, { settings: { python: "py", core: path.join(dir, "nope") }, bridge: fakeBridge({}, []) })).promise;
  assert.strictEqual(nocore.error.message_key, "adobe.error.core_missing");
  const missing = await job.startKeyJob(Object.assign({}, base, { bridge: fakeBridge({ path: path.join(dir, "gone.mov"), ref: {} }, []) })).promise;
  assert.strictEqual(missing.error.message_key, "adobe.error.source_missing");
  const failing = await job.startKeyJob(Object.assign({}, base, { env: { KEYMASTER_FAKE_FAIL: "out_of_memory" }, bridge: fakeBridge({ path: clip, ref: {} }, []) })).promise;
  assert.strictEqual(failing.status, "error");
  assert.strictEqual(failing.error.message_key, "core.error.out_of_memory");
  const hostErr = await job.startKeyJob(Object.assign({}, base, { bridge: { call: () => Promise.reject(Object.assign(new Error("x"), { name: "KeymasterError", message_key: "adobe.error.no_comp" })) } })).promise;
  assert.strictEqual(hostErr.error.message_key, "adobe.error.no_comp");
});
