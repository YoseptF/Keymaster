#include "process.hpp"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cstring>
#include <thread>

#ifdef _WIN32
#include <windows.h>
#else
#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <poll.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
extern char** environ;
#endif

namespace km {

static const char* kDropped[] = {"PYTHONHOME", "PYTHONPATH", "PYTHONEXECUTABLE", "PYTHONSTARTUP",
                                 "PYTHONUSERBASE", "LD_LIBRARY_PATH", "LD_PRELOAD", "PYTHONUNBUFFERED",
                                 "PYTHONIOENCODING", "PYTHONUTF8"};
static const char* kAdded[] = {"PYTHONUNBUFFERED=1", "PYTHONIOENCODING=utf-8", "PYTHONUTF8=1"};

bool keepChildEnv(const std::string& name) {
    std::string upper = name;
#ifdef _WIN32
    std::transform(upper.begin(), upper.end(), upper.begin(), [](unsigned char c) { return (char)std::toupper(c); });
#endif
    for (const char* dropped : kDropped) {
        if (upper == dropped) return false;
    }
    return true;
}

namespace {

struct LineSplitter {
    std::string pending;
    const LineFn& onLine;
    explicit LineSplitter(const LineFn& fn) : onLine(fn) {}
    void feed(const char* data, size_t size) {
        pending.append(data, size);
        size_t start = 0;
        for (;;) {
            size_t end = pending.find('\n', start);
            if (end == std::string::npos) break;
            std::string line = pending.substr(start, end - start);
            if (!line.empty() && line.back() == '\r') line.pop_back();
            if (!line.empty() && onLine) onLine(line);
            start = end + 1;
        }
        pending.erase(0, start);
    }
    void finish() {
        if (!pending.empty() && onLine) onLine(pending);
        pending.clear();
    }
};

}

#ifdef _WIN32

static std::wstring widenText(const std::string& text) {
    return u8path(text).wstring();
}

static std::wstring quoteArg(const std::wstring& arg) {
    if (!arg.empty() && arg.find_first_of(L" \t\n\v\"") == std::wstring::npos) return arg;
    std::wstring out = L"\"";
    for (size_t i = 0;; ++i) {
        size_t slashes = 0;
        while (i < arg.size() && arg[i] == L'\\') {
            ++i;
            ++slashes;
        }
        if (i == arg.size()) {
            out.append(slashes * 2, L'\\');
            break;
        }
        if (arg[i] == L'"') {
            out.append(slashes * 2 + 1, L'\\');
            out.push_back(L'"');
        } else {
            out.append(slashes, L'\\');
            out.push_back(arg[i]);
        }
    }
    out.push_back(L'"');
    return out;
}

static std::wstring buildEnvironment() {
    std::wstring block;
    wchar_t* env = GetEnvironmentStringsW();
    if (env) {
        for (const wchar_t* p = env; *p; p += wcslen(p) + 1) {
            std::wstring entry(p);
            size_t eq = entry.find(L'=', 1);
            std::wstring name = eq == std::wstring::npos ? entry : entry.substr(0, eq);
            if (!keepChildEnv(u8string(fs::path(name)))) continue;
            block += entry;
            block.push_back(L'\0');
        }
        FreeEnvironmentStringsW(env);
    }
    for (const char* added : kAdded) {
        block += widenText(added);
        block.push_back(L'\0');
    }
    block.push_back(L'\0');
    return block;
}

RunResult runProcess(const std::vector<std::string>& argv, const std::string& cwd, const fs::path& stderrLog,
                     const LineFn& onLine, const CancelFn& shouldCancel) {
    RunResult result;
    if (argv.empty()) {
        result.error = "empty command";
        return result;
    }
    SECURITY_ATTRIBUTES sa{sizeof(SECURITY_ATTRIBUTES), nullptr, TRUE};
    HANDLE readPipe = nullptr, writePipe = nullptr;
    if (!CreatePipe(&readPipe, &writePipe, &sa, 0)) {
        result.error = "CreatePipe failed";
        return result;
    }
    SetHandleInformation(readPipe, HANDLE_FLAG_INHERIT, 0);
    HANDLE logFile = CreateFileW(stderrLog.wstring().c_str(), GENERIC_WRITE, FILE_SHARE_READ, &sa, CREATE_ALWAYS,
                                 FILE_ATTRIBUTE_NORMAL, nullptr);
    HANDLE nullIn = CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, OPEN_EXISTING, 0, nullptr);

    STARTUPINFOW si{};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdOutput = writePipe;
    si.hStdError = logFile != INVALID_HANDLE_VALUE ? logFile : writePipe;
    si.hStdInput = nullIn;
    PROCESS_INFORMATION pi{};

    std::wstring commandLine;
    for (size_t i = 0; i < argv.size(); ++i) {
        if (i) commandLine.push_back(L' ');
        commandLine += quoteArg(widenText(argv[i]));
    }
    std::wstring app = widenText(argv[0]);
    std::wstring dir = widenText(cwd);
    std::wstring env = buildEnvironment();
    HANDLE job = CreateJobObjectW(nullptr, nullptr);
    if (job) {
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION info{};
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        SetInformationJobObject(job, JobObjectExtendedLimitInformation, &info, sizeof(info));
    }
    BOOL ok = CreateProcessW(app.c_str(), commandLine.data(), nullptr, nullptr, TRUE,
                             CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW | CREATE_SUSPENDED, env.data(),
                             dir.empty() ? nullptr : dir.c_str(), &si, &pi);
    DWORD startError = ok ? 0 : GetLastError();
    CloseHandle(writePipe);
    if (logFile != INVALID_HANDLE_VALUE) CloseHandle(logFile);
    if (nullIn != INVALID_HANDLE_VALUE) CloseHandle(nullIn);
    if (!ok) {
        CloseHandle(readPipe);
        if (job) CloseHandle(job);
        result.error = "CreateProcess failed with error " + std::to_string(startError);
        return result;
    }
    if (job) AssignProcessToJobObject(job, pi.hProcess);
    ResumeThread(pi.hThread);
    CloseHandle(pi.hThread);
    result.started = true;

    LineSplitter splitter(onLine);
    char buffer[4096];
    bool exited = false;
    for (;;) {
        DWORD available = 0;
        bool pipeOpen = PeekNamedPipe(readPipe, nullptr, 0, nullptr, &available, nullptr) != 0;
        if (pipeOpen && available > 0) {
            DWORD got = 0;
            if (ReadFile(readPipe, buffer, (DWORD)std::min<DWORD>(available, sizeof(buffer)), &got, nullptr) && got > 0) {
                splitter.feed(buffer, got);
                continue;
            }
        }
        if (exited || !pipeOpen) break;
        if (shouldCancel && shouldCancel()) {
            result.cancelled = true;
            if (job) TerminateJobObject(job, 130);
            TerminateProcess(pi.hProcess, 130);
            WaitForSingleObject(pi.hProcess, 5000);
            break;
        }
        if (WaitForSingleObject(pi.hProcess, 50) == WAIT_OBJECT_0) exited = true;
    }
    splitter.finish();
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(pi.hProcess, &code);
    result.exitCode = result.cancelled ? 130 : (int)code;
    CloseHandle(pi.hProcess);
    CloseHandle(readPipe);
    if (job) CloseHandle(job);
    return result;
}

#else

RunResult runProcess(const std::vector<std::string>& argv, const std::string& cwd, const fs::path& stderrLog,
                     const LineFn& onLine, const CancelFn& shouldCancel) {
    RunResult result;
    if (argv.empty()) {
        result.error = "empty command";
        return result;
    }
    std::vector<std::string> envStrings;
    for (char** e = environ; e && *e; ++e) {
        std::string entry(*e);
        std::string name = entry.substr(0, entry.find('='));
        if (keepChildEnv(name)) envStrings.push_back(entry);
    }
    for (const char* added : kAdded) envStrings.emplace_back(added);
    std::vector<char*> envp;
    for (auto& entry : envStrings) envp.push_back(entry.data());
    envp.push_back(nullptr);
    std::vector<std::string> args = argv;
    std::vector<char*> argp;
    for (auto& arg : args) argp.push_back(arg.data());
    argp.push_back(nullptr);
    std::string logName = stderrLog.string();

    int out[2];
    int status[2];
    if (pipe(out) != 0) {
        result.error = std::string("pipe: ") + std::strerror(errno);
        return result;
    }
    if (pipe(status) != 0) {
        close(out[0]);
        close(out[1]);
        result.error = std::string("pipe: ") + std::strerror(errno);
        return result;
    }
    fcntl(out[0], F_SETFD, FD_CLOEXEC);
    fcntl(status[0], F_SETFD, FD_CLOEXEC);
    fcntl(status[1], F_SETFD, FD_CLOEXEC);
    int logFd = open(logName.c_str(), O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC, 0644);
    int nullFd = open("/dev/null", O_RDONLY | O_CLOEXEC);

    pid_t pid = fork();
    if (pid < 0) {
        result.error = std::string("fork: ") + std::strerror(errno);
        close(out[0]);
        close(out[1]);
        close(status[0]);
        close(status[1]);
        if (logFd >= 0) close(logFd);
        if (nullFd >= 0) close(nullFd);
        return result;
    }
    if (pid == 0) {
        setpgid(0, 0);
        if (nullFd >= 0) dup2(nullFd, 0);
        dup2(out[1], 1);
        dup2(logFd >= 0 ? logFd : out[1], 2);
        int err = 0;
        if (!cwd.empty() && chdir(cwd.c_str()) != 0) {
            err = errno;
        } else {
            execve(argp[0], argp.data(), envp.data());
            err = errno;
        }
        ssize_t ignored = write(status[1], &err, sizeof(err));
        (void)ignored;
        _exit(127);
    }
    setpgid(pid, pid);
    close(out[1]);
    close(status[1]);
    if (logFd >= 0) close(logFd);
    if (nullFd >= 0) close(nullFd);

    int childErr = 0;
    ssize_t n;
    do {
        n = read(status[0], &childErr, sizeof(childErr));
    } while (n < 0 && errno == EINTR);
    close(status[0]);
    if (n == (ssize_t)sizeof(childErr)) {
        int ignored;
        waitpid(pid, &ignored, 0);
        close(out[0]);
        result.error = std::string("cannot start ") + argv[0] + ": " + std::strerror(childErr);
        return result;
    }
    result.started = true;

    LineSplitter splitter(onLine);
    char buffer[4096];
    int waitStatus = 0;
    bool exited = false;
    for (;;) {
        pollfd pfd{out[0], POLLIN, 0};
        int ready = poll(&pfd, 1, exited ? 0 : 100);
        if (ready > 0) {
            ssize_t got = read(out[0], buffer, sizeof(buffer));
            if (got > 0) {
                splitter.feed(buffer, (size_t)got);
                continue;
            }
            if (got == 0 || (got < 0 && errno != EINTR && errno != EAGAIN)) break;
        }
        if (exited) break;
        if (shouldCancel && shouldCancel()) {
            result.cancelled = true;
            kill(-pid, SIGTERM);
            auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
            while (std::chrono::steady_clock::now() < deadline) {
                if (waitpid(pid, &waitStatus, WNOHANG) == pid) {
                    exited = true;
                    break;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(50));
            }
            if (!exited) {
                kill(-pid, SIGKILL);
                waitpid(pid, &waitStatus, 0);
                exited = true;
            }
            close(out[0]);
            splitter.finish();
            result.exitCode = 130;
            return result;
        }
        if (!exited && waitpid(pid, &waitStatus, WNOHANG) == pid) exited = true;
    }
    close(out[0]);
    splitter.finish();
    if (!exited) waitpid(pid, &waitStatus, 0);
    if (WIFEXITED(waitStatus)) result.exitCode = WEXITSTATUS(waitStatus);
    else if (WIFSIGNALED(waitStatus)) result.exitCode = 128 + WTERMSIG(waitStatus);
    return result;
}

#endif

}
