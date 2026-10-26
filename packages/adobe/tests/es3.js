"use strict";

const REGEX_PREV = /[(,=:[!&|?{};+\-*%<>~^]$/;
const KEYWORD_PREV = /(?:^|[^\w$])(?:return|typeof|instanceof|in|of|new|delete|void|throw|case|do|else)$/;

function strip(source) {
  let out = "";
  let i = 0;
  const n = source.length;
  while (i < n) {
    const c = source[i];
    const next = source[i + 1];
    if (c === "/" && next === "/") {
      while (i < n && source[i] !== "\n") i++;
      continue;
    }
    if (c === "/" && next === "*") {
      const end = source.indexOf("*/", i + 2);
      const stop = end === -1 ? n : end + 2;
      out += " " + source.slice(i, stop).replace(/[^\n]/g, "");
      i = stop;
      continue;
    }
    if (c === '"' || c === "'") {
      i++;
      while (i < n && source[i] !== c) {
        if (source[i] === "\\") i++;
        if (source[i] === "\n") throw new Error("unterminated string");
        i++;
      }
      i++;
      out += '""';
      continue;
    }
    if (c === "`") {
      out += "`";
      i++;
      continue;
    }
    if (c === "/") {
      const before = out.replace(/\s+$/, "");
      if (before === "" || REGEX_PREV.test(before) || KEYWORD_PREV.test(before)) {
        i++;
        let inClass = false;
        while (i < n) {
          const r = source[i];
          if (r === "\\") { i += 2; continue; }
          if (r === "\n") throw new Error("unterminated regex");
          if (r === "[") inClass = true;
          else if (r === "]") inClass = false;
          else if (r === "/" && !inClass) break;
          i++;
        }
        i++;
        while (i < n && /[a-z]/i.test(source[i])) i++;
        out += "/re/";
        continue;
      }
    }
    out += c;
    i++;
  }
  return out;
}

const RULES = [
  [/\blet\b/, "let"],
  [/\bconst\b/, "const"],
  [/=>/, "arrow function"],
  [/`/, "template literal"],
  [/\bclass\b/, "class"],
  [/\.\.\./, "spread or rest"],
  [/\bfor\s*\([^;)]*\bof\b/, "for...of"],
  [/\b(?:async|await|yield)\b/, "async or generator"],
  [/\bimport\b|\bexport\b/, "module syntax"],
  [/\.(?:forEach|map|filter|reduce|some|every|trim|bind)\s*\(/, "ES5 library method"],
  [/\bJSON\s*\./, "JSON object"],
  [/\bObject\s*\.\s*(?:keys|create|defineProperty|assign|freeze)\b/, "ES5 Object method"],
  [/\bArray\s*\.\s*isArray\b/, "Array.isArray"],
  [/\b(?:get|set)\s+\w+\s*\(/, "accessor"],
  [/\bfunction\s*\*/, "generator"]
];

function es3Problems(source) {
  const code = strip(source);
  const problems = [];
  const lines = code.split("\n");
  lines.forEach((line, index) => {
    for (const [pattern, name] of RULES) {
      if (pattern.test(line)) problems.push({ line: index + 1, rule: name, text: line.trim() });
    }
  });
  return problems;
}

module.exports = { strip, es3Problems };
