"use strict";

var PHASES = ["load", "prepass", "stage1", "stage2", "write"];

function phaseKey(phase) {
  switch (phase) {
    case "load": return { message_key: "adobe.phase.load" };
    case "prepass": return { message_key: "adobe.phase.prepass" };
    case "stage1": return { message_key: "adobe.phase.stage1" };
    case "stage2": return { message_key: "adobe.phase.stage2" };
    case "write": return { message_key: "adobe.phase.write" };
    default: return { message_key: "adobe.phase.working" };
  }
}

function ProgressTracker() {
  this.fraction = 0;
  this.phase = null;
  this.messageKey = null;
}

ProgressTracker.prototype.update = function (event) {
  var f = Number(event && event.fraction);
  if (isFinite(f)) this.fraction = Math.max(this.fraction, Math.min(1, Math.max(0, f)));
  if (event && typeof event.phase === "string") this.phase = event.phase;
  if (event && typeof event.message_key === "string" && event.message_key) this.messageKey = event.message_key;
  return this.fraction;
};

ProgressTracker.prototype.text = function (i18n) {
  if (this.messageKey && i18n.has(this.messageKey)) return i18n.t(this.messageKey);
  return i18n.t(phaseKey(this.phase).message_key);
};

ProgressTracker.prototype.percent = function () {
  return Math.floor(this.fraction * 100);
};

module.exports = { PHASES: PHASES, phaseKey: phaseKey, ProgressTracker: ProgressTracker };
