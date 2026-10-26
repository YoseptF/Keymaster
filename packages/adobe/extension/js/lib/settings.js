"use strict";

var nodePath = require("path");
var fs = require("fs");

var LANGUAGES = ["en", "es-419"];

function pathApi(platform) {
  return platform === "win32" ? nodePath.win32 : nodePath.posix;
}

function normalizeLanguage(value) {
  if (typeof value !== "string") return "en";
  var v = value.trim();
  for (var i = 0; i < LANGUAGES.length; i++) {
    if (LANGUAGES[i].toLowerCase() === v.toLowerCase()) return LANGUAGES[i];
  }
  return "en";
}

function settingsPath(env, platform, home) {
  var p = pathApi(platform);
  if (env.KEYMASTER_SETTINGS) return env.KEYMASTER_SETTINGS;
  if (platform === "win32") {
    var appData = env.APPDATA || p.join(home, "AppData", "Roaming");
    return p.join(appData, "Keymaster", "settings.json");
  }
  var base = env.XDG_CONFIG_HOME || p.join(home, ".config");
  return p.join(base, "keymaster", "settings.json");
}

function readSettings(file, fsApi) {
  var f = fsApi || fs;
  try {
    var data = JSON.parse(f.readFileSync(file, "utf8").replace(/^﻿/, ""));
    return data && typeof data === "object" && !Array.isArray(data) ? data : {};
  } catch (e) {
    return {};
  }
}

function venvPython(core, platform) {
  var p = pathApi(platform);
  return platform === "win32" ? p.join(core, ".venv", "Scripts", "python.exe") : p.join(core, ".venv", "bin", "python");
}

function nonEmpty(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function resolveSettings(env, fileData, platform, exists) {
  var core = nonEmpty(env.KEYMASTER_CORE) || nonEmpty(fileData.core);
  var python = nonEmpty(env.KEYMASTER_PYTHON) || nonEmpty(fileData.python);
  if (!python && core && exists && exists(venvPython(core, platform))) python = venvPython(core, platform);
  var language = normalizeLanguage(nonEmpty(env.KEYMASTER_LANGUAGE) || fileData.language);
  return { python: python, core: core, language: language };
}

function load(options) {
  var o = options || {};
  var env = o.env || process.env;
  var platform = o.platform || process.platform;
  var home = o.home || require("os").homedir();
  var f = o.fs || fs;
  var file = settingsPath(env, platform, home);
  var data = readSettings(file, f);
  var resolved = resolveSettings(env, data, platform, function (p) { return f.existsSync(p); });
  resolved.file = file;
  return resolved;
}

function writeLanguage(file, language, fsApi) {
  var f = fsApi || fs;
  var data = readSettings(file, f);
  data.language = normalizeLanguage(language);
  f.mkdirSync(nodePath.dirname(file), { recursive: true });
  var tmp = file + ".tmp-" + process.pid;
  f.writeFileSync(tmp, JSON.stringify(data, null, 2) + "\n", "utf8");
  f.renameSync(tmp, file);
  return data;
}

module.exports = {
  LANGUAGES: LANGUAGES,
  normalizeLanguage: normalizeLanguage,
  settingsPath: settingsPath,
  readSettings: readSettings,
  resolveSettings: resolveSettings,
  venvPython: venvPython,
  load: load,
  writeLanguage: writeLanguage
};
