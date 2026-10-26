#include "cache.hpp"

#include <chrono>
#include <cmath>
#include <cstdio>
#include <ctime>
#include <random>
#include <system_error>

#include <nlohmann/json.hpp>

namespace km {

static const char* kManifestName = "keymaster-openfx.json";
static const char* kDirPrefix = "km-";

fs::path cacheRoot(const EnvFn& env) {
#ifdef _WIN32
    std::string base = env("LOCALAPPDATA");
    if (base.empty()) base = env("APPDATA");
    return u8path(base) / "Keymaster" / "openfx";
#else
    std::string base = env("XDG_CACHE_HOME");
    if (base.empty()) base = env("HOME") + "/.cache";
    return u8path(base) / "keymaster" / "openfx";
#endif
}

static std::string randomHex(int digits) {
    static std::mt19937_64 engine([] {
        std::random_device device;
        uint64_t seed = ((uint64_t)device() << 32) ^ device();
        return seed ^ (uint64_t)std::chrono::high_resolution_clock::now().time_since_epoch().count();
    }());
    static const char* hex = "0123456789abcdef";
    std::string out;
    uint64_t value = engine();
    for (int i = 0; i < digits; ++i) {
        if (i % 16 == 0 && i) value = engine();
        out += hex[value & 15];
        value >>= 4;
    }
    return out;
}

std::string newCacheName() {
    std::time_t now = std::time(nullptr);
    std::tm parts{};
#ifdef _WIN32
    gmtime_s(&parts, &now);
#else
    gmtime_r(&now, &parts);
#endif
    char stamp[32];
    std::strftime(stamp, sizeof(stamp), "%Y%m%d-%H%M%S", &parts);
    return std::string(kDirPrefix) + stamp + "-" + randomHex(8);
}

std::string newToken() {
    return randomHex(16);
}

fs::path manifestPath(const fs::path& dir) { return dir / kManifestName; }
fs::path inputDir(const fs::path& dir) { return dir / "input"; }
fs::path outputDir(const fs::path& dir) { return dir / "out"; }
fs::path logPath(const fs::path& dir) { return dir / "core.log"; }

fs::path inputFramePath(const fs::path& dir, int index) {
    char name[32];
    std::snprintf(name, sizeof(name), "frame_%06d.exr", index);
    return inputDir(dir) / name;
}

static std::string relativeTo(const fs::path& dir, const std::string& value) {
    if (value.empty()) return value;
    std::string base = u8string(dir.lexically_normal());
    std::string full = u8string(u8path(value).lexically_normal());
    while (!base.empty() && (base.back() == '/' || base.back() == '\\')) base.pop_back();
    if (full.size() > base.size() + 1 && full.compare(0, base.size(), base) == 0 &&
        (full[base.size()] == '/' || full[base.size()] == '\\')) {
        std::string rest = full.substr(base.size() + 1);
        for (char& c : rest) {
            if (c == '\\') c = '/';
        }
        return rest;
    }
    return value;
}

bool writeManifest(const fs::path& dir, const Manifest& manifest) {
    nlohmann::json data;
    data["version"] = 1;
    data["token"] = manifest.token;
    data["first"] = manifest.first;
    data["last"] = manifest.last;
    data["width"] = manifest.width;
    data["height"] = manifest.height;
    data["hint_quality"] = manifest.hintQuality;
    data["despill"] = manifest.despill;
    nlohmann::json outputs = nlohmann::json::object();
    for (const auto& [kind, output] : manifest.outputs) {
        outputs[kind] = {{"type", output.type},
                         {"pattern", relativeTo(dir, output.pattern)},
                         {"first_frame", output.firstFrame},
                         {"frames", output.frames}};
    }
    data["outputs"] = outputs;
    return writeFileAtomic(manifestPath(dir), data.dump(2));
}

bool readManifest(const fs::path& dir, Manifest& manifest) {
    std::string text;
    if (!readFile(manifestPath(dir), text)) return false;
    nlohmann::json data = nlohmann::json::parse(text, nullptr, false);
    if (data.is_discarded() || !data.is_object()) return false;
    try {
        manifest = Manifest();
        manifest.token = data.at("token").get<std::string>();
        manifest.first = data.at("first").get<int>();
        manifest.last = data.at("last").get<int>();
        manifest.width = data.value("width", 0);
        manifest.height = data.value("height", 0);
        manifest.hintQuality = data.at("hint_quality").get<double>();
        manifest.despill = data.at("despill").get<double>();
        for (auto it = data.at("outputs").begin(); it != data.at("outputs").end(); ++it) {
            OutputInfo output = parseOutput(*it);
            output.kind = it.key();
            manifest.outputs[it.key()] = output;
        }
    } catch (const std::exception&) {
        return false;
    }
    return true;
}

std::string formatPattern(const std::string& pattern, int frame) {
    std::string out;
    size_t i = 0;
    bool done = false;
    while (i < pattern.size()) {
        if (!done && pattern[i] == '%') {
            size_t j = i + 1;
            bool zero = false;
            if (j < pattern.size() && pattern[j] == '0') {
                zero = true;
                ++j;
            }
            int width = 0;
            while (j < pattern.size() && pattern[j] >= '0' && pattern[j] <= '9') width = width * 10 + (pattern[j++] - '0');
            if (j < pattern.size() && pattern[j] == 'd' && width < 32) {
                std::string digits = std::to_string(frame < 0 ? -frame : frame);
                while ((int)digits.size() < width - (frame < 0 ? 1 : 0)) digits.insert(digits.begin(), zero ? '0' : ' ');
                if (frame < 0) digits.insert(digits.begin(), '-');
                out += digits;
                i = j + 1;
                done = true;
                continue;
            }
        }
        out += pattern[i++];
    }
    return out;
}

fs::path outputFramePath(const fs::path& dir, const OutputInfo& output, int index) {
    fs::path file = u8path(formatPattern(output.pattern, output.firstFrame + index));
    return file.is_absolute() ? file : dir / file;
}

CacheState evaluateCache(const std::string& dir, const std::string& token, bool manifestLoaded,
                         const Manifest& manifest, const KeyRequest& current) {
    if (token.empty() || dir.empty()) return CacheState::NotKeyed;
    if (!manifestLoaded) return CacheState::Missing;
    if (manifest.token != token) return CacheState::Stale;
    if (manifest.first != current.first || manifest.last != current.last) return CacheState::Stale;
    if (std::fabs(manifest.hintQuality - current.hintQuality) > 1e-6) return CacheState::Stale;
    if (std::fabs(manifest.despill - current.despill) > 1e-6) return CacheState::Stale;
    return CacheState::Ready;
}

bool clearCacheDir(const fs::path& dir) {
    if (dir.empty() || u8string(dir.filename()).rfind(kDirPrefix, 0) != 0) return false;
    std::error_code ec;
    if (!fs::exists(dir, ec)) return true;
    fs::remove_all(dir, ec);
    return !ec;
}

}
