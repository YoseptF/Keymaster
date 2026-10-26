#include "check.hpp"
#include "i18n.hpp"

using namespace km;

int main() {
    fs::path src = fs::path(KM_SOURCE_DIR);
    fs::path dir = fs::path(KM_TEST_TMP) / "i18n";
    fs::remove_all(dir);
    fs::create_directories(dir / "openfx");
    fs::create_directories(dir / "core");
    for (const char* lang : {"en.json", "es-419.json"}) {
        fs::copy_file(src / "i18n" / lang, dir / "openfx" / lang);
    }
    writeFile(dir / "core" / "en.json", R"({"core.progress.stage1": "Refining", "core.error.x": "Bad {name}", "core.empty": ""})");
    writeFile(dir / "core" / "es-419.json", R"({"core.progress.stage1": "Refinando", "core.empty": ""})");

    std::map<std::string, std::string> en, es;
    CHECK(loadTable(src / "i18n" / "en.json", en));
    CHECK(loadTable(src / "i18n" / "es-419.json", es));
    CHECK_EQ(en.size(), es.size());
    for (const auto& item : en) CHECK(es.count(item.first) == 1);
    CHECK(!loadTable(dir / "missing.json", en));

    Translator t;
    t.load(dir, "es-419");
    CHECK_EQ(t.language(), std::string("es-419"));
    CHECK_EQ(t.text("openfx.param.output.label"), std::string("Salida"));
    CHECK_EQ(t.text("core.progress.stage1"), std::string("Refinando"));
    CHECK_EQ(t.text("core.error.x"), std::string("Bad {name}"));
    CHECK_EQ(t.text("core.empty"), std::string("core.empty"));
    CHECK_EQ(t.lookup("core.empty"), std::string());
    CHECK_EQ(t.text("openfx.nope"), std::string("openfx.nope"));

    t.load(dir, "en");
    CHECK_EQ(t.text("openfx.param.output.label"), std::string("Output"));
    CHECK_EQ(t.text("core.progress.stage1"), std::string("Refining"));

    nlohmann::json params = {{"name", "GPU"}, {"frame", 12}};
    CHECK_EQ(formatText("Bad {name} at {frame} {other}", params), std::string("Bad GPU at 12 {other}"));
    CHECK_EQ(formatText("no {params}", nlohmann::json::object()), std::string("no {params}"));
    CHECK_EQ(formatText("{unclosed", params), std::string("{unclosed"));

    translator().load(dir, "es-419");
    CHECK_EQ(trCore("core.progress.stage1", nlohmann::json::object(), "fb"), std::string("Refinando"));
    CHECK_EQ(trCore("core.empty", nlohmann::json::object(), "fb"), std::string("fb"));
    CHECK_EQ(trCore("core.error.x", {{"name", "A"}}, "fb"), std::string("Bad A"));
    CHECK_EQ(tr("openfx.error.fetch_failed", {{"frame", 7}}),
             std::string("No se pudo leer el fotograma 7 del clip de origen desde el programa."));
    return finish("i18n");
}
