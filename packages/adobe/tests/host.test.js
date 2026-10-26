"use strict";

const test = require("node:test");
const assert = require("node:assert");
const vm = require("vm");
const { lib } = require("./helpers");
const { hostContext, evalScript } = require("./jsx-harness");
const host = lib("host");

test("host detection by app name", () => {
  assert.strictEqual(host.hostId("AEFT"), "AEFT");
  assert.strictEqual(host.hostId("PPRO"), "PPRO");
  assert.strictEqual(host.hostId("PHXS"), null);
  assert.strictEqual(host.hostId("constructor"), null);
});

test("script literals survive an ES3 eval with any characters", () => {
  const samples = ['C:\\Users\\José\\"quoted"\\clip.mov', "line\nbreak\r\ttab", "\u2028\u2029", "emoji 🎬", "</script>", ""];
  for (const s of samples) {
    const lit = host.scriptLiteral(s);
    assert.match(lit, /^"[\x20-\x7e]*"$/);
    assert.strictEqual(vm.runInNewContext(lit), s);
  }
});

test("call scripts refuse odd function names", () => {
  assert.throws(() => host.callScript("a(); evil", {}));
  assert.strictEqual(host.callScript("keymaster_ping", {}), 'keymaster_call("keymaster_ping", "{}")');
});

test("responses parse, failures become translatable errors", () => {
  assert.deepStrictEqual(host.parseResponse('{"ok":true,"x":1}'), { ok: true, x: 1 });
  assert.throws(() => host.parseResponse("EvalScript error."), (e) => e.message_key === "adobe.error.host" && e.params.detail === "EvalScript error.");
  assert.throws(() => host.parseResponse('{"ok":false,"error":"no_comp"}'), (e) => e.message_key === "adobe.error.no_comp");
  assert.throws(() => host.parseResponse(undefined), (e) => e.message_key === "adobe.error.host");
  assert.throws(() => host.parseResponse("null"), (e) => e.message_key === "adobe.error.host");
});

test("round trip through the ExtendScript dispatcher", async () => {
  const ctx = hostContext({ app: { version: "26.0" } }, "common.jsx");
  vm.runInContext('keymaster_handlers.echo = function (p) { return { ok: true, got: p, list: [1, "two", null, true], nested: { s: "Ñandú \\"q\\" \\\\ \\n" } }; };', ctx);
  vm.runInContext('keymaster_handlers.boom = function () { throw new Error("kaput"); };', ctx);
  const bridge = host.createBridge(evalScript(ctx));
  const payload = { path: "C:\\Clips\\Toma «1».mov", n: 1.5, flag: false, arr: [1, [2]], none: null };
  const res = await bridge.call("echo", payload);
  assert.deepStrictEqual(res.got, payload);
  assert.deepStrictEqual(res.list, [1, "two", null, true]);
  assert.strictEqual(res.nested.s, 'Ñandú "q" \\ \n');
  await assert.rejects(bridge.call("boom", {}), (e) => e.message_key === "adobe.error.host" && /kaput/.test(e.detail));
  await assert.rejects(bridge.call("nothing_here", {}), (e) => e.message_key === "adobe.error.host" && /unknown host function/.test(e.detail));
  const ping = await bridge.call("keymaster_ping");
  assert.deepStrictEqual(ping, { ok: true, app: "test", version: "26.0" });
});

test("the dispatcher refuses payloads that are not JSON", () => {
  const ctx = hostContext({}, "common.jsx");
  vm.runInContext("keymaster_handlers.echo = function (p) { return { ok: true }; };", ctx);
  const out = JSON.parse(vm.runInContext('keymaster_call("echo", "alert(1)")', ctx));
  assert.strictEqual(out.ok, false);
  assert.match(out.detail, /invalid JSON/);
});

test("loading a host file uses forward slashes and reports success", async () => {
  assert.strictEqual(host.loadScript("C:\\ext\\jsx\\aeft.jsx"), '$.evalFile("C:/ext/jsx/aeft.jsx"); "loaded"');
  const ok = host.createBridge((script, cb) => cb("loaded"));
  await ok.load("C:\\x.jsx");
  const bad = host.createBridge((script, cb) => cb("EvalScript error."));
  await assert.rejects(bad.load("C:\\x.jsx"), (e) => e.message_key === "adobe.error.host");
});
