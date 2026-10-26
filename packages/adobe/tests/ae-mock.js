"use strict";

const assert = require("node:assert");

function makeAe() {
  let nextId = 1;
  class File {
    constructor(p) {
      this.fsName = p;
      this.name = p.split(/[\\/]/).pop();
    }
  }
  class FileSource {
    constructor(file, isStill) {
      this.file = file;
      this.isStill = isStill;
      this.conformFrameRate = 0;
      this.alphaMode = 0;
      this.missingFootagePath = "";
    }
  }
  class Item {
    constructor(name) {
      this.id = nextId++;
      this.name = name;
      this.parentFolder = null;
    }
  }
  class FolderItem extends Item {}
  class FootageItem extends Item {
    constructor(file, opts) {
      super(file.name);
      this.mainSource = new FileSource(file, !!(opts && opts.still));
      this.frameRate = (opts && opts.fps) || 24;
      this.duration = 5;
      this.footageMissing = false;
      this.sequence = !!(opts && opts.sequence);
    }
  }
  class AVLayer {
    constructor(comp, source, name) {
      this.containingComp = comp;
      this.source = source;
      this.name = name || source.name;
      this.startTime = 0;
      this.inPoint = 0;
      this.outPoint = source.duration || 5;
      this.stretch = 100;
      this.enabled = true;
      this.timeRemapEnabled = false;
      this.effects = [];
    }
    get index() {
      return this.containingComp.list.indexOf(this) + 1;
    }
    duplicate() {
      const d = new AVLayer(this.containingComp, this.source, this.name);
      Object.assign(d, { startTime: this.startTime, inPoint: this.inPoint, outPoint: this.outPoint, stretch: this.stretch, enabled: this.enabled });
      d.effects = this.effects.slice();
      this.containingComp.list.splice(this.index - 1, 0, d);
      return d;
    }
    replaceSource(item, fix) {
      assert.strictEqual(fix, false);
      this.source = item;
    }
    property(name) {
      assert.strictEqual(name, "ADBE Effect Parade");
      const layer = this;
      return {
        get numProperties() { return layer.effects.length; },
        property(i) { return { remove() { layer.effects.splice(i - 1, 1); } }; }
      };
    }
  }
  class TextLayer {}
  class CompItem extends Item {
    constructor(name) {
      super(name);
      this.list = [];
      this.selectedLayers = [];
    }
    get numLayers() { return this.list.length; }
    layer(i) { return this.list[i - 1]; }
  }
  class ImportOptions {
    constructor(file) {
      this.file = file;
      this.sequence = false;
      this.forceAlphabetical = false;
      this.importAs = null;
    }
    canImportAs(type) { return type === ImportAsType.FOOTAGE; }
  }
  const ImportAsType = { FOOTAGE: 1, COMP: 2 };
  const AlphaMode = { IGNORE: 0, STRAIGHT: 1, PREMULTIPLIED: 2 };
  const root = new FolderItem("root");
  const items = [];
  const imports = [];
  const undo = [];
  const itemsApi = {
    get length() { return items.length; },
    addFolder(name) {
      const f = new FolderItem(name);
      f.parentFolder = root;
      items.push(f);
      sync();
      return f;
    }
  };
  function sync() {
    items.forEach((it, i) => { itemsApi[i + 1] = it; });
  }
  const project = {
    activeItem: null,
    rootFolder: root,
    items: itemsApi,
    itemByID(id) { return items.find((i) => i.id === id) || null; },
    importFile(io) {
      imports.push({ path: io.file.fsName, sequence: io.sequence, importAs: io.importAs });
      const f = new FootageItem(io.file, { sequence: io.sequence });
      f.parentFolder = root;
      items.push(f);
      sync();
      return f;
    }
  };
  function add(item) {
    item.parentFolder = root;
    items.push(item);
    sync();
    return item;
  }
  const app = {
    project,
    version: "26.0",
    beginUndoGroup(n) { undo.push("begin " + n); },
    endUndoGroup() { undo.push("end"); }
  };
  const globals = { app, File, FileSource, FootageItem, FolderItem, CompItem, AVLayer, TextLayer, ImportOptions, ImportAsType, AlphaMode };
  return { globals, add, items, imports, undo, FootageItem, File, CompItem, AVLayer, TextLayer, project, AlphaMode };
}

module.exports = { makeAe };
