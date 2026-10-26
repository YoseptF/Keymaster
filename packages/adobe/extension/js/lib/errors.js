"use strict";

function KeymasterError(info) {
  var err = new Error(info.detail || info.message_key);
  err.name = "KeymasterError";
  err.message_key = info.message_key;
  err.params = info.params || {};
  err.detail = info.detail || "";
  return err;
}

function isKeymasterError(err) {
  return !!err && err.name === "KeymasterError" && typeof err.message_key === "string";
}

var HOST_ERRORS = {
  no_selection: { message_key: "adobe.error.no_selection" },
  multiple: { message_key: "adobe.error.multiple" },
  no_footage: { message_key: "adobe.error.no_footage" },
  no_comp: { message_key: "adobe.error.no_comp" },
  no_sequence: { message_key: "adobe.error.no_sequence" },
  source_missing: { message_key: "adobe.error.source_missing" },
  import_failed: { message_key: "adobe.error.import_failed" },
  no_track: { message_key: "adobe.error.no_track" }
};

function fromHost(response) {
  var code = response && response.error;
  var detail = (response && response.detail) || String(code || "");
  var known = Object.prototype.hasOwnProperty.call(HOST_ERRORS, code) ? HOST_ERRORS[code] : null;
  if (known) return KeymasterError({ message_key: known.message_key, detail: detail });
  return KeymasterError({ message_key: "adobe.error.host", params: { detail: detail }, detail: detail });
}

function fromSpawnError(err, python) {
  var detail = (err && err.message) || "";
  if (err && (err.code === "ENOENT" || err.code === "EACCES" || err.code === "EPERM")) {
    return KeymasterError({ message_key: "adobe.error.python_missing", params: { path: python || err.path || "" }, detail: detail });
  }
  return KeymasterError({ message_key: "adobe.error.spawn", params: { detail: detail }, detail: detail });
}

function fromCoreEvent(event) {
  return KeymasterError({
    message_key: typeof event.message_key === "string" ? event.message_key : "",
    params: event.params && typeof event.params === "object" ? event.params : {},
    detail: event.detail || ""
  });
}

function describe(err, i18n) {
  if (err && typeof err.message_key === "string" && err.message_key && i18n.has(err.message_key)) {
    return i18n.t(err.message_key, err.params || {});
  }
  var detail = err && typeof err === "object" ? (err.detail || err.message_key || err.message || "") : String(err);
  return i18n.t("adobe.error.core_unknown", { detail: detail });
}

module.exports = {
  KeymasterError: KeymasterError,
  isKeymasterError: isKeymasterError,
  HOST_ERRORS: HOST_ERRORS,
  fromHost: fromHost,
  fromSpawnError: fromSpawnError,
  fromCoreEvent: fromCoreEvent,
  describe: describe
};
