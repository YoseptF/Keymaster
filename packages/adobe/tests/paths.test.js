"use strict";

const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const path = require("path");
const { lib, tmpDir } = require("./helpers");
const paths = lib("paths");

const when = new Date(2026, 9, 26, 9, 5, 7);

test("default output folder sits next to the source, unique per run", () => {
  assert.strictEqual(paths.defaultOutputDir("C:\\Shoot\\Day 1\\take.01.mov", "", when, "win32"),
    "C:\\Shoot\\Day 1\\Keymaster\\take.01_20261026-090507");
  assert.strictEqual(paths.defaultOutputDir("D:\\seq\\plate", "", when, "win32"), "D:\\seq\\Keymaster\\plate_20261026-090507");
  assert.strictEqual(paths.defaultOutputDir("/m/a b.mov", "/renders", when, "linux"), "/renders/a b_20261026-090507");
  assert.strictEqual(paths.safeName('a:b*c?. '), "a_b_c_");
  assert.strictEqual(paths.safeName("..."), "clip");
});

test("printf patterns expand like the core writes them", () => {
  assert.strictEqual(paths.expandPattern("C:\\o\\cutout_%06d.exr", 0), "C:\\o\\cutout_000000.exr");
  assert.strictEqual(paths.expandPattern("/o/a.%04d.exr", 1001), "/o/a.1001.exr");
  assert.strictEqual(paths.expandPattern("/o/a_%d.png", 7), "/o/a_7.png");
  assert.strictEqual(paths.expandPattern("/o/a_%3d.png", 7), "/o/a_7.png");
});

test("the first frame file of each output", () => {
  assert.strictEqual(paths.firstFrameFile({ type: "image_sequence", path: "/o/c", pattern: "/o/c/cutout_%06d.exr", first_frame: 3 }), "/o/c/cutout_000003.exr");
  assert.strictEqual(paths.firstFrameFile({ type: "video", path: "/o/c.mov" }), "/o/c.mov");
  assert.strictEqual(paths.firstFrameFile({ type: "image_sequence", path: "/o/c" }), "/o/c");
});

test("video files are passed as they are", () => {
  assert.deepStrictEqual(paths.resolveInput({ path: "C:\\a\\b.mov" }, "win32", { readdirSync() { throw new Error("no"); } }), { input: "C:\\a\\b.mov", sequence: false });
});

test("a frame of a numbered sequence becomes its folder", () => {
  const dir = tmpDir("seq-");
  for (let i = 1; i <= 3; i++) fs.writeFileSync(path.join(dir, "plate." + String(i).padStart(4, "0") + ".exr"), "");
  const got = paths.resolveInput({ path: path.join(dir, "plate.0001.exr") }, "linux");
  assert.deepStrictEqual(got, { input: dir, sequence: true, mixed: false });
  fs.writeFileSync(path.join(dir, "notes.png"), "");
  assert.strictEqual(paths.resolveInput({ path: path.join(dir, "plate.0001.exr") }, "linux").mixed, true);
});

test("a lone still stays a file unless the host says it is a sequence", () => {
  const dir = tmpDir("still-");
  fs.writeFileSync(path.join(dir, "frame_0001.png"), "");
  assert.deepStrictEqual(paths.resolveInput({ path: path.join(dir, "frame_0001.png") }, "linux"), { input: path.join(dir, "frame_0001.png"), sequence: false });
  assert.strictEqual(paths.resolveInput({ path: path.join(dir, "frame_0001.png"), isSequence: true }, "linux").input, dir);
  fs.writeFileSync(path.join(dir, "frame_0002.png"), "");
  assert.strictEqual(paths.resolveInput({ path: path.join(dir, "frame_0001.png"), isSequence: false }, "linux").sequence, false);
});

test("Windows sequence paths use Windows separators", () => {
  const fake = { readdirSync: () => ["p_001.tif", "p_002.tif"] };
  assert.deepStrictEqual(paths.resolveInput({ path: "E:\\plates\\p_001.tif" }, "win32", fake), { input: "E:\\plates", sequence: true, mixed: false });
});
