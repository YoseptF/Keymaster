"use strict";

const test = require("node:test");
const assert = require("node:assert");
const vm = require("vm");
const fs = require("fs");
const path = require("path");
const { EXT, FAKE_CORE, tmpDir, python } = require("./helpers");
const { hostContext, evalScript } = require("./jsx-harness");
const { makeAe } = require("./ae-mock");
const { parse } = require("./fake-dom");

async function until(check, what) {
  const deadline = Date.now() + 10000;
  while (!check()) {
    if (Date.now() > deadline) throw new Error("timed out waiting for " + what);
    await new Promise((r) => setTimeout(r, 10));
  }
}

function boot(options) {
  const dir = tmpDir("panel-");
  const settingsFile = path.join(dir, "Keymaster", "settings.json");
  fs.mkdirSync(path.dirname(settingsFile), { recursive: true });
  fs.writeFileSync(settingsFile, JSON.stringify(Object.assign({ language: "es-419", python: python(), core: FAKE_CORE }, options.settings || {})));
  process.env.KEYMASTER_SETTINGS = settingsFile;
  delete process.env.KEYMASTER_LANGUAGE;
  delete process.env.KEYMASTER_PYTHON;
  delete process.env.KEYMASTER_CORE;

  const ae = makeAe();
  const hostCtx = hostContext(Object.assign({}, ae.globals, {
    $: { evalFile: (file) => vm.runInContext(fs.readFileSync(file, "utf8"), hostCtx, { filename: file }) }
  }));
  const comp = ae.add(new ae.CompItem("Main"));
  const clip = path.join(dir, "green plate.mov");
  fs.writeFileSync(clip, "x");
  const plate = ae.add(new ae.FootageItem(new ae.File(clip), { fps: 25 }));
  const layer = new ae.AVLayer(comp, plate, "Actor");
  comp.list.push(layer);
  ae.project.activeItem = comp;
  comp.selectedLayers = [layer];

  const doc = parse(fs.readFileSync(path.join(EXT, "index.html"), "utf8"));
  const csListeners = {};
  const hostEval = evalScript(hostCtx);
  const scripts = [];
  function CSInterface() {}
  CSInterface.THEME_COLOR_CHANGED_EVENT = "com.adobe.csxs.events.ThemeColorChanged";
  CSInterface.prototype.getSystemPath = () => EXT;
  CSInterface.prototype.getHostEnvironment = () => ({
    appName: options.appName || "AEFT",
    appSkinInfo: options.skin || { panelBackgroundColor: { color: { red: 50, green: 50, blue: 50 } }, baseFontSize: 10 }
  });
  CSInterface.prototype.evalScript = (script, cb) => { scripts.push(script); hostEval(script, cb); };
  CSInterface.prototype.addEventListener = (type, fn) => { csListeners[type] = fn; };
  const storage = {};
  const dialogs = [];
  const windowListeners = {};
  const ctx = vm.createContext({
    require,
    process,
    setTimeout,
    clearTimeout,
    console,
    document: doc,
    CSInterface,
    SystemPath: { EXTENSION: "extension" },
    localStorage: {
      getItem: (k) => (k in storage ? storage[k] : null),
      setItem: (k, v) => { storage[k] = String(v); }
    },
    cep: { fs: { showOpenDialog: (multi, dirs, title, initial, types) => { dialogs.push({ dirs, title, types }); return { err: 0, data: [options.pick || "/picked"] }; } } },
    addEventListener: (type, fn) => { windowListeners[type] = fn; }
  });
  ctx.window = ctx;
  vm.runInContext(fs.readFileSync(path.join(EXT, "js", "panel.js"), "utf8"), ctx, { filename: "panel.js" });
  const $ = (id) => doc.getElementById(id);
  return { $, doc, ae, comp, layer, settingsFile, storage, dialogs, csListeners, windowListeners, scripts };
}

test("the panel boots translated, themed, with the selection shown", async () => {
  const p = boot({});
  await until(() => p.$("source-name").textContent === "Actor", "selection");
  assert.strictEqual(p.$("key").textContent, "Hacer key");
  assert.strictEqual(p.$("refresh").getAttribute("title"), "Vuelve a leer la capa o el clip seleccionado");
  assert.strictEqual(p.doc.documentElement.getAttribute("lang"), "es-419");
  assert.strictEqual(p.$("status").textContent, "Listo.");
  assert.strictEqual(p.$("format").value, "exr");
  assert.strictEqual(p.$("language").value, "es-419");
  assert.strictEqual(p.$("hint-path").textContent, "Ninguna");
  assert.strictEqual(p.doc.documentElement.style.props["--km-bg"], "#323232");
  assert.strictEqual(p.doc.documentElement.style.props["--km-font-size"], "10px");
  assert.match(p.scripts[0], /^\$\.evalFile\(".*\/jsx\/common\.jsx"\)/);
  assert.match(p.scripts[1], /\/jsx\/aeft\.jsx/);
  const empty = p.doc.all.filter((e) => e.getAttribute("data-i18n") !== null && !e.textContent);
  assert.deepStrictEqual(empty.map((e) => e.getAttribute("data-i18n")), []);
});

test("Premiere defaults to video and the theme follows host changes", async () => {
  const p = boot({ appName: "PPRO" });
  assert.strictEqual(p.$("format").value, "video");
  assert.strictEqual(p.$("source-name").textContent, "Selecciona un clip en la secuencia activa.");
  assert.ok(p.csListeners["com.adobe.csxs.events.ThemeColorChanged"]);
});

test("switching language writes the shared settings and re-translates live", async () => {
  const p = boot({});
  await until(() => p.$("source-name").textContent === "Actor", "selection");
  p.$("language").value = "en";
  p.$("language").dispatch("change");
  assert.strictEqual(JSON.parse(fs.readFileSync(p.settingsFile, "utf8")).language, "en");
  assert.strictEqual(JSON.parse(fs.readFileSync(p.settingsFile, "utf8")).core, FAKE_CORE);
  assert.strictEqual(p.$("key").textContent, "Key");
  assert.strictEqual(p.$("status").textContent, "Ready.");
  assert.strictEqual(p.doc.documentElement.getAttribute("lang"), "en");
  const s = JSON.parse(fs.readFileSync(p.settingsFile, "utf8"));
  s.language = "es-419";
  fs.writeFileSync(p.settingsFile, JSON.stringify(s));
  p.windowListeners.focus();
  assert.strictEqual(p.$("key").textContent, "Hacer key");
});

test("Key runs the core, shows progress and places the cutout", async () => {
  const p = boot({});
  await until(() => p.$("source-name").textContent === "Actor", "selection");
  p.$("key").click();
  assert.strictEqual(p.$("key").disabled, true);
  assert.strictEqual(p.$("cancel").disabled, false);
  await until(() => p.$("status").className === "status ok", "done");
  assert.match(p.$("status").textContent, /^Listo en \d+\.\d s\. El recorte quedó encima del origen\./);
  assert.strictEqual(Number(p.$("progress").value), 100);
  assert.strictEqual(p.$("percent").textContent, "100%");
  assert.ok(p.$("phase").textContent.length > 0);
  assert.strictEqual(p.comp.numLayers, 2);
  assert.strictEqual(p.comp.layer(2), p.layer);
  assert.strictEqual(p.layer.enabled, false);
  assert.match(p.comp.layer(1).source.name, /^cutout_0+\.png$/);
  assert.strictEqual(p.$("key").disabled, false);
  assert.strictEqual(p.$("cancel").disabled, true);
  assert.deepStrictEqual(JSON.parse(p.storage["keymaster.options.AEFT"]).outputs, ["cutout"]);
});

test("core errors show translated with details", async () => {
  process.env.KEYMASTER_FAKE_FAIL = "no_gpu";
  try {
    const p = boot({});
    await until(() => p.$("source-name").textContent === "Actor", "selection");
    p.$("key").click();
    await until(() => p.$("status").className === "status error", "error");
    const tables = require(path.join(EXT, "js", "lib", "i18n.js")).loadTables(EXT, ["en", "es-419"]);
    const expected = tables["es-419"]["core.error.no_gpu"] || tables.en["core.error.no_gpu"] || "Algo salió mal: fake failure no_gpu";
    assert.strictEqual(p.$("status").textContent, expected);
    assert.strictEqual(p.$("details").hidden, false);
    assert.match(p.$("details-text").textContent, /fake failure no_gpu/);
  } finally {
    delete process.env.KEYMASTER_FAKE_FAIL;
  }
});

test("cancel stops the run", async () => {
  process.env.KEYMASTER_FAKE_DELAY = "0.5";
  try {
    const p = boot({});
    await until(() => p.$("source-name").textContent === "Actor", "selection");
    p.$("key").click();
    await until(() => Number(p.$("progress").value) > 0, "progress");
    assert.ok(p.$("phase").textContent.length > 0);
    p.$("cancel").click();
    assert.strictEqual(p.$("status").textContent, "Cancelando…");
    await until(() => p.$("status").textContent === "Cancelado.", "cancelled");
    assert.strictEqual(p.comp.numLayers, 1);
  } finally {
    delete process.env.KEYMASTER_FAKE_DELAY;
  }
});

test("setup check lists the doctor results", async () => {
  const p = boot({ settings: { language: "en" } });
  p.$("doctor").click();
  assert.strictEqual(p.$("setup-status").textContent, "Checking your setup…");
  await until(() => p.$("checks").children.length === 4, "doctor");
  assert.strictEqual(p.$("setup-status").textContent, "Everything is ready.");
  assert.deepStrictEqual(p.$("checks").children.map((li) => li.className), ["ok", "ok", "ok", "ok"]);
  assert.strictEqual(p.$("checks").children[0].textContent, "gpu: OK");
});

test("a missing core shows the install hint", async () => {
  const p = boot({ settings: { python: "", core: "" } });
  assert.strictEqual(p.$("status").textContent, "El núcleo de Keymaster todavía no está instalado. Instálalo primero y vuelve a abrir este panel.");
  p.$("doctor").click();
  await until(() => p.$("setup-status").className === "status error", "doctor error");
});

test("options persist and pickers use translated titles", async () => {
  const p = boot({ settings: { language: "en" }, pick: "/shots/hint.png" });
  p.$("hint-choose").click();
  assert.strictEqual(p.dialogs[0].title, "Choose a first-frame hint image");
  assert.strictEqual(p.$("hint-path").textContent, "/shots/hint.png");
  p.$("despill").value = "0.3";
  p.$("despill").dispatch("input");
  assert.strictEqual(p.$("despill-value").textContent, "0.30");
  p.$("despill").dispatch("change");
  const saved = JSON.parse(p.storage["keymaster.options.AEFT"]);
  assert.strictEqual(saved.hintFirstFrame, "/shots/hint.png");
  assert.strictEqual(saved.despill, 0.3);
  p.$("hint-clear").click();
  assert.strictEqual(p.$("hint-path").textContent, "None");
  p.$("output-choose").click();
  assert.strictEqual(p.dialogs[1].dirs, true);
  assert.strictEqual(p.$("output-root").textContent, "/shots/hint.png");
});

test("an unsupported app is told so", () => {
  const p = boot({ appName: "PHXS", settings: { language: "en" } });
  assert.strictEqual(p.$("status").textContent, "This panel only works in After Effects and Premiere Pro (this app is PHXS).");
  assert.strictEqual(p.$("key").disabled, true);
});
