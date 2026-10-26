"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const { EXT, python } = require("./helpers");

const READ = `
import json, sys, xml.etree.ElementTree as ET
root = ET.parse(sys.argv[1]).getroot()
print(json.dumps({
    "tag": root.tag,
    "bundle": root.get("ExtensionBundleId"),
    "hosts": {h.get("Name"): h.get("Version") for h in root.iter("Host")},
    "runtime": [r.get("Version") for r in root.iter("RequiredRuntime") if r.get("Name") == "CSXS"],
    "extensions": [e.get("Id") for e in root.find("ExtensionList")],
    "dispatch": [e.get("Id") for e in root.find("DispatchInfoList")],
    "main": root.findtext(".//MainPath"),
    "script": root.findtext(".//ScriptPath"),
    "params": [p.text for p in root.iter("Parameter")],
    "type": root.findtext(".//UI/Type"),
}))
`;

function read(file) {
  return JSON.parse(execFileSync(python(), ["-c", READ, file], { encoding: "utf8" }));
}

test("the manifest is well-formed and targets both hosts on CEP 11+", () => {
  const m = read(path.join(EXT, "CSXS", "manifest.xml"));
  assert.strictEqual(m.tag, "ExtensionManifest");
  assert.deepStrictEqual(Object.keys(m.hosts).sort(), ["AEFT", "PPRO"]);
  for (const range of Object.values(m.hosts)) {
    const [lo, hi] = range.replace(/[[\]()]/g, "").split(",").map(Number);
    assert.ok(lo <= 22 && hi >= 26, range);
  }
  assert.ok(Number(m.runtime[0]) >= 11);
  assert.deepStrictEqual(m.extensions, m.dispatch);
  assert.strictEqual(m.type, "Panel");
  assert.ok(m.params.includes("--enable-nodejs"));
  assert.ok(m.params.includes("--mixed-context"));
  assert.ok(fs.existsSync(path.join(EXT, m.main)));
  assert.ok(fs.existsSync(path.join(EXT, m.script)));
});

test("a broken manifest would be caught", () => {
  const bad = path.join(require("./helpers").tmpDir("manifest-"), "manifest.xml");
  fs.writeFileSync(bad, "<ExtensionManifest><HostList></ExtensionManifest>");
  assert.throws(() => execFileSync(python(), ["-c", READ, bad], { stdio: "pipe" }));
});

test("the panel loads only files that exist", () => {
  const html = fs.readFileSync(path.join(EXT, "index.html"), "utf8");
  const refs = [...html.matchAll(/(?:src|href)="([^"]+)"/g)].map((m) => m[1]);
  assert.ok(refs.length >= 3);
  for (const ref of refs) assert.ok(fs.existsSync(path.join(EXT, ref)), ref);
  const panel = fs.readFileSync(path.join(EXT, "js", "panel.js"), "utf8");
  for (const m of panel.matchAll(/lib\("([a-z]+)"\)/g)) assert.ok(fs.existsSync(path.join(EXT, "js", "lib", m[1] + ".js")), m[1]);
});
