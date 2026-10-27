"use strict";

const test = require("node:test");
const assert = require("node:assert");
const { lib } = require("./helpers");
const { hostContext, evalScript, collection } = require("./jsx-harness");
const host = lib("host");

const TPS = 254016000000;

function time(seconds) {
  return { seconds: seconds, ticks: String(Math.round(seconds * TPS)) };
}

function makePpro(options) {
  const opts = options || {};
  let nextNode = 1;
  const ProjectItemType = { CLIP: 1, BIN: 2, ROOT: 3, FILE: 4 };
  const log = [];

  function projectItem(name, media, extra) {
    const item = Object.assign({
      nodeId: "pi" + nextNode++,
      name: name,
      type: ProjectItemType.CLIP,
      media: media,
      inSec: null,
      outSec: null,
      interp: { frameRate: 25, alphaUsage: 0 },
      overrideFps: 0,
      sequence: false,
      offline: false,
      isSequence() { return this.sequence; },
      isOffline() { return this.offline; },
      getMediaPath() { return this.media; },
      getFootageInterpretation() { return Object.assign({}, this.interp); },
      setFootageInterpretation(i) { this.interp = Object.assign({}, i); return true; },
      setOverrideFrameRate(f) { this.overrideFps = f; return 0; },
      setInPoint(sec, type) { assert.strictEqual(type, 4); assert.strictEqual(typeof sec, "number"); this.inSec = sec; return 0; },
      setOutPoint(sec, type) { assert.strictEqual(type, 4); this.outSec = sec; return 0; },
      clearInPoint() { log.push("clearIn " + this.name); this.inSec = null; },
      clearOutPoint() { log.push("clearOut " + this.name); this.outSec = null; }
    }, extra || {});
    return item;
  }

  function trackItem(item, start, inPoint, outPoint) {
    return {
      nodeId: "ti" + nextNode++,
      name: item.name,
      mediaType: "Video",
      projectItem: item,
      start: time(start),
      end: time(start + (outPoint - inPoint)),
      inPoint: time(inPoint),
      outPoint: time(outPoint),
      disabled: false
    };
  }

  function track(clips) {
    const list = clips.slice();
    const t = {
      clips: collection(list, "numItems"),
      overwriteClip(item, seconds) {
        assert.strictEqual(typeof seconds, "number");
        log.push("overwrite " + item.name + " @" + seconds.toFixed(3));
        const inS = item.inSec === null ? 0 : item.inSec;
        const outS = item.outSec === null ? 10 : item.outSec;
        list.push(trackItem(item, seconds, inS, outS));
        t.clips._sync();
        return true;
      }
    };
    return t;
  }

  const plate = projectItem("plate.mov", "C:\\Shoot\\plate.mov");
  const other = projectItem("other.mov", "C:\\Shoot\\other.mov");
  const source = trackItem(plate, 10, 2, 6);
  const tracksList = [track([source]), track(opts.blockAbove ? [trackItem(other, 12, 0, 1)] : [])];
  const videoTracks = collection(tracksList, "numTracks");
  const seq = {
    sequenceID: "seq-1",
    name: "Edit",
    timebase: String(TPS / 25),
    videoTracks: videoTracks,
    selection: [],
    getSelection() { return this.selection; }
  };
  const rootChildren = [];
  const root = {
    type: ProjectItemType.ROOT,
    children: collection(rootChildren, "numItems"),
    createBin(name) {
      const binChildren = [];
      const bin = { name: name, type: ProjectItemType.BIN, nodeId: "bin" + nextNode++, children: collection(binChildren, "numItems"), list: binChildren };
      rootChildren.push(bin);
      root.children._sync();
      log.push("createBin " + name);
      return bin;
    }
  };
  const imports = [];
  const project = {
    activeSequence: seq,
    rootItem: root,
    sequences: collection([seq], "numSequences"),
    importFiles(paths, suppress, bin, numbered) {
      imports.push({ paths: Array.from(paths), suppress: suppress, bin: bin.name, numbered: numbered });
      if (opts.importFails) return false;
      const p = paths[0];
      bin.list.push(projectItem(p.split("\\").pop(), p.replace(/\\/g, "/")));
      bin.children._sync();
      return true;
    }
  };
  const qeSeq = {
    addTracks(numVideo, index, numAudio) {
      log.push("addTracks " + numVideo + " " + index + " " + numAudio);
      if (!opts.noQe) {
        tracksList.push(track([]));
        videoTracks._sync();
      }
    }
  };
  const app = {
    project: project,
    version: "26.0",
    enableQE() { log.push("enableQE"); }
  };
  const globals = { app, ProjectItemType, qe: { project: { getActiveSequence: () => qeSeq } } };
  return { globals, seq, source, plate, imports, log, tracksList, root, projectItem, trackItem };
}

function setup(opts) {
  const pp = makePpro(opts);
  const ctx = hostContext(pp.globals, "common.jsx", "ppro.jsx");
  return Object.assign(pp, { bridge: host.createBridge(evalScript(ctx)) });
}

test("selection errors", async () => {
  const pp = setup();
  pp.globals.app.project.activeSequence = null;
  await assert.rejects(pp.bridge.call("keymaster_getSelection", {}), (e) => e.message_key === "adobe.error.no_sequence");
  pp.globals.app.project.activeSequence = pp.seq;
  await assert.rejects(pp.bridge.call("keymaster_getSelection", {}), (e) => e.message_key === "adobe.error.no_selection");
  pp.seq.selection = [Object.assign({}, pp.source, { mediaType: "Audio" })];
  await assert.rejects(pp.bridge.call("keymaster_getSelection", {}), (e) => e.message_key === "adobe.error.no_selection");
  pp.seq.selection = [pp.source, pp.trackItem(pp.plate, 0, 0, 1)];
  await assert.rejects(pp.bridge.call("keymaster_getSelection", {}), (e) => e.message_key === "adobe.error.multiple");
  const nested = pp.trackItem(pp.projectItem("Nest", "", { sequence: true }), 0, 0, 1);
  pp.seq.selection = [nested];
  await assert.rejects(pp.bridge.call("keymaster_getSelection", {}), (e) => e.message_key === "adobe.error.no_footage");
  const offline = pp.trackItem(pp.projectItem("gone.mov", "C:\\gone.mov", { offline: true }), 0, 0, 1);
  pp.seq.selection = [offline];
  await assert.rejects(pp.bridge.call("keymaster_getSelection", {}), (e) => e.message_key === "adobe.error.source_missing");
});

test("reads the selected clip with its timing", async () => {
  const pp = setup();
  pp.seq.selection = [pp.source, Object.assign({}, pp.source, { mediaType: "Audio" })];
  const res = await pp.bridge.call("keymaster_getSelection", {});
  assert.strictEqual(res.host, "PPRO");
  assert.strictEqual(res.source.path, "C:\\Shoot\\plate.mov");
  assert.strictEqual(res.source.fps, 25);
  assert.deepStrictEqual([res.source.start, res.source.end, res.source.inPoint, res.source.outPoint], [10, 14, 2, 6]);
  assert.deepStrictEqual(res.source.ref, {
    sequenceId: "seq-1",
    nodeId: pp.source.nodeId,
    trackIndex: 0,
    startTicks: time(10).ticks,
    endTicks: time(14).ticks,
    inTicks: time(2).ticks,
    outTicks: time(6).ticks
  });
});

test("imports into a Keymaster bin and overwrites onto the free track above", async () => {
  const pp = setup();
  pp.seq.selection = [pp.source];
  const sel = await pp.bridge.call("keymaster_getSelection", {});
  const res = await pp.bridge.call("keymaster_importResult", {
    ref: sel.source.ref,
    fps: 25,
    disableSource: true,
    folder: "Keymaster",
    outputs: [
      { kind: "cutout", type: "video", path: "C:\\o\\plate_cutout.mov", firstFile: "C:\\o\\plate_cutout.mov" },
      { kind: "alpha", type: "image_sequence", path: "C:\\o\\alpha", firstFile: "C:\\o\\alpha\\alpha_000000.exr" }
    ]
  });
  assert.deepStrictEqual(res, { ok: true, imported: [{ kind: "cutout", name: "plate_cutout.mov" }, { kind: "alpha", name: "alpha_000000.exr" }], placed: { track: 1, verified: true } });
  assert.deepStrictEqual(pp.imports, [
    { paths: ["C:\\o\\plate_cutout.mov"], suppress: true, bin: "Keymaster", numbered: false },
    { paths: ["C:\\o\\alpha\\alpha_000000.exr"], suppress: true, bin: "Keymaster", numbered: true }
  ]);
  const bin = pp.root.children[0];
  assert.strictEqual(bin.list[1].overrideFps, 25);
  assert.strictEqual(bin.list[0].overrideFps, 0);
  const placed = pp.tracksList[1].clips[0];
  assert.strictEqual(placed.projectItem, bin.list[0]);
  assert.strictEqual(placed.start.seconds, 10);
  assert.strictEqual(placed.inPoint.seconds, 2);
  assert.strictEqual(placed.outPoint.seconds, 6);
  assert.strictEqual(pp.tracksList[0].clips.numItems, 1);
  assert.strictEqual(pp.source.disabled, true);
  assert.deepStrictEqual(pp.log, ["createBin Keymaster", "overwrite plate_cutout.mov @10.000", "clearIn plate_cutout.mov", "clearOut plate_cutout.mov"]);
});

test("an image sequence cutout gets straight alpha and the reused bin", async () => {
  const pp = setup();
  pp.root.createBin("Keymaster");
  pp.log.length = 0;
  pp.seq.selection = [pp.source];
  const sel = await pp.bridge.call("keymaster_getSelection", {});
  await pp.bridge.call("keymaster_importResult", {
    ref: sel.source.ref, fps: 23.976, disableSource: false, folder: "Keymaster",
    outputs: [{ kind: "cutout", type: "image_sequence", path: "C:\\o\\c", firstFile: "C:\\o\\c\\cutout_000000.exr" }]
  });
  const item = pp.root.children[0].list[0];
  assert.strictEqual(item.interp.alphaUsage, 1);
  assert.strictEqual(item.overrideFps, 23.976);
  assert.strictEqual(pp.source.disabled, false);
  assert.ok(!pp.log.includes("createBin Keymaster"));
});

test("an occupied track above means a new track is added, nothing is overwritten", async () => {
  const pp = setup({ blockAbove: true });
  pp.seq.selection = [pp.source];
  const sel = await pp.bridge.call("keymaster_getSelection", {});
  const res = await pp.bridge.call("keymaster_importResult", {
    ref: sel.source.ref, fps: 25, disableSource: true, folder: "Keymaster",
    outputs: [{ kind: "cutout", type: "video", path: "C:\\o\\x.mov", firstFile: "C:\\o\\x.mov" }]
  });
  assert.deepStrictEqual(res.placed, { track: 2, verified: true });
  assert.strictEqual(pp.tracksList[1].clips.numItems, 1);
  assert.ok(pp.log.includes("addTracks 1 2 0"));
});

test("no way to add a track is reported and the source stays on", async () => {
  const pp = setup({ blockAbove: true, noQe: true });
  pp.seq.selection = [pp.source];
  const sel = await pp.bridge.call("keymaster_getSelection", {});
  await assert.rejects(pp.bridge.call("keymaster_importResult", {
    ref: sel.source.ref, fps: 25, disableSource: true, folder: "Keymaster",
    outputs: [{ kind: "cutout", type: "video", path: "C:\\o\\x.mov", firstFile: "C:\\o\\x.mov" }]
  }), (e) => e.message_key === "adobe.error.no_track");
  assert.strictEqual(pp.source.disabled, false);
});

test("a failed import is reported", async () => {
  const pp = setup({ importFails: true });
  pp.seq.selection = [pp.source];
  const sel = await pp.bridge.call("keymaster_getSelection", {});
  await assert.rejects(pp.bridge.call("keymaster_importResult", {
    ref: sel.source.ref, fps: 25, folder: "Keymaster",
    outputs: [{ kind: "cutout", type: "video", path: "C:\\o\\x.mov", firstFile: "C:\\o\\x.mov" }]
  }), (e) => e.message_key === "adobe.error.import_failed");
});
