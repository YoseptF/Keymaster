function keymaster_ae_is_image(name) {
    return /\.(exr|png|jpe?g|tiff?|dpx|bmp|tga|webp)$/i.test(String(name));
}

function keymaster_ae_layer_info(comp, layer) {
    var footage = layer.source;
    var src = footage.mainSource;
    var file = src.file;
    return {
        path: file.fsName,
        name: layer.name,
        isSequence: !src.isStill && keymaster_ae_is_image(file.name),
        fps: footage.frameRate,
        duration: footage.duration,
        startTime: layer.startTime,
        inPoint: layer.inPoint,
        outPoint: layer.outPoint,
        stretch: layer.stretch,
        timeRemap: layer.timeRemapEnabled === true,
        ref: {
            compId: comp.id,
            layerIndex: layer.index,
            layerName: layer.name,
            sourceId: footage.id
        }
    };
}

function keymaster_ae_is_footage_layer(layer) {
    return layer instanceof AVLayer && layer.source instanceof FootageItem && layer.source.mainSource instanceof FileSource;
}

keymaster_handlers.keymaster_getSelection = function () {
    var comp = app.project ? app.project.activeItem : null;
    var layers, layer;
    if (!comp || !(comp instanceof CompItem)) {
        return keymaster_fail("no_comp");
    }
    layers = comp.selectedLayers;
    if (!layers || layers.length === 0) {
        return keymaster_fail("no_selection");
    }
    if (layers.length > 1) {
        return keymaster_fail("multiple");
    }
    layer = layers[0];
    if (!keymaster_ae_is_footage_layer(layer)) {
        return keymaster_fail("no_footage");
    }
    if (layer.source.footageMissing) {
        return keymaster_fail("source_missing", layer.source.mainSource.missingFootagePath);
    }
    if (!layer.source.mainSource.file) {
        return keymaster_fail("no_footage");
    }
    return { ok: true, host: "AEFT", source: keymaster_ae_layer_info(comp, layer) };
};

function keymaster_ae_find_layer(ref) {
    var comp = app.project.itemByID(ref.compId);
    var i, layer, fallback = null;
    if (!comp || !(comp instanceof CompItem)) {
        return null;
    }
    if (ref.layerIndex >= 1 && ref.layerIndex <= comp.numLayers) {
        layer = comp.layer(ref.layerIndex);
        if (layer.source && layer.source.id === ref.sourceId && layer.name === ref.layerName) {
            return { comp: comp, layer: layer };
        }
    }
    for (i = 1; i <= comp.numLayers; i++) {
        layer = comp.layer(i);
        if (layer.source && layer.source.id === ref.sourceId) {
            if (layer.name === ref.layerName) {
                return { comp: comp, layer: layer };
            }
            if (!fallback) {
                fallback = layer;
            }
        }
    }
    return fallback ? { comp: comp, layer: fallback } : null;
}

function keymaster_ae_folder(name) {
    var items = app.project.items;
    var i, item;
    for (i = 1; i <= items.length; i++) {
        item = items[i];
        if (item instanceof FolderItem && item.name === name && item.parentFolder === app.project.rootFolder) {
            return item;
        }
    }
    return items.addFolder(name);
}

function keymaster_ae_import(output, fps, folder) {
    var options = new ImportOptions(new File(output.firstFile));
    var item;
    if (output.type === "image_sequence") {
        options.sequence = true;
        options.forceAlphabetical = false;
    }
    if (options.canImportAs(ImportAsType.FOOTAGE)) {
        options.importAs = ImportAsType.FOOTAGE;
    }
    item = app.project.importFile(options);
    if (!item) {
        return null;
    }
    item.parentFolder = folder;
    if (output.type === "image_sequence" && fps > 0) {
        item.mainSource.conformFrameRate = fps;
    }
    if (output.kind === "cutout" && output.type === "image_sequence") {
        try {
            item.mainSource.alphaMode = AlphaMode.STRAIGHT;
        } catch (e) {
        }
    }
    return item;
}

function keymaster_ae_strip_effects(layer) {
    var effects = layer.property("ADBE Effect Parade");
    var i;
    if (!effects) {
        return;
    }
    for (i = effects.numProperties; i >= 1; i--) {
        effects.property(i).remove();
    }
}

function keymaster_ae_place(found, item, disableSource) {
    var source = found.layer;
    var placed = source.duplicate();
    placed.replaceSource(item, false);
    keymaster_ae_strip_effects(placed);
    placed.enabled = true;
    if (disableSource) {
        source.enabled = false;
    }
    return placed;
}

keymaster_handlers.keymaster_importResult = function (payload) {
    var found = keymaster_ae_find_layer(payload.ref);
    var folder, i, output, item, cutout = null, imported = [], placed = null;
    if (!found) {
        return keymaster_fail("source_missing", "source layer not found");
    }
    app.beginUndoGroup("Keymaster");
    try {
        folder = keymaster_ae_folder(payload.folder || "Keymaster");
        for (i = 0; i < payload.outputs.length; i++) {
            output = payload.outputs[i];
            item = keymaster_ae_import(output, payload.fps, folder);
            if (!item) {
                return keymaster_fail("import_failed", output.firstFile);
            }
            imported.push({ kind: output.kind, id: item.id, name: item.name });
            if (output.kind === "cutout") {
                cutout = item;
            }
        }
        if (cutout) {
            placed = keymaster_ae_place(found, cutout, payload.disableSource);
        }
    } catch (e) {
        return keymaster_fail("import_failed", String(e) + (e && e.line ? " (line " + e.line + ")" : ""));
    } finally {
        app.endUndoGroup();
    }
    return { ok: true, imported: imported, placed: placed ? { index: placed.index, name: placed.name } : null };
};
