"use strict";

const vm = require("vm");
const fs = require("fs");
const path = require("path");
const { EXT } = require("./helpers");

function hostContext(globals) {
  const context = vm.createContext(Object.assign({ BridgeTalk: { appName: "test" } }, globals));
  for (const file of arguments.length > 1 ? Array.prototype.slice.call(arguments, 1) : []) {
    vm.runInContext(fs.readFileSync(path.join(EXT, "jsx", file), "utf8"), context, { filename: file });
  }
  return context;
}

function evalScript(context) {
  return function (script, callback) {
    let out;
    try {
      out = String(vm.runInContext(script, context));
    } catch (e) {
      out = "EvalScript error.";
    }
    setImmediate(() => callback(out));
  };
}

function collection(items, countName) {
  const c = {};
  Object.defineProperty(c, countName, { get: () => items.length });
  Object.defineProperty(c, "_items", { value: items });
  const sync = () => {
    for (let i = 0; i < items.length + 2; i++) delete c[i];
    items.forEach((it, i) => { c[i] = it; });
  };
  Object.defineProperty(c, "_sync", { value: sync });
  sync();
  return c;
}

module.exports = { hostContext, evalScript, collection };
