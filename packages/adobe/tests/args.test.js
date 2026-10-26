"use strict";

const test = require("node:test");
const assert = require("node:assert");
const { lib } = require("./helpers");
const args = lib("args");

test("key arguments on Windows keep paths intact", () => {
  const got = args.buildKeyArgs({
    input: "C:\\Footage\\Green Screen\\take 01.mov",
    outputDir: "C:\\Footage\\Green Screen\\Keymaster\\take 01_20260101-120000",
    hintFirstFrame: "\\\\nas\\share\\hint.png",
    hintQuality: 0.9,
    despill: "0,25",
    format: "video",
    outputs: ["fg", "cutout", "fg", "bogus"],
    lowVram: true
  }, "win32");
  assert.deepStrictEqual(got, [
    "-m", "keymaster", "key",
    "--input", "C:\\Footage\\Green Screen\\take 01.mov",
    "--output-dir", "C:\\Footage\\Green Screen\\Keymaster\\take 01_20260101-120000",
    "--hint-first-frame", "\\\\nas\\share\\hint.png",
    "--hint-quality", "0.9",
    "--despill", "0.25",
    "--format", "video",
    "--outputs", "fg", "cutout",
    "--low-vram",
    "--json"
  ]);
});

test("key arguments on Linux with defaults", () => {
  const got = args.buildKeyArgs({ input: "/m/a.mov", outputDir: "/m/out", outputs: ["cutout"] }, "linux");
  assert.deepStrictEqual(got, ["-m", "keymaster", "key", "--input", "/m/a.mov", "--output-dir", "/m/out",
    "--despill", "0.5", "--format", "exr", "--outputs", "cutout", "--json"]);
});

test("numbers are clamped and locale-proof", () => {
  const got = args.buildKeyArgs({ input: "/a", outputDir: "/b", outputs: ["alpha"], despill: 7, hintQuality: -1, frames: 12.7 }, "linux");
  assert.deepStrictEqual(got.slice(7), ["--hint-quality", "0", "--despill", "1", "--format", "exr", "--outputs", "alpha", "--frames", "12", "--json"]);
  const nan = args.buildKeyArgs({ input: "/a", outputDir: "/b", outputs: ["alpha"], despill: "abc" }, "linux");
  assert.strictEqual(nan[nan.indexOf("--despill") + 1], "0.5");
});

test("relative paths and empty outputs are refused with translatable errors", () => {
  assert.throws(() => args.buildKeyArgs({ input: "clip.mov", outputDir: "C:\\o", outputs: ["cutout"] }, "win32"),
    (e) => e.message_key === "adobe.error.bad_path" && e.params.path === "clip.mov");
  assert.throws(() => args.buildKeyArgs({ input: "/a", outputDir: "/b", outputs: [] }, "linux"),
    (e) => e.message_key === "adobe.error.no_outputs");
  assert.ok(!args.isAbsolutePath("/unix/on/windows", "win32"));
  assert.ok(args.isAbsolutePath("D:/forward/slashes", "win32"));
  assert.ok(!args.isAbsolutePath("C:relative", "win32"));
});

test("Windows argument quoting follows the C runtime rules", () => {
  const q = args.quoteWindowsArg;
  assert.strictEqual(q("plain"), "plain");
  assert.strictEqual(q(""), '""');
  assert.strictEqual(q("C:\\Program Files\\Python\\python.exe"), '"C:\\Program Files\\Python\\python.exe"');
  assert.strictEqual(q("C:\\dir with space\\"), '"C:\\dir with space\\\\"');
  assert.strictEqual(q('say "hi"'), '"say \\"hi\\""');
  assert.strictEqual(q('a\\"b c'), '"a\\\\\\"b c"');
  assert.strictEqual(q("C:\\no\\spaces\\"), "C:\\no\\spaces\\");
  assert.strictEqual(q("C:\\Usuarios\\José Núñez\\clip.mov"), '"C:\\Usuarios\\José Núñez\\clip.mov"');
  assert.strictEqual(args.windowsCommandLine(["a b", "c"]), '"a b" c');
});

test("display command quotes for each platform", () => {
  assert.strictEqual(args.displayCommand(["/usr/bin/python3", "-m", "keymaster", "--input", "/a b/it's.mov"], "linux"),
    "/usr/bin/python3 -m keymaster --input '/a b/it'\\''s.mov'");
  assert.strictEqual(args.displayCommand(["C:\\Py 3\\python.exe", "-m"], "win32"), '"C:\\Py 3\\python.exe" -m');
});

test("exe interpreters spawn directly, batch shims go through cmd with escaping", () => {
  const direct = args.spawnSpec("C:\\core\\.venv\\Scripts\\python.exe", ["-m", "keymaster"], "win32", {});
  assert.deepStrictEqual(direct, { command: "C:\\core\\.venv\\Scripts\\python.exe", args: ["-m", "keymaster"], windowsVerbatimArguments: false });
  const shim = args.spawnSpec("C:\\Users\\A B\\.pyenv\\shims\\python.bat", ["--input", "C:\\a & b\\x.mov"], "win32", { ComSpec: "C:\\Windows\\system32\\cmd.exe" });
  assert.strictEqual(shim.command, "C:\\Windows\\system32\\cmd.exe");
  assert.deepStrictEqual(shim.args.slice(0, 3), ["/d", "/s", "/c"]);
  assert.ok(shim.windowsVerbatimArguments);
  assert.strictEqual(shim.args[3],
    '"C:\\Users\\A^ B\\.pyenv\\shims\\python.bat ^^^"--input^^^" ^^^"C:\\a^^^ ^^^&^^^ b\\x.mov^^^""');
  const linux = args.spawnSpec("/x/python.bat", ["a"], "linux", {});
  assert.strictEqual(linux.command, "/x/python.bat");
});

test("doctor arguments", () => {
  assert.deepStrictEqual(args.buildDoctorArgs(), ["-m", "keymaster", "doctor", "--json"]);
});
