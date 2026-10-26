#include "check.hpp"
#include "events.hpp"

using namespace km;

int main() {
    Event e;
    CHECK(parseEvent(R"({"event": "start", "input": "/x", "frames": 120, "width": 1920, "height": 1080, "fps": 24.0})", e));
    CHECK(e.kind == EventKind::Start);
    CHECK_EQ(e.frames, 120);
    CHECK_EQ(e.width, 1920);
    CHECK_EQ(e.height, 1080);

    CHECK(parseEvent(R"({"event": "progress", "phase": "stage1", "fraction": 0.42, "message_key": "core.progress.stage1"})", e));
    CHECK(e.kind == EventKind::Progress);
    CHECK_EQ(e.phase, std::string("stage1"));
    CHECK(e.fraction > 0.419 && e.fraction < 0.421);
    CHECK_EQ(e.messageKey, std::string("core.progress.stage1"));

    CHECK(parseEvent(R"({"event": "progress", "phase": "write", "fraction": 1.7})", e));
    CHECK_EQ(e.fraction, 1.0);
    CHECK(parseEvent(R"({"event": "progress", "phase": "load", "fraction": -3})", e));
    CHECK_EQ(e.fraction, 0.0);

    CHECK(parseEvent(R"({"event": "output", "kind": "alpha", "type": "image_sequence", "path": "/c/out/a", "pattern": "/c/out/a/alpha_%06d.exr", "first_frame": 0, "frames": 12})", e));
    CHECK(e.kind == EventKind::Output);
    CHECK_EQ(e.output.kind, std::string("alpha"));
    CHECK_EQ(e.output.type, std::string("image_sequence"));
    CHECK_EQ(e.output.pattern, std::string("/c/out/a/alpha_%06d.exr"));
    CHECK_EQ(e.output.frames, 12);

    CHECK(parseEvent(R"({"event": "done", "outputs": [{"event": "output", "kind": "fg", "type": "image_sequence", "path": "p", "pattern": "p/fg_%06d.exr", "first_frame": 1, "frames": 3}, {"kind": "cutout", "type": "video", "path": "v.mov"}], "seconds": 81.2})", e));
    CHECK(e.kind == EventKind::Done);
    CHECK_EQ(e.outputs.size(), (size_t)2);
    CHECK_EQ(e.outputs[0].kind, std::string("fg"));
    CHECK_EQ(e.outputs[0].firstFrame, 1);
    CHECK_EQ(e.outputs[1].type, std::string("video"));

    CHECK(parseEvent(R"({"event": "error", "message_key": "core.error.no_gpu", "params": {"name": "x", "count": 2}, "detail": "boom"})", e));
    CHECK(e.kind == EventKind::Error);
    CHECK_EQ(e.messageKey, std::string("core.error.no_gpu"));
    CHECK_EQ(e.detail, std::string("boom"));
    CHECK_EQ(e.params["count"].get<int>(), 2);

    CHECK(!parseEvent("not json", e));
    CHECK(!parseEvent("", e));
    CHECK(!parseEvent("[1,2]", e));
    CHECK(!parseEvent(R"({"event": "mystery"})", e));
    CHECK(!parseEvent(R"({"no": "event"})", e));
    return finish("events");
}
