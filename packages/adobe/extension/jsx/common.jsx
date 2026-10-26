if (typeof keymaster_handlers === "undefined") {
    keymaster_handlers = {};
}

function keymaster_quote(text) {
    var s = String(text);
    var out = "\"";
    var i, c, code, hex;
    for (i = 0; i < s.length; i++) {
        c = s.charAt(i);
        code = s.charCodeAt(i);
        if (c === "\"") {
            out += "\\\"";
        } else if (c === "\\") {
            out += "\\\\";
        } else if (code === 10) {
            out += "\\n";
        } else if (code === 13) {
            out += "\\r";
        } else if (code === 9) {
            out += "\\t";
        } else if (code < 32 || code > 126) {
            hex = "0000" + code.toString(16);
            out += "\\u" + hex.substr(hex.length - 4);
        } else {
            out += c;
        }
    }
    return out + "\"";
}

function keymaster_stringify(value) {
    var parts, key, i;
    if (value === null || value === undefined) {
        return "null";
    }
    if (typeof value === "number") {
        return isFinite(value) ? String(value) : "null";
    }
    if (typeof value === "boolean") {
        return value ? "true" : "false";
    }
    if (typeof value === "string") {
        return keymaster_quote(value);
    }
    if (value instanceof Array) {
        parts = [];
        for (i = 0; i < value.length; i++) {
            parts.push(keymaster_stringify(value[i]));
        }
        return "[" + parts.join(",") + "]";
    }
    if (typeof value === "object") {
        parts = [];
        for (key in value) {
            if (value.hasOwnProperty(key) && typeof value[key] !== "function" && value[key] !== undefined) {
                parts.push(keymaster_quote(key) + ":" + keymaster_stringify(value[key]));
            }
        }
        return "{" + parts.join(",") + "}";
    }
    return keymaster_quote(String(value));
}

function keymaster_parse(text) {
    if (!/^[\],:{}\s]*$/.test(String(text).replace(/\\(?:["\\\/bfnrt]|u[0-9a-fA-F]{4})/g, "@").replace(/"[^"\\\n\r]*"|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g, "]").replace(/(?:^|:|,)(?:\s*\[)+/g, ""))) {
        throw new Error("invalid JSON from panel");
    }
    return eval("(" + text + ")");
}

function keymaster_fail(code, detail) {
    var result = { ok: false, error: code };
    if (detail !== undefined) {
        result.detail = String(detail);
    }
    return result;
}

function keymaster_call(name, payloadText) {
    var handler, payload, result;
    try {
        handler = keymaster_handlers[name];
        if (typeof handler !== "function") {
            return keymaster_stringify(keymaster_fail("host", "unknown host function " + name));
        }
        payload = keymaster_parse(payloadText);
        result = handler(payload);
        return keymaster_stringify(result);
    } catch (e) {
        return keymaster_stringify(keymaster_fail("host", String(e) + (e && e.line ? " (line " + e.line + ")" : "")));
    }
}

function keymaster_same_path(a, b) {
    var x = String(a).replace(/\\/g, "/").toLowerCase();
    var y = String(b).replace(/\\/g, "/").toLowerCase();
    return x === y;
}

keymaster_handlers.keymaster_ping = function () {
    return { ok: true, app: BridgeTalk.appName, version: String(app.version) };
};
