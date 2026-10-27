#include "events.hpp"

namespace km {

static std::string str(const nlohmann::json& data, const char* key) {
    auto it = data.find(key);
    return it != data.end() && it->is_string() ? it->get<std::string>() : std::string();
}

static int integer(const nlohmann::json& data, const char* key) {
    auto it = data.find(key);
    return it != data.end() && it->is_number() ? (int)it->get<double>() : 0;
}

OutputInfo parseOutput(const nlohmann::json& data) {
    OutputInfo info;
    if (!data.is_object()) return info;
    info.kind = str(data, "kind");
    info.type = str(data, "type");
    info.path = str(data, "path");
    info.pattern = str(data, "pattern");
    info.firstFrame = integer(data, "first_frame");
    info.frames = integer(data, "frames");
    return info;
}

bool parseEvent(const std::string& line, Event& event) {
    event = Event();
    nlohmann::json data = nlohmann::json::parse(line, nullptr, false);
    if (data.is_discarded() || !data.is_object()) return false;
    std::string name = str(data, "event");
    if (name == "start") {
        event.kind = EventKind::Start;
        event.frames = integer(data, "frames");
        event.width = integer(data, "width");
        event.height = integer(data, "height");
    } else if (name == "progress") {
        event.kind = EventKind::Progress;
        event.phase = str(data, "phase");
        event.messageKey = str(data, "message_key");
        auto it = data.find("fraction");
        if (it != data.end() && it->is_number()) event.fraction = it->get<double>();
        if (event.fraction < 0.0) event.fraction = 0.0;
        if (event.fraction > 1.0) event.fraction = 1.0;
    } else if (name == "output") {
        event.kind = EventKind::Output;
        event.output = parseOutput(data);
    } else if (name == "done") {
        event.kind = EventKind::Done;
        auto it = data.find("outputs");
        if (it != data.end() && it->is_array()) {
            for (const auto& item : *it) event.outputs.push_back(parseOutput(item));
        }
    } else if (name == "error") {
        event.kind = EventKind::Error;
        event.messageKey = str(data, "message_key");
        event.detail = str(data, "detail");
        auto it = data.find("params");
        if (it != data.end() && it->is_object()) event.params = *it;
    } else {
        return false;
    }
    return true;
}

}
