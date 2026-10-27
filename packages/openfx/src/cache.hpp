#pragma once

#include <map>
#include <string>

#include "events.hpp"
#include "paths.hpp"

namespace km {

struct Manifest {
    std::string token;
    int first = 0;
    int last = -1;
    int width = 0;
    int height = 0;
    double hintQuality = 0.0;
    double despill = 0.0;
    std::map<std::string, OutputInfo> outputs;
};

enum class CacheState { NotKeyed, Missing, Stale, Ready };

struct KeyRequest {
    std::string token;
    int first = 0;
    int last = -1;
    double hintQuality = 0.0;
    double despill = 0.0;
};

fs::path cacheRoot(const EnvFn& env);
std::string newCacheName();
std::string newToken();
fs::path manifestPath(const fs::path& dir);
fs::path inputDir(const fs::path& dir);
fs::path outputDir(const fs::path& dir);
fs::path logPath(const fs::path& dir);
fs::path inputFramePath(const fs::path& dir, int index);
bool writeManifest(const fs::path& dir, const Manifest& manifest);
bool readManifest(const fs::path& dir, Manifest& manifest);
std::string formatPattern(const std::string& pattern, int frame);
fs::path outputFramePath(const fs::path& dir, const OutputInfo& output, int index);
CacheState evaluateCache(const std::string& dir, const std::string& token, bool manifestLoaded,
                         const Manifest& manifest, const KeyRequest& current);
bool clearCacheDir(const fs::path& dir);

}
