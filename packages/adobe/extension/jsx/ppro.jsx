var KEYMASTER_TICKS = 254016000000;

function keymaster_pp_seconds(ticks) {
    return Number(ticks) / KEYMASTER_TICKS;
}

function keymaster_pp_track_of(seq, nodeId) {
    var t, c, track;
    for (t = 0; t < seq.videoTracks.numTracks; t++) {
        track = seq.videoTracks[t];
        for (c = 0; c < track.clips.numItems; c++) {
            if (track.clips[c].nodeId === nodeId) {
                return { index: t, clip: track.clips[c] };
            }
        }
    }
    return null;
}

function keymaster_pp_fps(item, seq) {
    var interp, rate = 0;
    try {
        interp = item.getFootageInterpretation();
        if (interp && interp.frameRate > 0) {
            rate = interp.frameRate;
        }
    } catch (e) {
    }
    if (!rate && seq && seq.timebase) {
        rate = KEYMASTER_TICKS / Number(seq.timebase);
    }
    return rate;
}

keymaster_handlers.keymaster_getSelection = function () {
    var seq = app.project ? app.project.activeSequence : null;
    var selection, videos = [], i, clip, item, path, found;
    if (!seq) {
        return keymaster_fail("no_sequence");
    }
    selection = seq.getSelection();
    for (i = 0; selection && i < selection.length; i++) {
        if (selection[i].mediaType === "Video") {
            videos.push(selection[i]);
        }
    }
    if (videos.length === 0) {
        return keymaster_fail("no_selection");
    }
    if (videos.length > 1) {
        return keymaster_fail("multiple");
    }
    clip = videos[0];
    item = clip.projectItem;
    if (!item || item.type === ProjectItemType.BIN || item.isSequence()) {
        return keymaster_fail("no_footage");
    }
    if (typeof item.isOffline === "function" && item.isOffline()) {
        return keymaster_fail("source_missing", item.name);
    }
    path = item.getMediaPath();
    if (!path) {
        return keymaster_fail("no_footage");
    }
    found = keymaster_pp_track_of(seq, clip.nodeId);
    return {
        ok: true,
        host: "PPRO",
        source: {
            path: path,
            name: clip.name,
            fps: keymaster_pp_fps(item, seq),
            start: clip.start.seconds,
            end: clip.end.seconds,
            inPoint: clip.inPoint.seconds,
            outPoint: clip.outPoint.seconds,
            ref: {
                sequenceId: seq.sequenceID,
                nodeId: clip.nodeId,
                trackIndex: found ? found.index : -1,
                startTicks: clip.start.ticks,
                endTicks: clip.end.ticks,
                inTicks: clip.inPoint.ticks,
                outTicks: clip.outPoint.ticks
            }
        }
    };
};

function keymaster_pp_sequence(id) {
    var i;
    for (i = 0; i < app.project.sequences.numSequences; i++) {
        if (app.project.sequences[i].sequenceID === id) {
            return app.project.sequences[i];
        }
    }
    return null;
}

function keymaster_pp_bin(name) {
    var root = app.project.rootItem;
    var i, child;
    for (i = 0; i < root.children.numItems; i++) {
        child = root.children[i];
        if (child.type === ProjectItemType.BIN && child.name === name) {
            return child;
        }
    }
    return root.createBin(name);
}

function keymaster_pp_find_in_bin(bin, file) {
    var i, child, path;
    for (i = bin.children.numItems - 1; i >= 0; i--) {
        child = bin.children[i];
        if (child.type !== ProjectItemType.BIN) {
            path = child.getMediaPath();
            if (path && keymaster_same_path(path, file)) {
                return child;
            }
        }
    }
    return null;
}

function keymaster_pp_import(output, fps, bin) {
    var sequence = output.type === "image_sequence";
    var item, interp;
    app.project.importFiles([output.firstFile], true, bin, sequence);
    item = keymaster_pp_find_in_bin(bin, output.firstFile);
    if (!item) {
        return null;
    }
    if (sequence && fps > 0) {
        item.setOverrideFrameRate(fps);
    }
    if (sequence && output.kind === "cutout") {
        try {
            interp = item.getFootageInterpretation();
            if (interp) {
                interp.alphaUsage = 1;
                item.setFootageInterpretation(interp);
            }
        } catch (e) {
        }
    }
    return item;
}

function keymaster_pp_track_is_free(track, startTicks, endTicks) {
    var c, clip, s = Number(startTicks), e = Number(endTicks);
    for (c = 0; c < track.clips.numItems; c++) {
        clip = track.clips[c];
        if (Number(clip.start.ticks) < e && Number(clip.end.ticks) > s) {
            return false;
        }
    }
    return true;
}

function keymaster_pp_free_track(seq, above, startTicks, endTicks) {
    var t, qeSeq, before;
    for (t = above + 1; t < seq.videoTracks.numTracks; t++) {
        if (keymaster_pp_track_is_free(seq.videoTracks[t], startTicks, endTicks)) {
            return t;
        }
    }
    if (app.project.activeSequence && app.project.activeSequence.sequenceID === seq.sequenceID) {
        before = seq.videoTracks.numTracks;
        try {
            app.enableQE();
            qeSeq = qe.project.getActiveSequence();
            qeSeq.addTracks(1, before, 0);
        } catch (e) {
        }
        if (seq.videoTracks.numTracks > before) {
            return seq.videoTracks.numTracks - 1;
        }
    }
    return -1;
}

function keymaster_pp_place(seq, found, item, ref) {
    var target = keymaster_pp_free_track(seq, found.index, ref.startTicks, ref.endTicks);
    var track, placed = null, c;
    if (target < 0) {
        return null;
    }
    item.setInPoint(keymaster_pp_seconds(ref.inTicks), 4);
    item.setOutPoint(keymaster_pp_seconds(ref.outTicks), 4);
    track = seq.videoTracks[target];
    track.overwriteClip(item, keymaster_pp_seconds(ref.startTicks));
    try {
        item.clearInPoint();
        item.clearOutPoint();
    } catch (e) {
    }
    for (c = 0; c < track.clips.numItems; c++) {
        if (track.clips[c].projectItem && track.clips[c].projectItem.nodeId === item.nodeId &&
                Math.abs(Number(track.clips[c].start.ticks) - Number(ref.startTicks)) < KEYMASTER_TICKS / 1000) {
            placed = track.clips[c];
        }
    }
    return { track: target, clip: placed };
}

keymaster_handlers.keymaster_importResult = function (payload) {
    var ref = payload.ref;
    var seq = keymaster_pp_sequence(ref.sequenceId);
    var found, bin, i, output, item, cutout = null, imported = [], placed = null;
    if (!seq) {
        return keymaster_fail("no_sequence");
    }
    found = keymaster_pp_track_of(seq, ref.nodeId);
    if (!found) {
        return keymaster_fail("source_missing", "source clip not found");
    }
    bin = keymaster_pp_bin(payload.folder || "Keymaster");
    if (!bin) {
        return keymaster_fail("import_failed", "bin");
    }
    for (i = 0; i < payload.outputs.length; i++) {
        output = payload.outputs[i];
        item = keymaster_pp_import(output, payload.fps, bin);
        if (!item) {
            return keymaster_fail("import_failed", output.firstFile);
        }
        imported.push({ kind: output.kind, name: item.name });
        if (output.kind === "cutout") {
            cutout = item;
        }
    }
    if (cutout) {
        placed = keymaster_pp_place(seq, found, cutout, ref);
        if (!placed) {
            return keymaster_fail("no_track");
        }
        if (payload.disableSource) {
            found.clip.disabled = true;
        }
    }
    return {
        ok: true,
        imported: imported,
        placed: placed ? { track: placed.track, verified: placed.clip !== null } : null
    };
};
