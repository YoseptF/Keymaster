#pragma once

#include <string>

#include "paths.hpp"

namespace km {

struct Settings {
    std::string language;
    std::string python;
    std::string core;
};

fs::path settingsPath(const EnvFn& env);
Settings loadSettings(const fs::path& path);
std::string normalizeLanguage(const std::string& value);
std::string localeFromEnv(const EnvFn& env);
std::string osUiLanguage(const EnvFn& env);
std::string resolveLanguage(const EnvFn& env, const Settings& settings, const std::string& osLanguage);
std::string resolveLanguage();

struct CoreLocation {
    std::string python;
    std::string core;
};

CoreLocation resolveCore(const EnvFn& env, const Settings& settings);

}
