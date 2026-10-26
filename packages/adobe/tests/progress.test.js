"use strict";

const test = require("node:test");
const assert = require("node:assert");
const { lib, EXT } = require("./helpers");
const progress = lib("progress");
const i18nLib = lib("i18n");

test("progress never goes backwards and stays in [0, 1]", () => {
  const p = new progress.ProgressTracker();
  const seen = [0.1, 0.05, 0.4, Number.NaN, 0.3, 2, -1, 0.9].map((f) => p.update({ fraction: f }));
  assert.deepStrictEqual(seen, [0.1, 0.1, 0.4, 0.4, 0.4, 1, 1, 1]);
  for (let i = 1; i < seen.length; i++) assert.ok(seen[i] >= seen[i - 1]);
  assert.strictEqual(p.percent(), 100);
});

test("string fractions are accepted, garbage ignored", () => {
  const p = new progress.ProgressTracker();
  p.update({ fraction: "0.256" });
  p.update({ fraction: "abc" });
  p.update(null);
  assert.strictEqual(p.percent(), 25);
});

test("phase text uses the core key when it is translated, else the panel's own", () => {
  const i18n = i18nLib.createI18n({
    en: { "core.progress.stage1": "Core stage one", "adobe.phase.stage2": "Panel stage two", "adobe.phase.working": "Working" },
    "es-419": { "core.progress.stage1": "Etapa uno" }
  }, "es-419");
  const p = new progress.ProgressTracker();
  p.update({ phase: "stage1", fraction: 0.3, message_key: "core.progress.stage1" });
  assert.strictEqual(p.text(i18n), "Etapa uno");
  p.update({ phase: "stage2", fraction: 0.5, message_key: "core.progress.stage2" });
  assert.strictEqual(p.text(i18n), "Panel stage two");
  p.update({ phase: "mystery", fraction: 0.6 });
  assert.strictEqual(p.text(i18n), "Working");
});

test("every core phase has a panel fallback in both languages", () => {
  const tables = i18nLib.loadTables(EXT, ["en", "es-419"]);
  for (const lang of ["en", "es-419"]) {
    for (const phase of progress.PHASES.concat(["unknown"])) {
      const key = progress.phaseKey(phase).message_key;
      assert.ok(tables[lang][key], lang + " " + key);
    }
  }
});
