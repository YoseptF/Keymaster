"use strict";

const test = require("node:test");
const assert = require("node:assert");
const { lib } = require("./helpers");
const theme = lib("theme");

function skin(r, g, b) {
  return { panelBackgroundColor: { color: { red: r, green: g, blue: b, alpha: 255 } }, baseFontSize: 12, baseFontFamily: "Segoe UI" };
}

test("dark host theme gives light text and lifted controls", () => {
  const v = theme.themeVars(skin(35, 35, 35));
  assert.strictEqual(v["--km-bg"], "#232323");
  assert.strictEqual(v["--km-fg"], "#d8d8d8");
  assert.strictEqual(v["--km-border"], "#3f3f3f");
  assert.strictEqual(v["--km-field"], "#171717");
  assert.strictEqual(v["--km-font-size"], "12px");
  assert.strictEqual(v["--km-font"], '"Segoe UI", sans-serif');
});

test("light host theme gives dark text and darker controls", () => {
  const v = theme.themeVars(skin(240, 240, 240));
  assert.strictEqual(v["--km-fg"], "#1e1e1e");
  assert.strictEqual(v["--km-border"], "#d4d4d4");
  assert.strictEqual(v["--km-field"], "#fcfcfc");
});

test("missing skin info falls back to a dark default", () => {
  const v = theme.themeVars(undefined);
  assert.strictEqual(v["--km-bg"], "#232323");
  assert.strictEqual(v["--km-font-size"], "11px");
  assert.strictEqual(theme.hex({ r: 300, g: -4, b: 15.6 }), "#ff0010");
});
