"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { PKG, EXT, lib, tmpDir, python } = require("./helpers");

const LIST = `
import json, sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
z.extractall(sys.argv[2])
print(json.dumps(z.namelist()))
`;

test("build.py writes an installable zip with bundled translations", () => {
  const out = tmpDir("build-");
  const printed = execFileSync(python(), [path.join(PKG, "build.py"), "--out", out, "--version", "1.2.3-pr.4"], { encoding: "utf8" }).trim();
  const zip = path.join(out, "keymaster-adobe-1.2.3-pr.4.zip");
  assert.strictEqual(printed, zip);
  const dest = path.join(out, "x");
  const names = JSON.parse(execFileSync(python(), ["-c", LIST, zip, dest], { encoding: "utf8" }));
  for (const name of ["install.ps1", "install.cmd", "uninstall.ps1", "uninstall.cmd", "README.md", "README.es-419.md", "LICENSE"]) {
    assert.ok(names.includes("keymaster-adobe/" + name), name);
  }
  const ext = path.join(dest, "keymaster-adobe", "com.keymaster.adobe");
  const manifest = fs.readFileSync(path.join(ext, "CSXS", "manifest.xml"), "utf8");
  assert.match(manifest, /ExtensionBundleVersion="1\.2\.3"/);
  assert.match(manifest, /<Extension Id="com\.keymaster\.adobe\.panel" Version="1\.2\.3"\/>/);
  for (const rel of ["index.html", "js/panel.js", "jsx/common.jsx", "jsx/aeft.jsx", "jsx/ppro.jsx", "vendor/adobe/CSInterface.js", "vendor/adobe/LICENSE.pdf"]) {
    assert.ok(fs.existsSync(path.join(ext, rel)), rel);
  }
  const srcLibs = fs.readdirSync(path.join(EXT, "js", "lib")).sort();
  assert.deepStrictEqual(fs.readdirSync(path.join(ext, "js", "lib")).sort(), srcLibs);
  const tables = lib("i18n").loadTables(ext, ["en", "es-419"]);
  const own = JSON.parse(fs.readFileSync(path.join(PKG, "i18n", "es-419.json"), "utf8"));
  for (const key of Object.keys(own)) assert.strictEqual(tables["es-419"][key], own[key]);
  assert.ok(!names.some((n) => n.includes("/tests/") || n.endsWith("build.py") || n.endsWith("package.json")));
});

test("install scripts are UTF-8 with BOM and CRLF so Windows PowerShell reads the accents", () => {
  for (const name of ["install.ps1", "uninstall.ps1"]) {
    const bytes = fs.readFileSync(path.join(PKG, "install", name));
    assert.deepStrictEqual([...bytes.subarray(0, 3)], [0xef, 0xbb, 0xbf], name);
    const text = bytes.toString("utf8");
    assert.ok(!/[^\r]\n/.test(text), name + " has LF-only lines");
  }
  const install = fs.readFileSync(path.join(PKG, "install", "install.ps1"), "utf8");
  assert.match(install, /@\('11', '12'\)/);
  assert.match(install, /CSXS\.\$version/);
  assert.match(install, /PlayerDebugMode/);
  assert.match(install, /Adobe\\CEP\\extensions/);
  for (const name of ["install", "uninstall"]) {
    const cmd = fs.readFileSync(path.join(PKG, "install", name + ".cmd"), "utf8");
    assert.ok(cmd.includes('-ExecutionPolicy Bypass -File "%~dp0' + name + '.ps1"'));
  }
});

test("a version without numbers is refused", () => {
  assert.throws(() => execFileSync(python(), [path.join(PKG, "build.py"), "--out", tmpDir("build-"), "--version", "staging"], { stdio: "pipe" }));
});
