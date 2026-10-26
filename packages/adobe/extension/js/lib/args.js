"use strict";

var errors = require("./errors");

var OUTPUT_KINDS = ["alpha", "fg", "cutout", "checker"];
var FORMATS = ["exr", "video"];
var CMD_META = /([()\][%!^"`<>&|;, *?])/g;

function isAbsolutePath(p, platform) {
  if (typeof p !== "string" || !p) return false;
  if (platform === "win32") return /^[A-Za-z]:[\\/]/.test(p) || /^\\\\[^\\]+\\[^\\]+/.test(p);
  return p.charAt(0) === "/";
}

function requireAbsolute(p, platform) {
  if (!isAbsolutePath(p, platform)) {
    throw errors.KeymasterError({ message_key: "adobe.error.bad_path", params: { path: String(p || "") }, detail: "not absolute: " + p });
  }
  return p;
}

function unit(value, fallback) {
  var n = typeof value === "string" ? parseFloat(value.replace(",", ".")) : Number(value);
  if (!isFinite(n)) n = fallback;
  n = Math.min(1, Math.max(0, n));
  return String(Math.round(n * 10000) / 10000);
}

function pickOutputs(outputs) {
  var list = Array.isArray(outputs) ? outputs : [];
  var picked = OUTPUT_KINDS.filter(function (kind) { return list.indexOf(kind) !== -1; });
  if (!picked.length) throw errors.KeymasterError({ message_key: "adobe.error.no_outputs", detail: "no outputs selected" });
  return picked;
}

function buildKeyArgs(options, platform) {
  var o = options || {};
  var args = ["-m", "keymaster", "key",
    "--input", requireAbsolute(o.input, platform),
    "--output-dir", requireAbsolute(o.outputDir, platform)];
  if (o.hintFirstFrame) args.push("--hint-first-frame", requireAbsolute(o.hintFirstFrame, platform));
  if (o.hintFirstFrame || o.hintQuality !== undefined) args.push("--hint-quality", unit(o.hintQuality, 0.95));
  args.push("--despill", unit(o.despill, 0.5));
  args.push("--format", FORMATS.indexOf(o.format) !== -1 ? o.format : "exr");
  args.push("--outputs");
  Array.prototype.push.apply(args, pickOutputs(o.outputs));
  if (o.frames && Math.floor(o.frames) > 0) args.push("--frames", String(Math.floor(o.frames)));
  if (o.lowVram) args.push("--low-vram");
  args.push("--json");
  return args;
}

function buildDoctorArgs() {
  return ["-m", "keymaster", "doctor", "--json"];
}

function quoteWindowsArg(arg) {
  var s = String(arg);
  if (s === "") return '""';
  if (!/[ \t\n\v"]/.test(s)) return s;
  var out = '"';
  var slashes = 0;
  for (var i = 0; i < s.length; i++) {
    var c = s.charAt(i);
    if (c === "\\") {
      slashes++;
      continue;
    }
    if (c === '"') {
      out += new Array(slashes * 2 + 2).join("\\") + '"';
    } else {
      out += new Array(slashes + 1).join("\\") + c;
    }
    slashes = 0;
  }
  out += new Array(slashes * 2 + 1).join("\\") + '"';
  return out;
}

function windowsCommandLine(argv) {
  return argv.map(quoteWindowsArg).join(" ");
}

function posixQuote(arg) {
  var s = String(arg);
  if (s !== "" && /^[A-Za-z0-9_\-+=.,/:@%]+$/.test(s)) return s;
  return "'" + s.replace(/'/g, "'\\''") + "'";
}

function displayCommand(argv, platform) {
  return platform === "win32" ? windowsCommandLine(argv) : argv.map(posixQuote).join(" ");
}

function cmdEscapeArgument(arg, doubleEscape) {
  var s = String(arg);
  s = s.replace(/(\\*)"/g, '$1$1\\"');
  s = s.replace(/(\\*)$/, "$1$1");
  s = '"' + s + '"';
  s = s.replace(CMD_META, "^$1");
  if (doubleEscape) s = s.replace(CMD_META, "^$1");
  return s;
}

function cmdEscapeCommand(cmd) {
  return String(cmd).replace(CMD_META, "^$1");
}

function isBatchFile(command) {
  return /\.(bat|cmd)$/i.test(command);
}

function spawnSpec(command, args, platform, env) {
  if (platform === "win32" && isBatchFile(command)) {
    var line = [cmdEscapeCommand(command)].concat(args.map(function (a) { return cmdEscapeArgument(a, true); })).join(" ");
    return {
      command: (env && (env.ComSpec || env.COMSPEC)) || "cmd.exe",
      args: ["/d", "/s", "/c", '"' + line + '"'],
      windowsVerbatimArguments: true
    };
  }
  return { command: command, args: args.slice(), windowsVerbatimArguments: false };
}

module.exports = {
  OUTPUT_KINDS: OUTPUT_KINDS,
  FORMATS: FORMATS,
  isAbsolutePath: isAbsolutePath,
  buildKeyArgs: buildKeyArgs,
  buildDoctorArgs: buildDoctorArgs,
  quoteWindowsArg: quoteWindowsArg,
  windowsCommandLine: windowsCommandLine,
  displayCommand: displayCommand,
  cmdEscapeArgument: cmdEscapeArgument,
  spawnSpec: spawnSpec
};
