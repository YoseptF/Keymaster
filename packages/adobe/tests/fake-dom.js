"use strict";

const VOID = new Set(["meta", "link", "input", "br", "img"]);

class Element {
  constructor(tag, attrs, doc) {
    this.tagName = tag.toUpperCase();
    this.attrs = attrs;
    this.doc = doc;
    this.children = [];
    this.listeners = {};
    this.textContent = "";
    this.className = attrs.class || "";
    this.disabled = "disabled" in attrs;
    this.hidden = "hidden" in attrs;
    this.checked = "checked" in attrs;
    this._value = attrs.value !== undefined ? attrs.value : "";
    this.style = { props: {}, setProperty(name, value) { this.props[name] = value; } };
  }
  get id() { return this.attrs.id || ""; }
  get name() { return this.attrs.name || ""; }
  get value() {
    if (this.tagName === "SELECT" && this._value === "") {
      const first = this.children.find((c) => c.tagName === "OPTION");
      return first ? first.attrs.value : "";
    }
    return this._value;
  }
  set value(v) {
    if (this.tagName === "SELECT" && !this.children.some((c) => c.attrs.value === String(v))) return;
    this._value = String(v);
  }
  getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attrs, name) ? this.attrs[name] : null; }
  setAttribute(name, value) { this.attrs[name] = String(value); }
  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  dispatch(type) {
    for (const fn of this.listeners[type] || []) fn({ type, target: this });
  }
  click() {
    if (!this.disabled) this.dispatch("click");
  }
  appendChild(child) { this.children.push(child); return child; }
  set innerHTML(v) {
    if (v !== "") throw new Error("only clearing is supported");
    this.children = [];
  }
}

function parse(html) {
  const doc = {
    all: [],
    listeners: {},
    getElementById(id) { return this.all.find((e) => e.id === id) || null; },
    querySelectorAll(selector) {
      if (selector === "[data-i18n], [data-i18n-title], [data-i18n-placeholder]") {
        return this.all.filter((e) => ["data-i18n", "data-i18n-title", "data-i18n-placeholder"].some((a) => e.getAttribute(a) !== null));
      }
      if (selector === "input[name=output]") return this.all.filter((e) => e.tagName === "INPUT" && e.name === "output");
      throw new Error("unsupported selector " + selector);
    },
    createElement(tag) { return new Element(tag, {}, doc); }
  };
  const body = html.replace(/<!--[\s\S]*?-->/g, "");
  const stack = [];
  const tagRe = /<(\/?)([a-zA-Z0-9]+)([^>]*)>/g;
  let m;
  while ((m = tagRe.exec(body))) {
    const [, closing, tag, rest] = m;
    const lower = tag.toLowerCase();
    if (lower === "!doctype") continue;
    if (closing) {
      while (stack.length && stack.pop().tagName !== tag.toUpperCase()) {}
      continue;
    }
    const attrs = {};
    for (const a of rest.matchAll(/([a-zA-Z0-9_:-]+)(?:="([^"]*)")?/g)) attrs[a[1]] = a[2] === undefined ? "" : a[2];
    const el = new Element(lower, attrs, doc);
    if (stack.length) stack[stack.length - 1].appendChild(el);
    doc.all.push(el);
    if (lower === "html") doc.documentElement = el;
    if (!VOID.has(lower) && !rest.trim().endsWith("/")) stack.push(el);
  }
  return doc;
}

module.exports = { parse, Element };
