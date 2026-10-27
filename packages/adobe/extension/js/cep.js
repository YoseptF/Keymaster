(function (root) {
  "use strict";

  var THEME_COLOR_CHANGED = "com.adobe.csxs.events.ThemeColorChanged";

  function fileUrlToPath(url, platform) {
    var path = decodeURI(String(url));
    if (path.indexOf("file:///") === 0) {
      return platform === "win32" ? path.slice(8) : path.slice(7);
    }
    if (path.indexOf("file://") === 0) return path.slice(7);
    return path;
  }

  function connect(host, platform) {
    if (!host) throw new Error("window.__adobe_cep__ is missing");
    return {
      evalScript: function (script, callback) {
        host.evalScript(script, callback || function () {});
      },
      hostEnvironment: function () {
        return JSON.parse(host.getHostEnvironment());
      },
      extensionPath: function () {
        return fileUrlToPath(host.getSystemPath("extension"), platform);
      },
      onThemeChange: function (listener) {
        host.addEventListener(THEME_COLOR_CHANGED, listener);
      }
    };
  }

  root.KeymasterCep = { THEME_COLOR_CHANGED: THEME_COLOR_CHANGED, fileUrlToPath: fileUrlToPath, connect: connect };
})(window);
