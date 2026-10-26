"use strict";

const test = require("node:test");
const assert = require("node:assert");
const { lib } = require("./helpers");
const { hostContext, evalScript } = require("./jsx-harness");
const { makeAe } = require("./ae-mock");
const host = lib("host");

function setup() {
  const ae = makeAe();
  const ctx = hostContext(ae.globals, "common.jsx", "aeft.jsx");
  const bridge = host.createBridge(evalScript(ctx));
  const comp = ae.add(new ae.CompItem("Main"));
  const plate = ae.add(new ae.FootageItem(new ae.File("C:\\Shoot\\green plate.mov"), { fps: 23.976 }));
  const bg = ae.add(new ae.FootageItem(new ae.File("C:\\Shoot\\bg.png"), { still: true }));
  const bgLayer = new ae.AVLayer(comp, bg);
  const src = new ae.AVLayer(comp, plate, "Actor");
  Object.assign(src, { startTime: 2, inPoint: 3, outPoint: 6.5, stretch: 100 });
  src.effects = ["Keylight", "Curves"];
  comp.list.push(src, bgLayer);
  return { ae, bridge, comp, plate, src, bgLayer };
}

test("errors when nothing usable is selected", async () => {
  const { ae, bridge, comp, src, bgLayer } = setup();
  await assert.rejects(bridge.call("keymaster_getSelection", {}), (e) => e.message_key === "adobe.error.no_comp");
  ae.project.activeItem = comp;
  await assert.rejects(bridge.call("keymaster_getSelection", {}), (e) => e.message_key === "adobe.error.no_selection");
  comp.selectedLayers = [src, bgLayer];
  await assert.rejects(bridge.call("keymaster_getSelection", {}), (e) => e.message_key === "adobe.error.multiple");
  comp.selectedLayers = [new ae.TextLayer()];
  await assert.rejects(bridge.call("keymaster_getSelection", {}), (e) => e.message_key === "adobe.error.no_footage");
  comp.selectedLayers = [src];
  src.source.footageMissing = true;
  await assert.rejects(bridge.call("keymaster_getSelection", {}), (e) => e.message_key === "adobe.error.source_missing");
});

test("reads the selected footage layer", async () => {
  const { ae, bridge, comp, plate, src } = setup();
  ae.project.activeItem = comp;
  comp.selectedLayers = [src];
  const res = await bridge.call("keymaster_getSelection", {});
  assert.deepStrictEqual(res, {
    ok: true,
    host: "AEFT",
    source: {
      path: "C:\\Shoot\\green plate.mov",
      name: "Actor",
      isSequence: false,
      fps: 23.976,
      duration: 5,
      startTime: 2,
      inPoint: 3,
      outPoint: 6.5,
      stretch: 100,
      timeRemap: false,
      ref: { compId: comp.id, layerIndex: 1, layerName: "Actor", sourceId: plate.id }
    }
  });
});

test("imports an EXR sequence and places the cutout above the source, aligned", async () => {
  const { ae, bridge, comp, src, bgLayer } = setup();
  ae.project.activeItem = comp;
  comp.selectedLayers = [src];
  const sel = await bridge.call("keymaster_getSelection", {});
  comp.list.unshift(new ae.AVLayer(comp, bgLayer.source, "Moved in front"));
  const res = await bridge.call("keymaster_importResult", {
    ref: sel.source.ref,
    fps: 23.976,
    disableSource: true,
    folder: "Keymaster",
    outputs: [
      { kind: "alpha", type: "image_sequence", path: "C:\\o\\alpha", firstFile: "C:\\o\\alpha\\alpha_000000.exr" },
      { kind: "cutout", type: "image_sequence", path: "C:\\o\\cutout", firstFile: "C:\\o\\cutout\\cutout_000000.exr" }
    ]
  });
  assert.strictEqual(res.ok, true);
  assert.deepStrictEqual(ae.imports, [
    { path: "C:\\o\\alpha\\alpha_000000.exr", sequence: true, importAs: 1 },
    { path: "C:\\o\\cutout\\cutout_000000.exr", sequence: true, importAs: 1 }
  ]);
  const folder = ae.items.find((i) => i.name === "Keymaster");
  const imported = ae.items.filter((i) => i.parentFolder === folder);
  assert.strictEqual(imported.length, 2);
  for (const item of imported) assert.strictEqual(item.mainSource.conformFrameRate, 23.976);
  const cutoutItem = imported.find((i) => i.name === "cutout_000000.exr");
  assert.strictEqual(cutoutItem.mainSource.alphaMode, ae.AlphaMode.STRAIGHT);
  const placed = comp.layer(res.placed.index);
  assert.strictEqual(placed.source, cutoutItem);
  assert.strictEqual(comp.layer(res.placed.index + 1), src);
  assert.deepStrictEqual([placed.startTime, placed.inPoint, placed.outPoint, placed.stretch], [2, 3, 6.5, 100]);
  assert.deepStrictEqual(placed.effects, []);
  assert.deepStrictEqual(src.effects, ["Keylight", "Curves"]);
  assert.strictEqual(placed.enabled, true);
  assert.strictEqual(src.enabled, false);
  assert.deepStrictEqual(ae.undo, ["begin Keymaster", "end"]);
});

test("reuses the Keymaster folder, keeps the source on when asked, imports video as one file", async () => {
  const { ae, bridge, comp, src } = setup();
  ae.project.activeItem = comp;
  comp.selectedLayers = [src];
  const existing = ae.project.items.addFolder("Keymaster");
  const sel = await bridge.call("keymaster_getSelection", {});
  const res = await bridge.call("keymaster_importResult", {
    ref: sel.source.ref,
    fps: 24,
    disableSource: false,
    folder: "Keymaster",
    outputs: [{ kind: "cutout", type: "video", path: "C:\\o\\a_cutout.mov", firstFile: "C:\\o\\a_cutout.mov" }]
  });
  assert.ok(res.placed);
  assert.deepStrictEqual(ae.imports, [{ path: "C:\\o\\a_cutout.mov", sequence: false, importAs: 1 }]);
  assert.strictEqual(ae.items.filter((i) => i.name === "Keymaster").length, 1);
  const movie = ae.items.find((i) => i.name === "a_cutout.mov");
  assert.strictEqual(movie.parentFolder, existing);
  assert.strictEqual(movie.mainSource.conformFrameRate, 0);
  assert.strictEqual(src.enabled, true);
});

test("without a cutout output nothing is placed", async () => {
  const { ae, bridge, comp, src } = setup();
  ae.project.activeItem = comp;
  comp.selectedLayers = [src];
  const sel = await bridge.call("keymaster_getSelection", {});
  const before = comp.numLayers;
  const res = await bridge.call("keymaster_importResult", {
    ref: sel.source.ref, fps: 24, disableSource: true, folder: "Keymaster",
    outputs: [{ kind: "alpha", type: "video", path: "C:\\o\\a.mp4", firstFile: "C:\\o\\a.mp4" }]
  });
  assert.strictEqual(res.placed, null);
  assert.strictEqual(comp.numLayers, before);
  assert.strictEqual(src.enabled, true);
});

test("a deleted source layer is reported", async () => {
  const { ae, bridge, comp, src } = setup();
  ae.project.activeItem = comp;
  comp.selectedLayers = [src];
  const sel = await bridge.call("keymaster_getSelection", {});
  comp.list.splice(0, 1);
  await assert.rejects(bridge.call("keymaster_importResult", { ref: sel.source.ref, fps: 24, outputs: [] }),
    (e) => e.message_key === "adobe.error.source_missing");
});
