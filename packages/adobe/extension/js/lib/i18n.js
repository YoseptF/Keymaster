"use strict";

var nodePath = require("path");
var fs = require("fs");

function format(text, params) {
  if (!params) return text;
  return text.replace(/\{([a-zA-Z0-9_]+)\}/g, function (whole, name) {
    return Object.prototype.hasOwnProperty.call(params, name) && params[name] !== undefined && params[name] !== null ? String(params[name]) : whole;
  });
}

function createI18n(tables, language) {
  var state = { language: language || "en" };
  function lookup(key) {
    var own = tables[state.language];
    if (own && typeof own[key] === "string" && own[key]) return own[key];
    var en = tables.en;
    if (en && typeof en[key] === "string" && en[key]) return en[key];
    return null;
  }
  return {
    t: function (key, params) {
      var text = lookup(key);
      return text === null ? key : format(text, params);
    },
    has: function (key) {
      return lookup(key) !== null;
    },
    setLanguage: function (lang) {
      state.language = lang;
    },
    language: function () {
      return state.language;
    }
  };
}

function tableDirs(extensionRoot) {
  var p = nodePath;
  return {
    adobe: [p.join(extensionRoot, "i18n", "adobe"), p.join(extensionRoot, "..", "i18n")],
    core: [p.join(extensionRoot, "i18n", "core"), p.join(extensionRoot, "..", "..", "core", "i18n")]
  };
}

function readTable(dir, lang, fsApi) {
  try {
    var data = JSON.parse(fsApi.readFileSync(nodePath.join(dir, lang + ".json"), "utf8").replace(/^﻿/, ""));
    return data && typeof data === "object" ? data : null;
  } catch (e) {
    return null;
  }
}

function firstTable(dirs, lang, fsApi) {
  for (var i = 0; i < dirs.length; i++) {
    var table = readTable(dirs[i], lang, fsApi);
    if (table) return table;
  }
  return {};
}

function loadTables(extensionRoot, languages, fsApi) {
  var f = fsApi || fs;
  var dirs = tableDirs(extensionRoot);
  var tables = {};
  languages.forEach(function (lang) {
    tables[lang] = Object.assign({}, firstTable(dirs.core, lang, f), firstTable(dirs.adobe, lang, f));
  });
  return tables;
}

function translateDocument(root, i18n) {
  var nodes = root.querySelectorAll("[data-i18n], [data-i18n-title], [data-i18n-placeholder]");
  for (var i = 0; i < nodes.length; i++) {
    var el = nodes[i];
    var text = el.getAttribute("data-i18n");
    var title = el.getAttribute("data-i18n-title");
    var placeholder = el.getAttribute("data-i18n-placeholder");
    if (text) el.textContent = i18n.t(text);
    if (title) el.setAttribute("title", i18n.t(title));
    if (placeholder) el.setAttribute("placeholder", i18n.t(placeholder));
  }
  if (root.documentElement) root.documentElement.setAttribute("lang", i18n.language());
}

module.exports = {
  format: format,
  createI18n: createI18n,
  tableDirs: tableDirs,
  loadTables: loadTables,
  translateDocument: translateDocument
};
