"use strict";

const test = require("node:test");
const assert = require("node:assert");
const { lib } = require("./helpers");
const errors = lib("errors");
const i18nLib = lib("i18n");

const i18n = i18nLib.createI18n({
  en: {
    "core.error.no_gpu": "No NVIDIA GPU found ({name})",
    "adobe.error.core_unknown": "Something went wrong: {detail}",
    "adobe.error.no_selection": "Nothing selected",
    "adobe.error.host": "Host error: {detail}",
    "adobe.error.python_missing": "No python at {path}",
    "adobe.error.spawn": "Spawn failed: {detail}"
  },
  "es-419": {
    "core.error.no_gpu": "No se encontró una GPU NVIDIA ({name})",
    "adobe.error.no_selection": "Nada seleccionado"
  }
}, "es-419");

test("core error events are translated with their params", () => {
  const err = errors.fromCoreEvent({ event: "error", message_key: "core.error.no_gpu", params: { name: "x" }, detail: "raw" });
  assert.strictEqual(errors.describe(err, i18n), "No se encontró una GPU NVIDIA (x)");
  assert.strictEqual(err.detail, "raw");
});

test("unknown core keys fall back to a generic message with the detail", () => {
  const err = errors.fromCoreEvent({ event: "error", message_key: "core.error.brand_new", detail: "disk full" });
  assert.strictEqual(errors.describe(err, i18n), "Something went wrong: disk full");
  const bare = errors.fromCoreEvent({ event: "error" });
  assert.strictEqual(errors.describe(bare, i18n), "Something went wrong: ");
});

test("host responses map to panel errors", () => {
  assert.strictEqual(errors.describe(errors.fromHost({ ok: false, error: "no_selection" }), i18n), "Nada seleccionado");
  assert.strictEqual(errors.describe(errors.fromHost({ ok: false, error: "host", detail: "line 3" }), i18n), "Host error: line 3");
  assert.strictEqual(errors.fromHost({ ok: false, error: "toString" }).message_key, "adobe.error.host");
  for (const code of Object.keys(errors.HOST_ERRORS)) {
    assert.match(errors.fromHost({ ok: false, error: code }).message_key, /^adobe\.error\./);
  }
});

test("spawn failures name the interpreter", () => {
  const missing = errors.fromSpawnError(Object.assign(new Error("spawn x ENOENT"), { code: "ENOENT" }), "C:\\py.exe");
  assert.strictEqual(errors.describe(missing, i18n), "No python at C:\\py.exe");
  const other = errors.fromSpawnError(new Error("boom"));
  assert.strictEqual(errors.describe(other, i18n), "Spawn failed: boom");
});

test("plain exceptions still produce a message", () => {
  assert.strictEqual(errors.describe(new Error("weird"), i18n), "Something went wrong: weird");
  assert.strictEqual(errors.describe("text", i18n), "Something went wrong: text");
});
