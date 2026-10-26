#include <chrono>
#include <cstdlib>

#include "check.hpp"
#include "events.hpp"
#include "process.hpp"

using namespace km;

static void setVar(const char* name, const char* value) {
#ifdef _WIN32
    _putenv_s(name, value ? value : "");
#else
    if (value) setenv(name, value, 1);
    else unsetenv(name);
#endif
}

int main() {
    fs::path core = fs::path(KM_REPO_ROOT) / "packages" / "core" / "testing" / "fake_core";
    fs::path dir = fs::path(KM_TEST_TMP) / "process";
    fs::remove_all(dir);
    fs::create_directories(dir / "input");
    std::string python = KM_PYTHON;
    CHECK(!python.empty());

    setVar("PYTHONHOME", "/definitely/not/a/python/home");
    setVar("PYTHONPATH", "/nowhere");
    std::vector<std::string> argv = {python, "-m", "keymaster", "key", "--input", (dir / "input").string(),
                                     "--output-dir", (dir / "out").string(), "--format", "exr",
                                     "--outputs", "alpha", "fg", "cutout", "--frames", "3", "--json"};
    std::vector<Event> events;
    RunResult r = runProcess(argv, core.string(), dir / "core.log",
                             [&](const std::string& line) {
                                 Event e;
                                 if (parseEvent(line, e)) events.push_back(e);
                             },
                             [] { return false; });
    CHECK(r.started);
    CHECK(!r.cancelled);
    CHECK_EQ(r.exitCode, 0);
    CHECK(!events.empty());
    CHECK(events.front().kind == EventKind::Start);
    CHECK(events.back().kind == EventKind::Done);
    if (!events.empty()) CHECK_EQ(events.back().outputs.size(), (size_t)3);
    double last = 0.0;
    bool monotonic = true;
    for (const auto& e : events) {
        if (e.kind == EventKind::Progress) {
            monotonic = monotonic && e.fraction >= last;
            last = e.fraction;
        }
    }
    CHECK(monotonic);
    CHECK_EQ(last, 1.0);
    CHECK(fs::exists(dir / "out" / "input_alpha" / "alpha_000002.png"));

    std::vector<std::string> envProbe = {python, "-c", "import os,sys;print(os.environ.get('PYTHONHOME','-')+'|'+os.environ.get('PYTHONUNBUFFERED','-')+'|'+os.getcwd())"};
    std::string seen;
    r = runProcess(envProbe, dir.string(), dir / "probe.log", [&](const std::string& line) { seen = line; }, nullptr);
    CHECK_EQ(r.exitCode, 0);
    CHECK_EQ(seen, std::string("-|1|") + fs::canonical(dir).string());

    setVar("KEYMASTER_FAKE_FAIL", "no_gpu");
    events.clear();
    r = runProcess(argv, core.string(), dir / "core.log",
                   [&](const std::string& line) {
                       Event e;
                       if (parseEvent(line, e)) events.push_back(e);
                   },
                   nullptr);
    CHECK_EQ(r.exitCode, 1);
    CHECK(!events.empty() && events.back().kind == EventKind::Error);
    if (!events.empty()) CHECK_EQ(events.back().messageKey, std::string("core.error.no_gpu"));
    setVar("KEYMASTER_FAKE_FAIL", nullptr);

    setVar("KEYMASTER_FAKE_DELAY", "2");
    int lines = 0;
    auto started = std::chrono::steady_clock::now();
    r = runProcess(argv, core.string(), dir / "core.log", [&](const std::string&) { ++lines; },
                   [&] { return lines >= 1; });
    double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    CHECK(r.cancelled);
    CHECK_EQ(r.exitCode, 130);
    CHECK(seconds < 8.0);
    setVar("KEYMASTER_FAKE_DELAY", nullptr);

    r = runProcess({(dir / "no-such-python").string(), "-V"}, dir.string(), dir / "x.log", nullptr, nullptr);
    CHECK(!r.started);
    CHECK(!r.error.empty());

    CHECK(!keepChildEnv("PYTHONHOME"));
    CHECK(!keepChildEnv("LD_LIBRARY_PATH"));
    CHECK(keepChildEnv("PATH"));
    CHECK(keepChildEnv("KEYMASTER_CORE"));
    return finish("process");
}
