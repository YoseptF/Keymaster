"use strict";

const test = require("node:test");
const assert = require("node:assert");
const vm = require("vm");
const fs = require("fs");
const path = require("path");
const { EXT } = require("./helpers");

function load() {
  const ctx = vm.createContext({});
  ctx.window = ctx;
  vm.runInContext(fs.readFileSync(path.join(EXT, "js", "cep.js"), "utf8"), ctx);
  return ctx.KeymasterCep;
}

test("extension paths from CEP file URLs", () => {
  const cep = load();
  assert.strictEqual(cep.fileUrlToPath("file:///C:/Users/Jos%C3%A9/AppData/Roaming/Adobe/CEP/extensions/com.keymaster.adobe", "win32"),
    "C:/Users/José/AppData/Roaming/Adobe/CEP/extensions/com.keymaster.adobe");
  assert.strictEqual(cep.fileUrlToPath("file:///C:/Program%20Files/Common%20Files/Adobe/CEP/extensions/x", "win32"),
    "C:/Program Files/Common Files/Adobe/CEP/extensions/x");
  assert.strictEqual(cep.fileUrlToPath("file:///home/a/ext", "linux"), "/home/a/ext");
  assert.strictEqual(cep.fileUrlToPath("C:/plain/path", "win32"), "C:/plain/path");
});

test("connect forwards to the host object CEP injects", () => {
  const cep = load();
  const calls = [];
  const host = {
    evalScript: (script, cb) => { calls.push(["eval", script]); cb("result"); },
    getHostEnvironment: () => '{"appName":"PPRO","appUILocale":"es_MX","appSkinInfo":{"baseFontSize":12}}',
    getSystemPath: (type) => { calls.push(["path", type]); return "file:///D:/ext%20dir"; },
    addEventListener: (type, fn) => calls.push(["listen", type, typeof fn])
  };
  const adobe = cep.connect(host, "win32");
  let got = null;
  adobe.evalScript("1+1", (r) => { got = r; });
  adobe.evalScript("noCallback()");
  assert.strictEqual(got, "result");
  assert.deepStrictEqual(JSON.parse(JSON.stringify(adobe.hostEnvironment())), { appName: "PPRO", appUILocale: "es_MX", appSkinInfo: { baseFontSize: 12 } });
  assert.strictEqual(adobe.extensionPath(), "D:/ext dir");
  adobe.onThemeChange(() => {});
  assert.deepStrictEqual(JSON.parse(JSON.stringify(calls)), [
    ["eval", "1+1"], ["eval", "noCallback()"], ["path", "extension"],
    ["listen", "com.adobe.csxs.events.ThemeColorChanged", "function"]
  ]);
  assert.throws(() => cep.connect(undefined, "win32"), /__adobe_cep__/);
});
