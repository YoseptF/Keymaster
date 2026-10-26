#pragma once

#include <string>
#include <vector>

#include <nlohmann/json.hpp>

namespace km {

struct OutputInfo {
    std::string kind;
    std::string type;
    std::string path;
    std::string pattern;
    int firstFrame = 0;
    int frames = 0;
};

enum class EventKind { Unknown, Start, Progress, Output, Done, Error };

struct Event {
    EventKind kind = EventKind::Unknown;
    std::string phase;
    double fraction = 0.0;
    std::string messageKey;
    std::string detail;
    nlohmann::json params = nlohmann::json::object();
    int frames = 0;
    int width = 0;
    int height = 0;
    OutputInfo output;
    std::vector<OutputInfo> outputs;
};

bool parseEvent(const std::string& line, Event& event);
OutputInfo parseOutput(const nlohmann::json& data);

}
