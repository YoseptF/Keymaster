"use strict";

var errors = require("./errors");

var HOSTS = { AEFT: "aeft", PPRO: "ppro" };

function hostId(appName) {
  return Object.prototype.hasOwnProperty.call(HOSTS, appName) ? appName : null;
}

function scriptLiteral(value) {
  var s = String(value);
  var out = '"';
  for (var i = 0; i < s.length; i++) {
    var c = s.charCodeAt(i);
    var ch = s.charAt(i);
    if (ch === '"') out += '\\"';
    else if (ch === "\\") out += "\\\\";
    else if (c === 10) out += "\\n";
    else if (c === 13) out += "\\r";
    else if (c === 9) out += "\\t";
    else if (c < 32 || c > 126) out += "\\u" + ("0000" + c.toString(16)).slice(-4);
    else out += ch;
  }
  return out + '"';
}

function callScript(fnName, payload) {
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(fnName)) throw new Error("bad host function name");
  return "keymaster_call(" + scriptLiteral(fnName) + ", " + scriptLiteral(JSON.stringify(payload === undefined ? {} : payload)) + ")";
}

function loadScript(file) {
  return "$.evalFile(" + scriptLiteral(file.replace(/\\/g, "/")) + "); \"loaded\"";
}

function parseResponse(raw) {
  var text = typeof raw === "string" ? raw : "";
  var data;
  try {
    data = JSON.parse(text);
  } catch (e) {
    throw errors.KeymasterError({ message_key: "adobe.error.host", params: { detail: text || "no response" }, detail: text });
  }
  if (!data || typeof data !== "object") {
    throw errors.KeymasterError({ message_key: "adobe.error.host", params: { detail: text }, detail: text });
  }
  if (data.ok === false) throw errors.fromHost(data);
  return data;
}

function createBridge(evalScript) {
  return {
    call: function (fnName, payload) {
      return new Promise(function (resolve, reject) {
        var script;
        try {
          script = callScript(fnName, payload);
        } catch (e) {
          reject(e);
          return;
        }
        evalScript(script, function (raw) {
          try {
            resolve(parseResponse(raw));
          } catch (err) {
            reject(err);
          }
        });
      });
    },
    load: function (file) {
      return new Promise(function (resolve, reject) {
        evalScript(loadScript(file), function (raw) {
          if (raw === "loaded") resolve();
          else reject(errors.KeymasterError({ message_key: "adobe.error.host", params: { detail: String(raw) }, detail: String(raw) }));
        });
      });
    }
  };
}

module.exports = {
  HOSTS: HOSTS,
  hostId: hostId,
  scriptLiteral: scriptLiteral,
  callScript: callScript,
  loadScript: loadScript,
  parseResponse: parseResponse,
  createBridge: createBridge
};
