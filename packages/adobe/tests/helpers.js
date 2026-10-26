"use strict";

const path = require("path");
const fs = require("fs");

const PKG = path.resolve(__dirname, "..");
const EXT = path.join(PKG, "extension");
const ROOT = path.resolve(PKG, "..", "..");
const FAKE_CORE = path.join(ROOT, "packages", "core", "testing", "fake_core");

function lib(name) {
  return require(path.join(EXT, "js", "lib", name + ".js"));
}

function tmpDir(prefix) {
  const base = path.join(ROOT, "tmp", "adobe-tests");
  fs.mkdirSync(base, { recursive: true });
  return fs.mkdtempSync(path.join(base, prefix || "t-"));
}

function python() {
  return process.env.PYTHON || "python3";
}

module.exports = { PKG, EXT, ROOT, FAKE_CORE, lib, tmpDir, python };
