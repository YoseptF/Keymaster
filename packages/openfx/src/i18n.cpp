#include "i18n.hpp"

#include "settings.hpp"

namespace km {

bool loadTable(const fs::path& file, std::map<std::string, std::string>& into) {
    std::string text;
    if (!readFile(file, text)) return false;
    nlohmann::json data = nlohmann::json::parse(text, nullptr, false);
    if (data.is_discarded() || !data.is_object()) return false;
    for (auto it = data.begin(); it != data.end(); ++it) {
        if (it->is_string() && !it->get<std::string>().empty()) into[it.key()] = it->get<std::string>();
    }
    return true;
}

void Translator::load(const fs::path& i18nDir, const std::string& language) {
    language_ = language;
    primary_.clear();
    fallback_.clear();
    for (const char* table : {"openfx", "core"}) {
        loadTable(i18nDir / table / "en.json", fallback_);
        if (language != "en") loadTable(i18nDir / table / (language + ".json"), primary_);
    }
}

std::string Translator::lookup(const std::string& key) const {
    auto it = primary_.find(key);
    if (it != primary_.end()) return it->second;
    it = fallback_.find(key);
    if (it != fallback_.end()) return it->second;
    return std::string();
}

std::string Translator::text(const std::string& key) const {
    std::string found = lookup(key);
    return found.empty() ? key : found;
}

static std::string paramText(const nlohmann::json& value) {
    if (value.is_string()) return value.get<std::string>();
    if (value.is_number_integer()) return std::to_string(value.get<long long>());
    return value.dump();
}

std::string formatText(const std::string& text, const nlohmann::json& params) {
    if (!params.is_object() || params.empty()) return text;
    std::string out;
    size_t i = 0;
    while (i < text.size()) {
        if (text[i] == '{') {
            size_t close = text.find('}', i + 1);
            if (close != std::string::npos) {
                std::string name = text.substr(i + 1, close - i - 1);
                auto it = params.find(name);
                if (it != params.end()) {
                    out += paramText(*it);
                    i = close + 1;
                    continue;
                }
            }
        }
        out += text[i++];
    }
    return out;
}

Translator& translator() {
    static Translator instance;
    return instance;
}

void initTranslator() {
    translator().load(resourcesDir() / "i18n", resolveLanguage());
}

std::string tr(const char* key) {
    return translator().text(key);
}

std::string tr(const char* key, const nlohmann::json& params) {
    return formatText(translator().text(key), params);
}

std::string trCore(const std::string& key, const nlohmann::json& params, const std::string& fallback) {
    std::string found = translator().lookup(key);
    if (found.empty()) return fallback;
    return formatText(found, params);
}

}
