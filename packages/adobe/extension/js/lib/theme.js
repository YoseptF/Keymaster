"use strict";

function clamp(n) {
  return Math.max(0, Math.min(255, Math.round(n)));
}

function hex(rgb) {
  return "#" + [rgb.r, rgb.g, rgb.b].map(function (v) {
    var s = clamp(v).toString(16);
    return s.length === 1 ? "0" + s : s;
  }).join("");
}

function shift(rgb, amount) {
  return { r: rgb.r + amount, g: rgb.g + amount, b: rgb.b + amount };
}

function readColor(skin) {
  var c = skin && skin.panelBackgroundColor && skin.panelBackgroundColor.color;
  if (!c) return { r: 35, g: 35, b: 35 };
  return { r: Number(c.red) || 0, g: Number(c.green) || 0, b: Number(c.blue) || 0 };
}

function luminance(rgb) {
  return (0.2126 * rgb.r + 0.7152 * rgb.g + 0.0722 * rgb.b) / 255;
}

function themeVars(skin) {
  var bg = readColor(skin);
  var dark = luminance(bg) < 0.5;
  var dir = dark ? 1 : -1;
  var size = skin && Number(skin.baseFontSize) > 0 ? Number(skin.baseFontSize) : 11;
  return {
    "--km-bg": hex(bg),
    "--km-fg": dark ? "#d8d8d8" : "#1e1e1e",
    "--km-muted": dark ? "#9a9a9a" : "#5a5a5a",
    "--km-field": hex(shift(bg, -12 * dir)),
    "--km-border": hex(shift(bg, 28 * dir)),
    "--km-button": hex(shift(bg, 18 * dir)),
    "--km-button-hover": hex(shift(bg, 30 * dir)),
    "--km-accent": dark ? "#2d8ceb" : "#1473e6",
    "--km-error": dark ? "#ff7b72" : "#c9252d",
    "--km-ok": dark ? "#5fc77a" : "#268e47",
    "--km-font-size": size + "px",
    "--km-font": skin && skin.baseFontFamily ? '"' + String(skin.baseFontFamily).replace(/"/g, "") + '", sans-serif' : "sans-serif"
  };
}

module.exports = { themeVars: themeVars, hex: hex, luminance: luminance };
