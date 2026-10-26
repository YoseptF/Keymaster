"use strict";

var nodePath = require("path");
var fs = require("fs");

var IMAGE_EXT = ["exr", "png", "jpg", "jpeg", "tif", "tiff", "dpx", "bmp", "tga", "webp"];

function pathApi(platform) {
  return platform === "win32" ? nodePath.win32 : nodePath.posix;
}

function pad(n, width) {
  var s = String(n);
  while (s.length < width) s = "0" + s;
  return s;
}

function stamp(date) {
  return date.getFullYear() + pad(date.getMonth() + 1, 2) + pad(date.getDate(), 2) + "-" +
    pad(date.getHours(), 2) + pad(date.getMinutes(), 2) + pad(date.getSeconds(), 2);
}

function safeName(name) {
  var cleaned = String(name).replace(/[<>:"\/\\|?*\x00-\x1f]/g, "_").replace(/[. ]+$/, "");
  return cleaned || "clip";
}

function defaultOutputDir(sourcePath, outputRoot, date, platform) {
  var p = pathApi(platform);
  var parsed = p.parse(sourcePath);
  var stem = parsed.ext ? parsed.name : parsed.base;
  var root = outputRoot || p.join(parsed.dir, "Keymaster");
  return p.join(root, safeName(stem) + "_" + stamp(date));
}

function expandPattern(pattern, frame) {
  return String(pattern).replace(/%(0?)(\d*)d/g, function (whole, zero, width) {
    var w = width ? parseInt(width, 10) : 0;
    var n = Math.max(0, Math.floor(frame));
    return zero && w ? pad(n, w) : String(n);
  });
}

function firstFrameFile(output) {
  if (!output || output.type !== "image_sequence" || !output.pattern) return output ? output.path : "";
  return expandPattern(output.pattern, output.first_frame || 0);
}

function extension(file) {
  var m = /\.([^.\\\/]+)$/.exec(file);
  return m ? m[1].toLowerCase() : "";
}

function isImageFile(file) {
  return IMAGE_EXT.indexOf(extension(file)) !== -1;
}

function sequenceStem(name) {
  var m = /^(.*?)(\d+)(\.[^.]+)$/.exec(name);
  return m ? { prefix: m[1], digits: m[2], ext: m[3].toLowerCase() } : null;
}

function resolveInput(source, platform, fsApi) {
  var f = fsApi || fs;
  var p = pathApi(platform);
  var file = source.path;
  if (!isImageFile(file)) return { input: file, sequence: false };
  if (source.isSequence === false) return { input: file, sequence: false };
  var dir = p.dirname(file);
  var me = sequenceStem(p.basename(file));
  if (!me) return { input: file, sequence: false };
  var names;
  try {
    names = f.readdirSync(dir);
  } catch (e) {
    return { input: file, sequence: false };
  }
  var siblings = 0;
  var others = 0;
  names.forEach(function (name) {
    if (!isImageFile(name)) return;
    var s = sequenceStem(name);
    if (s && s.prefix === me.prefix && s.ext === me.ext) siblings++;
    else others++;
  });
  if (siblings < 2 && source.isSequence !== true) return { input: file, sequence: false };
  return { input: dir, sequence: true, mixed: others > 0 };
}

module.exports = {
  IMAGE_EXT: IMAGE_EXT,
  stamp: stamp,
  safeName: safeName,
  defaultOutputDir: defaultOutputDir,
  expandPattern: expandPattern,
  firstFrameFile: firstFrameFile,
  isImageFile: isImageFile,
  resolveInput: resolveInput
};
