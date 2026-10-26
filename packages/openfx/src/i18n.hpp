#pragma once

#include <map>
#include <string>

#include <nlohmann/json.hpp>

#include "paths.hpp"

namespace km {

class Translator {
public:
    void load(const fs::path& i18nDir, const std::string& language);
    std::string lookup(const std::string& key) const;
    std::string text(const std::string& key) const;
    const std::string& language() const { return language_; }
    size_t size() const { return primary_.size() + fallback_.size(); }

private:
    std::string language_ = "en";
    std::map<std::string, std::string> primary_;
    std::map<std::string, std::string> fallback_;
};

bool loadTable(const fs::path& file, std::map<std::string, std::string>& into);
std::string formatText(const std::string& text, const nlohmann::json& params);

Translator& translator();
void initTranslator();
std::string tr(const char* key);
std::string tr(const char* key, const nlohmann::json& params);
std::string trCore(const std::string& key, const nlohmann::json& params, const std::string& fallback);

}
