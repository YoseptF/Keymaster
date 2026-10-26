#include "paths.hpp"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <system_error>

#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace km {

#ifdef _WIN32
static std::wstring widen(const std::string& text) {
    if (text.empty()) return std::wstring();
    int n = MultiByteToWideChar(CP_UTF8, 0, text.data(), (int)text.size(), nullptr, 0);
    std::wstring out(n, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, text.data(), (int)text.size(), out.data(), n);
    return out;
}

static std::string narrow(const std::wstring& text) {
    if (text.empty()) return std::string();
    int n = WideCharToMultiByte(CP_UTF8, 0, text.data(), (int)text.size(), nullptr, 0, nullptr, nullptr);
    std::string out(n, '\0');
    WideCharToMultiByte(CP_UTF8, 0, text.data(), (int)text.size(), out.data(), n, nullptr, nullptr);
    return out;
}
#endif

fs::path u8path(const std::string& text) {
#ifdef _WIN32
    return fs::path(widen(text));
#else
    return fs::path(text);
#endif
}

std::string u8string(const fs::path& path) {
#ifdef _WIN32
    return narrow(path.wstring());
#else
    return path.string();
#endif
}

std::string getEnv(const std::string& name) {
#ifdef _WIN32
    std::wstring wname = widen(name);
    DWORD n = GetEnvironmentVariableW(wname.c_str(), nullptr, 0);
    if (n == 0) return std::string();
    std::wstring value(n, L'\0');
    DWORD got = GetEnvironmentVariableW(wname.c_str(), value.data(), n);
    value.resize(got);
    return narrow(value);
#else
    const char* value = std::getenv(name.c_str());
    return value ? std::string(value) : std::string();
#endif
}

EnvFn processEnv() {
    return [](const std::string& name) { return getEnv(name); };
}

bool readFile(const fs::path& path, std::string& out) {
    std::ifstream in(path, std::ios::binary);
    if (!in) return false;
    std::ostringstream buffer;
    buffer << in.rdbuf();
    out = buffer.str();
    return true;
}

bool writeFile(const fs::path& path, const std::string& data) {
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    if (!out) return false;
    out.write(data.data(), (std::streamsize)data.size());
    return (bool)out;
}

bool writeFileAtomic(const fs::path& path, const std::string& data) {
    fs::path tmp = path;
    tmp += ".tmp";
    if (!writeFile(tmp, data)) return false;
    std::error_code ec;
    fs::rename(tmp, path, ec);
    if (ec) {
        fs::remove(tmp, ec);
        return false;
    }
    return true;
}

fs::path moduleDir() {
#ifdef _WIN32
    HMODULE module = nullptr;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                            reinterpret_cast<LPCWSTR>(&moduleDir), &module)) {
        return fs::path();
    }
    std::wstring buffer(32768, L'\0');
    DWORD n = GetModuleFileNameW(module, buffer.data(), (DWORD)buffer.size());
    buffer.resize(n);
    return fs::path(buffer).parent_path();
#else
    Dl_info info;
    if (!dladdr(reinterpret_cast<void*>(&moduleDir), &info) || !info.dli_fname) return fs::path();
    std::error_code ec;
    fs::path file = fs::weakly_canonical(fs::path(info.dli_fname), ec);
    if (ec) file = fs::path(info.dli_fname);
    return file.parent_path();
#endif
}

fs::path resourcesDir() {
    return moduleDir().parent_path() / "Resources";
}

}
