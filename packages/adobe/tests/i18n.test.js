"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const { lib, EXT, PKG, ROOT, tmpDir } = require("./helpers");
const i18nLib = lib("i18n");

const tables = {
  en: { "adobe.a": "Hello {name}", "adobe.b": "Only English", "adobe.empty": "" },
  "es-419": { "adobe.a": "Hola {name}", "adobe.empty": "" }
};

test("t picks the language, falls back to English, then to the key", () => {
  const i18n = i18nLib.createI18n(tables, "es-419");
  assert.strictEqual(i18n.t("adobe.a", { name: "Ana" }), "Hola Ana");
  assert.strictEqual(i18n.t("adobe.b"), "Only English");
  assert.strictEqual(i18n.t("adobe.missing"), "adobe.missing");
  assert.strictEqual(i18n.t("adobe.empty"), "adobe.empty");
  assert.ok(i18n.has("adobe.b"));
  assert.ok(!i18n.has("adobe.missing"));
  i18n.setLanguage("en");
  assert.strictEqual(i18n.t("adobe.a", { name: "Ana" }), "Hello Ana");
  assert.strictEqual(i18n.language(), "en");
});

test("placeholders without a value stay visible", () => {
  assert.strictEqual(i18nLib.format("{a} and {b}", { a: 1 }), "1 and {b}");
  assert.strictEqual(i18nLib.format("{a}", { a: 0 }), "0");
  assert.strictEqual(i18nLib.format("{toString}", {}), "{toString}");
});

function fakeDocument() {
  function el(attrs) {
    return {
      attrs: Object.assign({}, attrs),
      textContent: "",
      getAttribute(n) { return Object.prototype.hasOwnProperty.call(this.attrs, n) ? this.attrs[n] : null; },
      setAttribute(n, v) { this.attrs[n] = String(v); }
    };
  }
  const nodes = [
    el({ "data-i18n": "adobe.a" }),
    el({ "data-i18n-title": "adobe.b" }),
    el({ "data-i18n": "adobe.a", "data-i18n-placeholder": "adobe.b" })
  ];
  const html = el({});
  return {
    nodes,
    documentElement: html,
    querySelectorAll(sel) {
      assert.strictEqual(sel, "[data-i18n], [data-i18n-title], [data-i18n-placeholder]");
      return nodes;
    }
  };
}

test("binding fills text, titles and placeholders and re-translates live", () => {
  const doc = fakeDocument();
  const i18n = i18nLib.createI18n(tables, "en");
  i18nLib.translateDocument(doc, i18n);
  assert.strictEqual(doc.nodes[0].textContent, "Hello {name}");
  assert.strictEqual(doc.nodes[1].attrs.title, "Only English");
  assert.strictEqual(doc.nodes[1].textContent, "");
  assert.strictEqual(doc.nodes[2].attrs.placeholder, "Only English");
  assert.strictEqual(doc.documentElement.attrs.lang, "en");
  i18n.setLanguage("es-419");
  i18nLib.translateDocument(doc, i18n);
  assert.strictEqual(doc.nodes[0].textContent, "Hola {name}");
  assert.strictEqual(doc.nodes[1].attrs.title, "Only English");
  assert.strictEqual(doc.documentElement.attrs.lang, "es-419");
});

test("dev layout loads the repo tables, bundled layout wins when present", () => {
  const dev = i18nLib.loadTables(EXT, ["en", "es-419"]);
  const own = JSON.parse(fs.readFileSync(path.join(PKG, "i18n", "en.json"), "utf8"));
  for (const key of Object.keys(own)) assert.strictEqual(dev.en[key], own[key]);
  const core = JSON.parse(fs.readFileSync(path.join(ROOT, "packages", "core", "i18n", "en.json"), "utf8"));
  for (const key of Object.keys(core)) assert.strictEqual(dev.en[key], core[key]);

  const ext = path.join(tmpDir("bundle-"), "com.keymaster.adobe");
  fs.mkdirSync(path.join(ext, "i18n", "adobe"), { recursive: true });
  fs.mkdirSync(path.join(ext, "i18n", "core"), { recursive: true });
  fs.writeFileSync(path.join(ext, "i18n", "adobe", "en.json"), JSON.stringify({ "adobe.x": "X" }));
  fs.writeFileSync(path.join(ext, "i18n", "core", "en.json"), JSON.stringify({ "core.y": "Y" }));
  const bundled = i18nLib.loadTables(ext, ["en", "es-419"]);
  assert.deepStrictEqual(bundled.en, { "core.y": "Y", "adobe.x": "X" });
  assert.deepStrictEqual(bundled["es-419"], {});
});

test("the panel's own tables have the same keys and placeholders", () => {
  const en = JSON.parse(fs.readFileSync(path.join(PKG, "i18n", "en.json"), "utf8"));
  const es = JSON.parse(fs.readFileSync(path.join(PKG, "i18n", "es-419.json"), "utf8"));
  assert.deepStrictEqual(Object.keys(es).sort(), Object.keys(en).sort());
  const ph = (s) => (s.match(/\{[a-z0-9_]+\}/gi) || []).sort().join();
  for (const key of Object.keys(en)) assert.strictEqual(ph(es[key]), ph(en[key]), key);
});

test("every data-i18n key in the HTML exists", () => {
  const html = fs.readFileSync(path.join(EXT, "index.html"), "utf8");
  const en = JSON.parse(fs.readFileSync(path.join(PKG, "i18n", "en.json"), "utf8"));
  const keys = [...html.matchAll(/data-i18n(?:-[a-z]+)?="([^"]+)"/g)].map((m) => m[1]);
  assert.ok(keys.length > 20);
  for (const key of keys) assert.ok(en[key], key);
});
