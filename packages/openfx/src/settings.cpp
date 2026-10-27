#include "settings.hpp"

#include <algorithm>
#include <cctype>

#include <nlohmann/json.hpp>

#ifdef _WIN32
#include <windows.h>
#endif

namespace km {

fs::path settingsPath(const EnvFn& env) {
    std::string forced = env("KEYMASTER_SETTINGS");
    if (!forced.empty()) return u8path(forced);
#ifdef _WIN32
    std::string appdata = env("APPDATA");
    return u8path(appdata) / "Keymaster" / "settings.json";
#else
    std::string base = env("XDG_CONFIG_HOME");
    if (base.empty()) base = env("HOME") + "/.config";
    return u8path(base) / "keymaster" / "settings.json";
#endif
}

static std::string stringField(const nlohmann::json& data, const char* key) {
    auto it = data.find(key);
    if (it == data.end() || !it->is_string()) return std::string();
    return it->get<std::string>();
}

Settings loadSettings(const fs::path& path) {
    Settings settings;
    std::string text;
    if (!readFile(path, text)) return settings;
    nlohmann::json data = nlohmann::json::parse(text, nullptr, false);
    if (data.is_discarded() || !data.is_object()) return settings;
    settings.language = stringField(data, "language");
    settings.python = stringField(data, "python");
    settings.core = stringField(data, "core");
    return settings;
}

static std::string lower(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) { return (char)std::tolower(c); });
    return value;
}

std::string normalizeLanguage(const std::string& value) {
    std::string v = lower(value);
    if (v.rfind("es", 0) == 0) return "es-419";
    return "en";
}

static bool isAuto(const std::string& value) {
    std::string v = lower(value);
    return v.empty() || v == "auto";
}

std::string localeFromEnv(const EnvFn& env) {
    for (const char* name : {"LC_ALL", "LC_MESSAGES", "LANG"}) {
        std::string value = env(name);
        if (!value.empty()) return value;
    }
    return std::string();
}

std::string osUiLanguage(const EnvFn& env) {
#ifdef _WIN32
    (void)env;
    LANGID id = GetUserDefaultUILanguage();
    return PRIMARYLANGID(id) == LANG_SPANISH ? "es" : "en";
#else
    return localeFromEnv(env);
#endif
}

std::string resolveLanguage(const EnvFn& env, const Settings& settings, const std::string& osLanguage) {
    std::string forced = env("KEYMASTER_LANGUAGE");
    if (!isAuto(forced)) return normalizeLanguage(forced);
    if (!isAuto(settings.language)) return normalizeLanguage(settings.language);
    return normalizeLanguage(osLanguage);
}

std::string resolveLanguage() {
    EnvFn env = processEnv();
    return resolveLanguage(env, loadSettings(settingsPath(env)), osUiLanguage(env));
}

CoreLocation resolveCore(const EnvFn& env, const Settings& settings) {
    CoreLocation location;
    location.python = env("KEYMASTER_PYTHON");
    if (location.python.empty()) location.python = settings.python;
    location.core = env("KEYMASTER_CORE");
    if (location.core.empty()) location.core = settings.core;
    return location;
}

}
