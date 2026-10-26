(function () {
  "use strict";

  var cs = new CSInterface();
  var nodePath = require("path");
  var extRoot = cs.getSystemPath(SystemPath.EXTENSION);
  function lib(name) {
    return require(nodePath.join(extRoot, "js", "lib", name + ".js"));
  }
  var settingsLib = lib("settings");
  var i18nLib = lib("i18n");
  var hostLib = lib("host");
  var themeLib = lib("theme");
  var errorsLib = lib("errors");
  var jobLib = lib("job");
  var progressLib = lib("progress");

  var env = cs.getHostEnvironment();
  var host = hostLib.hostId(env.appName);
  var settings = settingsLib.load();
  var i18n = i18nLib.createI18n(i18nLib.loadTables(extRoot, settingsLib.LANGUAGES), settings.language);
  var bridge = hostLib.createBridge(function (script, callback) { cs.evalScript(script, callback); });
  var storageKey = "keymaster.options." + (host || "unknown");

  var state = {
    job: null,
    source: null,
    tracker: new progressLib.ProgressTracker(),
    showProgress: false,
    status: null,
    error: null,
    detail: "",
    doctor: null,
    doctorStatus: null,
    hintFirstFrame: "",
    outputRoot: ""
  };

  function $(id) {
    return document.getElementById(id);
  }

  function defaults() {
    return {
      hintFirstFrame: "",
      hintQuality: 0.95,
      despill: 0.5,
      outputs: ["cutout"],
      format: host === "PPRO" ? "video" : "exr",
      outputRoot: "",
      disableSource: true,
      lowVram: false
    };
  }

  function loadOptions() {
    var o = defaults();
    try {
      var saved = JSON.parse(window.localStorage.getItem(storageKey) || "{}");
      Object.keys(o).forEach(function (k) {
        if (saved[k] !== undefined && saved[k] !== null) o[k] = saved[k];
      });
    } catch (e) {}
    return o;
  }

  function readOptions() {
    var outputs = [];
    var boxes = document.querySelectorAll("input[name=output]");
    for (var i = 0; i < boxes.length; i++) if (boxes[i].checked) outputs.push(boxes[i].value);
    return {
      hintFirstFrame: state.hintFirstFrame,
      hintQuality: parseFloat($("hint-quality").value),
      despill: parseFloat($("despill").value),
      outputs: outputs,
      format: $("format").value,
      outputRoot: state.outputRoot,
      disableSource: $("disable-source").checked,
      lowVram: $("low-vram").checked
    };
  }

  function saveOptions() {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(readOptions()));
    } catch (e) {}
  }

  function applyOptions(o) {
    state.hintFirstFrame = o.hintFirstFrame || "";
    state.outputRoot = o.outputRoot || "";
    $("hint-quality").value = String(o.hintQuality);
    $("despill").value = String(o.despill);
    $("format").value = o.format === "video" ? "video" : "exr";
    $("disable-source").checked = !!o.disableSource;
    $("low-vram").checked = !!o.lowVram;
    var boxes = document.querySelectorAll("input[name=output]");
    for (var i = 0; i < boxes.length; i++) boxes[i].checked = o.outputs.indexOf(boxes[i].value) !== -1;
  }

  function setStatus(info, params, kind) {
    state.status = info ? { key: info.message_key, params: params || {}, kind: kind || "" } : null;
    state.error = null;
  }

  function setError(err) {
    state.error = err;
    state.status = null;
    var lines = [];
    if (err && err.detail) lines.push(err.detail);
    if (err && err.stderr) lines.push(err.stderr);
    state.detail = lines.join("\n\n").trim();
  }

  function render() {
    var busy = !!state.job;
    $("key").disabled = busy || !host;
    $("cancel").disabled = !busy;
    $("doctor").disabled = busy;
    $("refresh").disabled = busy;
    $("hint-quality-value").textContent = Number($("hint-quality").value).toFixed(2);
    $("despill-value").textContent = Number($("despill").value).toFixed(2);
    $("hint-path").textContent = state.hintFirstFrame || i18n.t("adobe.options.hint_none");
    $("output-root").textContent = state.outputRoot || i18n.t("adobe.options.output_root_default");
    $("language").value = i18n.language();

    if (state.source) {
      $("source-name").textContent = state.source.name || "";
      $("source-path").textContent = state.source.path || "";
    } else {
      $("source-name").textContent = host === "PPRO" ? i18n.t("adobe.source.none_ppro") : i18n.t("adobe.source.none_aeft");
      $("source-path").textContent = "";
    }

    $("progress").value = state.showProgress ? state.tracker.percent() : 0;
    $("phase").textContent = state.showProgress ? state.tracker.text(i18n) : "";
    $("percent").textContent = state.showProgress ? i18n.t("adobe.progress.percent", { percent: state.tracker.percent() }) : "";

    var status = $("status");
    if (state.error) {
      status.textContent = errorsLib.describe(state.error, i18n);
      status.className = "status error";
    } else if (state.status) {
      status.textContent = i18n.t(state.status.key, state.status.params);
      status.className = "status " + state.status.kind;
    } else {
      status.textContent = "";
      status.className = "status";
    }
    $("details").hidden = !state.detail;
    $("details-text").textContent = state.detail;

    renderDoctor();
  }

  function renderDoctor() {
    var box = $("setup-status");
    var list = $("checks");
    list.innerHTML = "";
    if (state.doctorStatus && state.doctorStatus.error) {
      box.textContent = errorsLib.describe(state.doctorStatus.error, i18n);
      box.className = "status error";
      return;
    }
    if (state.doctorStatus && state.doctorStatus.message_key) {
      box.textContent = i18n.t(state.doctorStatus.message_key);
      box.className = "status " + (state.doctorStatus.kind || "");
    } else {
      box.textContent = "";
      box.className = "status";
    }
    var checks = state.doctor && Array.isArray(state.doctor.checks) ? state.doctor.checks : [];
    checks.forEach(function (check) {
      var li = document.createElement("li");
      li.className = check.ok ? "ok" : "missing";
      li.textContent = check.message_key && i18n.has(check.message_key)
        ? i18n.t(check.message_key, check.params || {})
        : (check.ok ? i18n.t("adobe.doctor.ok", { id: check.id }) : i18n.t("adobe.doctor.missing", { id: check.id }));
      list.appendChild(li);
    });
  }

  function retranslate() {
    i18nLib.translateDocument(document, i18n);
    render();
  }

  function applyTheme() {
    var skin = cs.getHostEnvironment().appSkinInfo;
    var vars = themeLib.themeVars(skin);
    Object.keys(vars).forEach(function (name) {
      document.documentElement.style.setProperty(name, vars[name]);
    });
  }

  function refreshSelection() {
    if (!host || state.job) return Promise.resolve();
    return bridge.call("keymaster_getSelection", {}).then(function (res) {
      state.source = res.source;
      render();
    }, function (err) {
      state.source = null;
      render();
      return err;
    });
  }

  function choose(title, directory, initial, types) {
    if (!window.cep || !window.cep.fs) return "";
    var res = window.cep.fs.showOpenDialog(false, directory, title, initial || "", types || []);
    return res && res.err === 0 && res.data && res.data.length ? res.data[0] : "";
  }

  function startKey() {
    if (state.job) return;
    saveOptions();
    settings = settingsLib.load();
    state.tracker = new progressLib.ProgressTracker();
    state.showProgress = false;
    state.detail = "";
    setStatus({ message_key: "adobe.status.selection" });
    var job = jobLib.startKeyJob({
      settings: settings,
      bridge: bridge,
      options: readOptions(),
      onUpdate: function (update) {
        if (update.source) state.source = update.source;
        if (update.phase === "selection") setStatus({ message_key: "adobe.status.selection" });
        if (update.phase === "keying") {
          state.tracker = update.tracker;
          state.showProgress = true;
          setStatus(null);
        }
        if (update.phase === "importing") setStatus({ message_key: "adobe.status.importing" });
        render();
      }
    });
    state.job = job;
    render();
    job.promise.then(function (result) {
      state.job = null;
      if (result.status === "done") {
        state.tracker.update({ fraction: 1 });
        var placed = result.imported && result.imported.placed;
        setStatus(placed ? { message_key: "adobe.status.done" } : { message_key: "adobe.status.done_not_placed" }, {
          seconds: result.seconds.toFixed(1),
          path: result.outputDir
        }, "ok");
        state.detail = result.commandLine || "";
      } else if (result.status === "cancelled") {
        state.showProgress = false;
        setStatus({ message_key: "adobe.status.cancelled" });
      } else {
        state.showProgress = false;
        setError(result.error);
      }
      render();
    });
  }

  function cancelKey() {
    if (!state.job) return;
    state.job.cancel();
    setStatus({ message_key: "adobe.status.cancelling" });
    render();
  }

  function runDoctor() {
    settings = settingsLib.load();
    state.doctor = null;
    state.doctorStatus = { message_key: "adobe.status.doctor_running" };
    $("doctor").disabled = true;
    render();
    jobLib.runDoctor({ settings: settings }).then(function (res) {
      if (res.status === "done") {
        state.doctor = res.report;
        state.doctorStatus = res.report.ok ? { message_key: "adobe.status.doctor_ok", kind: "ok" } : { message_key: "adobe.status.doctor_failed", kind: "error" };
      } else {
        state.doctorStatus = { error: res.error };
      }
      render();
    });
  }

  function changeLanguage(lang) {
    var chosen = settingsLib.normalizeLanguage(lang);
    try {
      settingsLib.writeLanguage(settings.file, chosen);
    } catch (e) {
      setError(errorsLib.KeymasterError({ message_key: "adobe.error.settings_write", params: { path: settings.file }, detail: e.message }));
    }
    i18n.setLanguage(chosen);
    retranslate();
  }

  function syncLanguage() {
    var fresh = settingsLib.load();
    settings = fresh;
    if (fresh.language !== i18n.language()) {
      i18n.setLanguage(fresh.language);
      retranslate();
    }
  }

  function wire() {
    $("key").addEventListener("click", startKey);
    $("cancel").addEventListener("click", cancelKey);
    $("doctor").addEventListener("click", runDoctor);
    $("refresh").addEventListener("click", function () { refreshSelection(); });
    $("language").addEventListener("change", function (e) { changeLanguage(e.target.value); });
    $("hint-choose").addEventListener("click", function () {
      var file = choose(i18n.t("adobe.options.hint_dialog"), false, state.source ? nodePath.dirname(state.source.path) : "", ["png", "jpg", "jpeg", "exr", "tif", "tiff"]);
      if (file) {
        state.hintFirstFrame = file;
        saveOptions();
        render();
      }
    });
    $("hint-clear").addEventListener("click", function () {
      state.hintFirstFrame = "";
      saveOptions();
      render();
    });
    $("output-choose").addEventListener("click", function () {
      var dir = choose(i18n.t("adobe.options.output_root_dialog"), true, state.outputRoot, []);
      if (dir) {
        state.outputRoot = dir;
        saveOptions();
        render();
      }
    });
    $("output-clear").addEventListener("click", function () {
      state.outputRoot = "";
      saveOptions();
      render();
    });
    ["hint-quality", "despill"].forEach(function (id) {
      $(id).addEventListener("input", render);
      $(id).addEventListener("change", saveOptions);
    });
    ["format", "disable-source", "low-vram"].forEach(function (id) {
      $(id).addEventListener("change", saveOptions);
    });
    var boxes = document.querySelectorAll("input[name=output]");
    for (var i = 0; i < boxes.length; i++) boxes[i].addEventListener("change", saveOptions);
    window.addEventListener("focus", function () {
      syncLanguage();
      refreshSelection();
    });
    cs.addEventListener(CSInterface.THEME_COLOR_CHANGED_EVENT, applyTheme);
  }

  function loadHostScripts() {
    var file = host === "PPRO" ? "ppro.jsx" : "aeft.jsx";
    return bridge.load(nodePath.join(extRoot, "jsx", "common.jsx"))
      .then(function () { return bridge.load(nodePath.join(extRoot, "jsx", file)); });
  }

  applyTheme();
  applyOptions(loadOptions());
  wire();
  retranslate();
  if (!host) {
    setError(errorsLib.KeymasterError({ message_key: "adobe.error.no_host", params: { app: env.appName }, detail: env.appName }));
    render();
    return;
  }
  if (!settings.python || !settings.core) {
    setError(errorsLib.KeymasterError({ message_key: "adobe.error.not_configured", detail: settings.file }));
  } else {
    setStatus({ message_key: "adobe.status.ready" });
  }
  render();
  loadHostScripts().then(refreshSelection, function (err) {
    setError(err);
    render();
  });
})();
