#pragma once

#include <filesystem>
#include <functional>
#include <string>

namespace km {

namespace fs = std::filesystem;

using EnvFn = std::function<std::string(const std::string&)>;

fs::path u8path(const std::string& text);
std::string u8string(const fs::path& path);
std::string getEnv(const std::string& name);
EnvFn processEnv();
bool readFile(const fs::path& path, std::string& out);
bool writeFile(const fs::path& path, const std::string& data);
bool writeFileAtomic(const fs::path& path, const std::string& data);
fs::path moduleDir();
fs::path resourcesDir();

}
