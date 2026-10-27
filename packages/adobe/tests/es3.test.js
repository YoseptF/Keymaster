"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const { EXT } = require("./helpers");
const { es3Problems, strip } = require("./es3");

const jsxFiles = fs.readdirSync(path.join(EXT, "jsx")).filter((f) => f.endsWith(".jsx"));

test("there are host scripts to check", () => {
  assert.deepStrictEqual(jsxFiles.sort(), ["aeft.jsx", "common.jsx", "ppro.jsx"]);
});

for (const file of jsxFiles) {
  test(file + " is ES3-safe", () => {
    const problems = es3Problems(fs.readFileSync(path.join(EXT, "jsx", file), "utf8"));
    assert.deepStrictEqual(problems, []);
  });
}

test("the checker catches modern syntax", () => {
  const bad = {
    "let a = 1;": "let",
    "const b = 2;": "const",
    "var f = (x) => x;": "arrow function",
    "var s = `hi ${a}`;": "template literal",
    "class A {}": "class",
    "f(...args);": "spread or rest",
    "for (var x of xs) {}": "for...of",
    "list.forEach(function () {});": "ES5 library method",
    "var o = JSON.parse(t);": "JSON object",
    "Object.keys(o);": "ES5 Object method",
    "async function f() {}": "async or generator"
  };
  for (const [src, rule] of Object.entries(bad)) {
    assert.ok(es3Problems(src).some((p) => p.rule === rule), src);
  }
});

test("strings, comments and regex literals do not trigger it", () => {
  const ok = [
    'var s = "let const => ` class";',
    "var r = /=>|`|const/g;",
    "var x = a / b / c;",
    "// let x = 1;",
    "/* const y = 2;\n class */ var z = 3;",
    "if (/\\.(exr|png)$/i.test(name)) { return 1; }",
    "var q = 'it\\'s => fine';"
  ];
  for (const src of ok) assert.deepStrictEqual(es3Problems(src), [], src);
  assert.strictEqual(strip("/* a\nb */x").split("\n").length, 2);
});
