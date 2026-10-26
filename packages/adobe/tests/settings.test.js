"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const { lib, tmpDir } = require("./helpers");
const settings = lib("settings");

test("settings path on Windows uses APPDATA", () => {
  assert.strictEqual(
    settings.settingsPath({ APPDATA: "C:\\Users\\Ana\\AppData\\Roaming" }, "win32", "C:\\Users\\Ana"),
    "C:\\Users\\Ana\\AppData\\Roaming\\Keymaster\\settings.json");
});

test("settings path on Windows without APPDATA falls back to the profile", () => {
  assert.strictEqual(settings.settingsPath({}, "win32", "C:\\Users\\Ana"),
    "C:\\Users\\Ana\\AppData\\Roaming\\Keymaster\\settings.json");
});

test("settings path on Linux honours XDG_CONFIG_HOME and defaults to ~/.config", () => {
  assert.strictEqual(settings.settingsPath({ XDG_CONFIG_HOME: "/x/cfg" }, "linux", "/home/a"), "/x/cfg/keymaster/settings.json");
  assert.strictEqual(settings.settingsPath({}, "linux", "/home/a"), "/home/a/.config/keymaster/settings.json");
});

test("KEYMASTER_SETTINGS overrides the location", () => {
  assert.strictEqual(settings.settingsPath({ KEYMASTER_SETTINGS: "D:\\s.json", APPDATA: "C:\\A" }, "win32", "C:\\U"), "D:\\s.json");
});

test("environment overrides the file, in order", () => {
  const file = { python: "C:\\core\\.venv\\Scripts\\python.exe", core: "C:\\core", language: "es-419" };
  assert.deepStrictEqual(settings.resolveSettings({}, file, "win32"), { python: file.python, core: file.core, language: "es-419" });
  const env = { KEYMASTER_PYTHON: "D:\\py.exe", KEYMASTER_CORE: "D:\\core", KEYMASTER_LANGUAGE: "en" };
  assert.deepStrictEqual(settings.resolveSettings(env, file, "win32"), { python: "D:\\py.exe", core: "D:\\core", language: "en" });
});

test("unknown or missing language becomes English", () => {
  assert.strictEqual(settings.resolveSettings({}, { language: "fr" }, "linux").language, "en");
  assert.strictEqual(settings.resolveSettings({}, {}, "linux").language, "en");
  assert.strictEqual(settings.resolveSettings({}, { language: "ES-419" }, "linux").language, "es-419");
  assert.strictEqual(settings.normalizeLanguage(42), "en");
});

test("python falls back to the core venv when only core is known", () => {
  const exists = (p) => p === "C:\\core\\.venv\\Scripts\\python.exe";
  assert.strictEqual(settings.resolveSettings({}, { core: "C:\\core" }, "win32", exists).python, "C:\\core\\.venv\\Scripts\\python.exe");
  assert.strictEqual(settings.resolveSettings({}, { core: "C:\\core" }, "win32", () => false).python, "");
  assert.strictEqual(settings.venvPython("/opt/core", "linux"), "/opt/core/.venv/bin/python");
});

test("broken or missing settings files read as empty", () => {
  const dir = tmpDir("settings-");
  const bad = path.join(dir, "bad.json");
  fs.writeFileSync(bad, "{not json");
  assert.deepStrictEqual(settings.readSettings(bad), {});
  assert.deepStrictEqual(settings.readSettings(path.join(dir, "none.json")), {});
  fs.writeFileSync(bad, "[1,2]");
  assert.deepStrictEqual(settings.readSettings(bad), {});
  fs.writeFileSync(bad, "\uFEFF{\"language\":\"es-419\"}");
  assert.deepStrictEqual(settings.readSettings(bad), { language: "es-419" });
});

test("writing the language keeps the other keys and creates folders", () => {
  const dir = tmpDir("settings-");
  const file = path.join(dir, "Keymaster", "settings.json");
  assert.deepStrictEqual(settings.writeLanguage(file, "es-419"), { language: "es-419" });
  fs.writeFileSync(file, JSON.stringify({ language: "en", python: "/p", core: "/c" }));
  settings.writeLanguage(file, "es-419");
  assert.deepStrictEqual(JSON.parse(fs.readFileSync(file, "utf8")), { language: "es-419", python: "/p", core: "/c" });
  settings.writeLanguage(file, "klingon");
  assert.strictEqual(JSON.parse(fs.readFileSync(file, "utf8")).language, "en");
  assert.deepStrictEqual(fs.readdirSync(path.dirname(file)), ["settings.json"]);
});

test("load reads the file named by the environment", () => {
  const dir = tmpDir("settings-");
  const file = path.join(dir, "s.json");
  fs.writeFileSync(file, JSON.stringify({ language: "es-419", python: "/py", core: "/core" }));
  const got = settings.load({ env: { KEYMASTER_SETTINGS: file, KEYMASTER_CORE: "/other" }, platform: "linux", home: "/home/x" });
  assert.deepStrictEqual(got, { python: "/py", core: "/other", language: "es-419", file: file });
});
