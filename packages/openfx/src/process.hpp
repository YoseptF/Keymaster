#pragma once

#include <functional>
#include <string>
#include <vector>

#include "paths.hpp"

namespace km {

struct RunResult {
    bool started = false;
    bool cancelled = false;
    int exitCode = -1;
    std::string error;
};

using LineFn = std::function<void(const std::string&)>;
using CancelFn = std::function<bool()>;

RunResult runProcess(const std::vector<std::string>& argv, const std::string& cwd, const fs::path& stderrLog,
                     const LineFn& onLine, const CancelFn& shouldCancel);
bool keepChildEnv(const std::string& name);

}
