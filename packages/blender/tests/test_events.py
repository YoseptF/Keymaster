import unittest

from keymaster import events


class ParseLine(unittest.TestCase):
    def test_parses_json_events(self):
        self.assertEqual(events.parse_line('{"event": "start", "frames": 3}\n'), {"event": "start", "frames": 3})

    def test_ignores_noise(self):
        for line in ("", "   ", "hello", "{not json", "[1, 2]", '{"no_event": 1}', '{"event": 3}'):
            self.assertIsNone(events.parse_line(line), line)


class State(unittest.TestCase):
    def run_events(self, items, code=0, cancelled=False):
        state = events.RunState()
        state.begin()
        for item in items:
            state.apply(item)
        state.finish(code, cancelled=cancelled)
        return state

    def test_success(self):
        out = {"event": "output", "kind": "cutout", "type": "image_sequence", "path": "/x", "pattern": "/x/c_%06d.exr",
               "first_frame": 0, "frames": 2}
        state = self.run_events([
            {"event": "start", "frames": 2},
            {"event": "progress", "phase": "stage1", "fraction": 0.4, "message_key": "core.progress.stage1"},
            out,
            {"event": "done", "outputs": [out], "seconds": 1.0},
        ])
        self.assertEqual(state.status, events.DONE)
        self.assertEqual(state.fraction, 1.0)
        self.assertEqual(state.message_key, "core.progress.stage1")
        self.assertEqual(state.final_outputs(), [out])

    def test_fraction_only_grows(self):
        state = events.RunState()
        state.apply({"event": "progress", "fraction": 0.5, "message_key": "core.progress.stage1"})
        state.apply({"event": "progress", "fraction": 0.2, "message_key": "core.progress.stage2"})
        state.apply({"event": "progress", "fraction": "bad"})
        self.assertEqual(state.fraction, 0.5)
        self.assertEqual(state.message_key, "core.progress.stage2")

    def test_outputs_without_done_list(self):
        out = {"event": "output", "kind": "alpha"}
        state = self.run_events([out, {"event": "done", "outputs": []}])
        self.assertEqual(state.final_outputs(), [out])

    def test_error_event(self):
        state = self.run_events([{"event": "error", "message_key": "core.error.no_gpu", "params": {"a": 1},
                                  "detail": "boom"}], code=1)
        self.assertEqual(state.status, events.FAILED)
        self.assertEqual(state.error, {"message_key": "core.error.no_gpu", "params": {"a": 1}, "detail": "boom"})

    def test_crash_without_error_event(self):
        state = events.RunState()
        state.finish(2, detail="Traceback")
        self.assertEqual(state.status, events.FAILED)
        self.assertIsNone(state.error["message_key"])
        self.assertEqual(state.error["detail"], "Traceback")

    def test_error_with_exit_zero_is_failure(self):
        state = self.run_events([{"event": "error", "message_key": "core.error.x"}], code=0)
        self.assertEqual(state.status, events.FAILED)

    def test_cancel(self):
        self.assertEqual(self.run_events([], code=-15, cancelled=True).status, events.CANCELLED)
        self.assertEqual(self.run_events([], code=130).status, events.CANCELLED)

    def test_doctor(self):
        report = {"event": "doctor", "ok": True, "checks": []}
        self.assertEqual(self.run_events([report]).doctor, report)


if __name__ == "__main__":
    unittest.main()
