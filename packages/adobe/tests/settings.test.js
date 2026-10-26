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

test("language: environment, then an explicit setting, then the app's locale", () => {
  const r = (env, file, locale) => settings.resolveSettings(env, file, "win32", null, locale).language;
  assert.strictEqual(r({}, {}, "es_MX"), "es-419");
  assert.strictEqual(r({}, {}, "es_ES"), "es-419");
  assert.strictEqual(r({}, {}, "es"), "es-419");
  assert.strictEqual(r({}, {}, "en_US"), "en");
  assert.strictEqual(r({}, {}, "fr_FR"), "en");
  assert.strictEqual(r({}, {}, "est_EE"), "en");
  assert.strictEqual(r({}, {}, undefined), "en");
  assert.strictEqual(r({}, { language: "auto" }, "es_MX"), "es-419");
  assert.strictEqual(r({}, { language: "en" }, "es_MX"), "en");
  assert.strictEqual(r({}, { language: "ES-419" }, "en_US"), "es-419");
  assert.strictEqual(r({}, { language: "fr" }, "es_AR"), "es-419");
  assert.strictEqual(r({}, { language: 42 }, "en_GB"), "en");
  assert.strictEqual(r({ KEYMASTER_LANGUAGE: "en" }, { language: "es-419" }, "es_MX"), "en");
  assert.strictEqual(r({ KEYMASTER_LANGUAGE: "es-419" }, { language: "en" }, "en_US"), "es-419");
  assert.strictEqual(r({ KEYMASTER_LANGUAGE: "auto" }, { language: "es-419" }, "en_US"), "es-419");
  assert.strictEqual(r({ KEYMASTER_LANGUAGE: "auto" }, {}, "es_CO"), "es-419");
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

test("load reads the file named by the environment", () => {
  const dir = tmpDir("settings-");
  const file = path.join(dir, "s.json");
  fs.writeFileSync(file, JSON.stringify({ language: "es-419", python: "/py", core: "/core" }));
  const got = settings.load({ env: { KEYMASTER_SETTINGS: file, KEYMASTER_CORE: "/other" }, platform: "linux", home: "/home/x", hostLocale: "en_US" });
  assert.deepStrictEqual(got, { python: "/py", core: "/other", language: "es-419", file: file });
  fs.writeFileSync(file, JSON.stringify({ python: "/py", core: "/core" }));
  assert.strictEqual(settings.load({ env: { KEYMASTER_SETTINGS: file }, hostLocale: "es_MX" }).language, "es-419");
  assert.strictEqual(settings.load({ env: { KEYMASTER_SETTINGS: file } }).language, "en");
});
