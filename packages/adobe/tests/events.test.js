"use strict";

const test = require("node:test");
const assert = require("node:assert");
const { lib } = require("./helpers");
const events = lib("events");

test("lines split across chunks are joined", () => {
  const s = new events.LineSplitter();
  assert.deepStrictEqual(s.push('{"event":"st'), []);
  assert.deepStrictEqual(s.push('art"}\n{"event":"progress","fraction":0.1}\n{"ev'), ['{"event":"start"}', '{"event":"progress","fraction":0.1}']);
  assert.deepStrictEqual(s.push('ent":"done"}'), []);
  assert.deepStrictEqual(s.flush(), ['{"event":"done"}']);
  assert.deepStrictEqual(s.flush(), []);
});

test("CRLF and blank lines are handled", () => {
  const s = new events.LineSplitter();
  assert.deepStrictEqual(s.push(Buffer.from('{"event":"a"}\r\n\r\n{"event":"b"}\r\n')), ['{"event":"a"}', '{"event":"b"}']);
});

test("a multi-byte character split between chunks survives", () => {
  const s = new events.LineSplitter();
  const bytes = Buffer.from('{"event":"error","detail":"Núñez ✓"}\n', "utf8");
  const cut = bytes.indexOf(Buffer.from("ñ")) + 1;
  assert.deepStrictEqual(s.push(bytes.subarray(0, cut)), []);
  const lines = s.push(bytes.subarray(cut));
  assert.strictEqual(events.parseEvent(lines[0]).detail, "Núñez ✓");
});

test("every byte as its own chunk still yields whole events", () => {
  const text = '{"event":"start","input":"C:\\\\clips\\\\é.mov"}\n{"event":"done","outputs":[]}\n';
  const seen = [];
  const stream = new events.EventStream((e) => seen.push(e));
  for (const b of Buffer.from(text, "utf8")) stream.write(Buffer.from([b]));
  stream.end();
  assert.deepStrictEqual(seen.map((e) => e.event), ["start", "done"]);
  assert.strictEqual(seen[0].input, "C:\\clips\\é.mov");
});

test("non-event lines are marked invalid instead of throwing", () => {
  assert.deepStrictEqual(events.parseEvent("Traceback (most recent call last):"), { event: "invalid", raw: "Traceback (most recent call last):" });
  assert.strictEqual(events.parseEvent("[1,2]").event, "invalid");
  assert.strictEqual(events.parseEvent('{"no":"event"}').event, "invalid");
  assert.strictEqual(events.parseEvent('\uFEFF{"event":"start"}').event, "start");
});

test("a final line without newline is delivered on end", () => {
  const seen = [];
  const stream = new events.EventStream((e) => seen.push(e));
  stream.write('{"event":"error","message_key":"core.error.no_gpu"}');
  assert.strictEqual(seen.length, 0);
  stream.end();
  assert.strictEqual(seen[0].message_key, "core.error.no_gpu");
});
