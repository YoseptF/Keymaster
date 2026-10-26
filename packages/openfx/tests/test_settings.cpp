#include <map>

#include "check.hpp"
#include "settings.hpp"

using namespace km;

static EnvFn fakeEnv(std::map<std::string, std::string> values) {
    return [values](const std::string& name) {
        auto it = values.find(name);
        return it == values.end() ? std::string() : it->second;
    };
}

int main() {
    CHECK_EQ(normalizeLanguage("es-419"), std::string("es-419"));
    CHECK_EQ(normalizeLanguage("es_MX.UTF-8"), std::string("es-419"));
    CHECK_EQ(normalizeLanguage("ES"), std::string("es-419"));
    CHECK_EQ(normalizeLanguage("en_US.UTF-8"), std::string("en"));
    CHECK_EQ(normalizeLanguage("fr_FR"), std::string("en"));
    CHECK_EQ(normalizeLanguage("C"), std::string("en"));
    CHECK_EQ(normalizeLanguage(""), std::string("en"));

    Settings none;
    Settings spanish;
    spanish.language = "es-419";
    Settings english;
    english.language = "en";
    Settings automatic;
    automatic.language = "auto";

    CHECK_EQ(resolveLanguage(fakeEnv({{"KEYMASTER_LANGUAGE", "es-419"}}), english, "en_US"), std::string("es-419"));
    CHECK_EQ(resolveLanguage(fakeEnv({{"KEYMASTER_LANGUAGE", "en"}}), spanish, "es_AR"), std::string("en"));
    CHECK_EQ(resolveLanguage(fakeEnv({{"KEYMASTER_LANGUAGE", "auto"}}), spanish, "en_US"), std::string("es-419"));
    CHECK_EQ(resolveLanguage(fakeEnv({}), spanish, "en_US"), std::string("es-419"));
    CHECK_EQ(resolveLanguage(fakeEnv({}), english, "es_ES"), std::string("en"));
    CHECK_EQ(resolveLanguage(fakeEnv({}), automatic, "es_CO.UTF-8"), std::string("es-419"));
    CHECK_EQ(resolveLanguage(fakeEnv({}), none, "es_CO.UTF-8"), std::string("es-419"));
    CHECK_EQ(resolveLanguage(fakeEnv({}), none, "de_DE.UTF-8"), std::string("en"));
    CHECK_EQ(resolveLanguage(fakeEnv({}), none, ""), std::string("en"));

    CHECK_EQ(localeFromEnv(fakeEnv({{"LC_ALL", "es_MX"}, {"LC_MESSAGES", "en_US"}, {"LANG", "en_US"}})), std::string("es_MX"));
    CHECK_EQ(localeFromEnv(fakeEnv({{"LC_MESSAGES", "es_PE"}, {"LANG", "en_US"}})), std::string("es_PE"));
    CHECK_EQ(localeFromEnv(fakeEnv({{"LANG", "es_CL.UTF-8"}})), std::string("es_CL.UTF-8"));
    CHECK_EQ(localeFromEnv(fakeEnv({})), std::string(""));

    fs::path dir = fs::path(KM_TEST_TMP) / "settings";
    fs::create_directories(dir);
#ifndef _WIN32
    CHECK_EQ(settingsPath(fakeEnv({{"HOME", "/home/u"}})), fs::path("/home/u/.config/keymaster/settings.json"));
    CHECK_EQ(settingsPath(fakeEnv({{"HOME", "/home/u"}, {"XDG_CONFIG_HOME", "/cfg"}})), fs::path("/cfg/keymaster/settings.json"));
#endif
    CHECK_EQ(settingsPath(fakeEnv({{"KEYMASTER_SETTINGS", (dir / "s.json").string()}})), dir / "s.json");

    writeFile(dir / "s.json", R"({"language": "es-419", "python": "/v/bin/python", "core": "/opt/core"})");
    Settings loaded = loadSettings(dir / "s.json");
    CHECK_EQ(loaded.language, std::string("es-419"));
    CHECK_EQ(loaded.python, std::string("/v/bin/python"));
    CHECK_EQ(loaded.core, std::string("/opt/core"));

    writeFile(dir / "bad.json", "{oops");
    Settings bad = loadSettings(dir / "bad.json");
    CHECK(bad.language.empty() && bad.python.empty());
    Settings missing = loadSettings(dir / "nope.json");
    CHECK(missing.core.empty());

    CoreLocation fromFile = resolveCore(fakeEnv({}), loaded);
    CHECK_EQ(fromFile.python, std::string("/v/bin/python"));
    CHECK_EQ(fromFile.core, std::string("/opt/core"));
    CoreLocation fromEnv = resolveCore(fakeEnv({{"KEYMASTER_PYTHON", "/p"}, {"KEYMASTER_CORE", "/c"}}), loaded);
    CHECK_EQ(fromEnv.python, std::string("/p"));
    CHECK_EQ(fromEnv.core, std::string("/c"));
    return finish("settings");
}
