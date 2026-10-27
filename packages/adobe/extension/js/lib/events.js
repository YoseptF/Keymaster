"use strict";

var StringDecoder = require("string_decoder").StringDecoder;

function LineSplitter() {
  this.decoder = new StringDecoder("utf8");
  this.buffer = "";
}

LineSplitter.prototype.push = function (chunk) {
  this.buffer += typeof chunk === "string" ? chunk : this.decoder.write(chunk);
  var parts = this.buffer.split("\n");
  this.buffer = parts.pop();
  return parts.map(stripCr).filter(function (line) { return line.trim() !== ""; });
};

LineSplitter.prototype.flush = function () {
  var rest = this.buffer + this.decoder.end();
  this.buffer = "";
  rest = stripCr(rest);
  return rest.trim() === "" ? [] : [rest];
};

function stripCr(line) {
  return line.charAt(line.length - 1) === "\r" ? line.slice(0, -1) : line;
}

function parseEvent(line) {
  var text = String(line).replace(/^﻿/, "").trim();
  var data;
  try {
    data = JSON.parse(text);
  } catch (e) {
    return { event: "invalid", raw: line };
  }
  if (!data || typeof data !== "object" || Array.isArray(data) || typeof data.event !== "string") {
    return { event: "invalid", raw: line };
  }
  return data;
}

function EventStream(onEvent) {
  this.splitter = new LineSplitter();
  this.onEvent = onEvent;
}

EventStream.prototype.write = function (chunk) {
  var lines = this.splitter.push(chunk);
  for (var i = 0; i < lines.length; i++) this.onEvent(parseEvent(lines[i]));
};

EventStream.prototype.end = function () {
  var lines = this.splitter.flush();
  for (var i = 0; i < lines.length; i++) this.onEvent(parseEvent(lines[i]));
};

module.exports = { LineSplitter: LineSplitter, parseEvent: parseEvent, EventStream: EventStream };
