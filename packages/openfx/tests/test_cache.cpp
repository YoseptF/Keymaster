#include <map>
#include <set>

#include "cache.hpp"
#include "check.hpp"

using namespace km;

static EnvFn fakeEnv(std::map<std::string, std::string> values) {
    return [values](const std::string& name) {
        auto it = values.find(name);
        return it == values.end() ? std::string() : it->second;
    };
}

int main() {
#ifndef _WIN32
    CHECK_EQ(cacheRoot(fakeEnv({{"HOME", "/home/u"}})), fs::path("/home/u/.cache/keymaster/openfx"));
    CHECK_EQ(cacheRoot(fakeEnv({{"HOME", "/home/u"}, {"XDG_CACHE_HOME", "/c"}})), fs::path("/c/keymaster/openfx"));
#endif
    std::set<std::string> names;
    for (int i = 0; i < 50; ++i) {
        std::string name = newCacheName();
        CHECK(name.rfind("km-", 0) == 0);
        CHECK(name.find('/') == std::string::npos);
        names.insert(name);
    }
    CHECK_EQ(names.size(), (size_t)50);
    CHECK(newToken() != newToken());
    CHECK_EQ(newToken().size(), (size_t)16);

    CHECK_EQ(formatPattern("a/alpha_%06d.exr", 12), std::string("a/alpha_000012.exr"));
    CHECK_EQ(formatPattern("f_%04d.png", 123456), std::string("f_123456.png"));
    CHECK_EQ(formatPattern("f_%d.png", 7), std::string("f_7.png"));
    CHECK_EQ(formatPattern("f_%03d.png", -2), std::string("f_-02.png"));
    CHECK_EQ(formatPattern("100%_%04d_%04d", 3), std::string("100%_0003_%04d"));
    CHECK_EQ(formatPattern("plain.exr", 3), std::string("plain.exr"));

    fs::path dir = fs::path(KM_TEST_TMP) / "cache" / "km-test";
    fs::remove_all(dir.parent_path());
    fs::create_directories(dir);
    CHECK_EQ(inputFramePath(dir, 3), dir / "input" / "frame_000003.exr");

    Manifest m;
    m.token = "abc";
    m.first = 10;
    m.last = 21;
    m.width = 1920;
    m.height = 1080;
    m.hintQuality = 0.95;
    m.despill = 0.5;
    OutputInfo alpha;
    alpha.kind = "alpha";
    alpha.type = "image_sequence";
    alpha.pattern = (dir / "out" / "input_alpha" / "alpha_%06d.exr").string();
    alpha.frames = 12;
    m.outputs["alpha"] = alpha;
    OutputInfo outside = alpha;
    outside.kind = "fg";
    outside.pattern = "/elsewhere/fg_%06d.exr";
    m.outputs["fg"] = outside;
    CHECK(writeManifest(dir, m));

    std::string raw;
    CHECK(readFile(manifestPath(dir), raw));
    CHECK(raw.find("\"out/input_alpha/alpha_%06d.exr\"") != std::string::npos);
    CHECK(raw.find("/elsewhere/fg_%06d.exr") != std::string::npos);

    Manifest back;
    CHECK(readManifest(dir, back));
    CHECK_EQ(back.token, std::string("abc"));
    CHECK_EQ(back.first, 10);
    CHECK_EQ(back.last, 21);
    CHECK_EQ(back.width, 1920);
    CHECK_EQ(back.outputs.size(), (size_t)2);
    CHECK_EQ(outputFramePath(dir, back.outputs["alpha"], 4), dir / "out" / "input_alpha" / "alpha_000004.exr");
    CHECK_EQ(outputFramePath(dir, back.outputs["fg"], 0), fs::path("/elsewhere/fg_000000.exr"));

    fs::path moved = fs::path(KM_TEST_TMP) / "cache" / "km-moved";
    fs::rename(dir, moved);
    Manifest movedBack;
    CHECK(readManifest(moved, movedBack));
    CHECK_EQ(outputFramePath(moved, movedBack.outputs["alpha"], 1), moved / "out" / "input_alpha" / "alpha_000001.exr");

    KeyRequest req{"abc", 10, 21, 0.95, 0.5};
    CHECK(evaluateCache("", "", false, back, req) == CacheState::NotKeyed);
    CHECK(evaluateCache(moved.string(), "", true, back, req) == CacheState::NotKeyed);
    CHECK(evaluateCache(moved.string(), "abc", false, back, req) == CacheState::Missing);
    CHECK(evaluateCache(moved.string(), "abc", true, back, req) == CacheState::Ready);
    CHECK(evaluateCache(moved.string(), "zzz", true, back, req) == CacheState::Stale);
    KeyRequest longer = req;
    longer.last = 30;
    CHECK(evaluateCache(moved.string(), "abc", true, back, longer) == CacheState::Stale);
    KeyRequest shifted = req;
    shifted.first = 0;
    CHECK(evaluateCache(moved.string(), "abc", true, back, shifted) == CacheState::Stale);
    KeyRequest despill = req;
    despill.despill = 0.7;
    CHECK(evaluateCache(moved.string(), "abc", true, back, despill) == CacheState::Stale);
    KeyRequest hint = req;
    hint.hintQuality = 0.5;
    CHECK(evaluateCache(moved.string(), "abc", true, back, hint) == CacheState::Stale);

    writeFile(manifestPath(moved), "{broken");
    Manifest broken;
    CHECK(!readManifest(moved, broken));
    CHECK(!readManifest(fs::path(KM_TEST_TMP) / "cache" / "none", broken));

    fs::path foreign = fs::path(KM_TEST_TMP) / "cache" / "precious";
    fs::create_directories(foreign);
    CHECK(!clearCacheDir(foreign));
    CHECK(fs::exists(foreign));
    CHECK(clearCacheDir(moved));
    CHECK(!fs::exists(moved));
    CHECK(clearCacheDir(fs::path(KM_TEST_TMP) / "cache" / "km-never-made"));
    return finish("cache");
}
