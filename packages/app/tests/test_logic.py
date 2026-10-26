from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

from keymaster_app import clips, settings
from keymaster_app.commands import KeyOptions, doctor_command, key_command
from keymaster_app.i18n import Translator, install
from keymaster_app.media import collect_inputs, output_dir_for, preview_source
from keymaster_app.runner import RunResult, parse_event
from keymaster_app.texts import check_text, error_text, status_text

from tests.helpers import APP, REPO, TempEnv


class SettingsTest(TempEnv):
    def test_default_path_follows_xdg(self) -> None:
        os.environ.pop("KEYMASTER_SETTINGS")
        os.environ["XDG_CONFIG_HOME"] = str(self.tmp / "cfg")
        if sys.platform != "win32":
            self.assertEqual(settings.settings_path(), self.tmp / "cfg" / "keymaster" / "settings.json")

    def test_missing_file_resolves_defaults(self) -> None:
        resolved = settings.resolve()
        self.assertEqual(resolved.language, "en")
        self.assertEqual(resolved.python, sys.executable)
        self.assertIsNone(resolved.core)
        self.assertEqual(settings.core_problem(resolved), "core")

    def test_save_language_keeps_other_keys(self) -> None:
        Path(os.environ["KEYMASTER_SETTINGS"]).write_text(json.dumps({"python": "/x/python", "core": "/x/core"}))
        settings.save_language("es-419")
        data = json.loads(Path(os.environ["KEYMASTER_SETTINGS"]).read_text())
        self.assertEqual(data, {"python": "/x/python", "core": "/x/core", "language": "es-419"})
        self.assertEqual(settings.resolve().language, "es-419")

    def test_unknown_language_falls_back_to_english(self) -> None:
        self.assertEqual(settings.normalize_language("fr"), "en")
        self.assertEqual(settings.normalize_language(None), "en")
        self.assertEqual(settings.normalize_language("ES-419"), "es-419")

    def test_environment_overrides_file(self) -> None:
        settings.save({"python": "/file/python", "core": "/file/core", "language": "en"})
        os.environ["KEYMASTER_PYTHON"] = "/env/python"
        os.environ["KEYMASTER_CORE"] = "/env/core"
        os.environ["KEYMASTER_LANGUAGE"] = "es-419"
        resolved = settings.resolve()
        self.assertEqual((resolved.python, resolved.core, resolved.language), ("/env/python", "/env/core", "es-419"))

    def test_fake_core_has_no_problem(self) -> None:
        self.use_fake_core()
        self.assertIsNone(settings.core_problem(settings.resolve()))


class TranslatorTest(TempEnv):
    def tearDown(self) -> None:
        install(Translator("en"))
        super().tearDown()

    def test_tables_match(self) -> None:
        en = json.loads((APP / "i18n" / "en.json").read_text(encoding="utf-8"))
        es = json.loads((APP / "i18n" / "es-419.json").read_text(encoding="utf-8"))
        self.assertEqual(set(en), set(es))

    def test_switch_and_params(self) -> None:
        tr = Translator("en")
        self.assertEqual(tr("app.start"), "Start")
        tr.set_language("es-419")
        self.assertEqual(tr("app.start"), "Iniciar")
        self.assertIn("3", tr("app.notice.skipped", count=3))
        self.assertEqual(tr("app.not.a.key"), "app.not.a.key")

    def test_missing_param_left_visible(self) -> None:
        self.assertIn("{count}", Translator("en")("app.notice.skipped"))

    def test_core_table_priority(self) -> None:
        app_root = self.tmp / "app"
        (app_root / "i18n" / "core").mkdir(parents=True)
        core = self.tmp / "core"
        (core / "i18n").mkdir(parents=True)
        (app_root / "i18n" / "en.json").write_text(json.dumps({"app.x": "x"}))
        (app_root / "i18n" / "core" / "en.json").write_text(json.dumps({"core.a": "bundled", "core.b": "bundled b"}))
        (app_root / "i18n" / "core" / "es-419.json").write_text(json.dumps({"core.b": "b empaquetado"}))
        (core / "i18n" / "en.json").write_text(json.dumps({"core.a": "installed"}))
        tr = Translator("en", core_dir=str(core), app_root=app_root)
        self.assertEqual(tr("core.a"), "installed")
        self.assertEqual(tr("core.b"), "bundled b")
        tr.set_language("es-419")
        self.assertEqual(tr("core.b"), "b empaquetado")
        self.assertEqual(tr("core.a"), "installed")

    def test_dev_checkout_reads_core_tables(self) -> None:
        tr = Translator("en")
        self.assertIn(REPO / "packages" / "core" / "i18n", tr.table_dirs())


class CommandTest(unittest.TestCase):
    def test_key_command(self) -> None:
        opts = KeyOptions(hint_quality=0.8, despill=0.25, outputs=("cutout", "alpha"), format="video", low_vram=True)
        cmd = key_command("/py", "/in/a.mp4", "/out", opts, hint="/in/hint.png")
        self.assertEqual(cmd[:4], ["/py", "-m", "keymaster", "key"])
        self.assertEqual(cmd[cmd.index("--input") + 1], os.path.abspath("/in/a.mp4"))
        self.assertEqual(cmd[cmd.index("--hint-first-frame") + 1], os.path.abspath("/in/hint.png"))
        self.assertEqual(cmd[cmd.index("--hint-quality") + 1], "0.8")
        self.assertEqual(cmd[cmd.index("--despill") + 1], "0.25")
        self.assertEqual(cmd[cmd.index("--format") + 1], "video")
        i = cmd.index("--outputs")
        self.assertEqual(cmd[i + 1:i + 3], ["alpha", "cutout"])
        self.assertIn("--low-vram", cmd)
        self.assertEqual(cmd[-1], "--json")

    def test_defaults_without_hint(self) -> None:
        cmd = key_command("/py", "rel/clip.mov", "rel/out", KeyOptions())
        self.assertNotIn("--hint-first-frame", cmd)
        self.assertNotIn("--low-vram", cmd)
        self.assertTrue(os.path.isabs(cmd[cmd.index("--output-dir") + 1]))
        i = cmd.index("--outputs")
        self.assertEqual(cmd[i + 1:i + 4], ["alpha", "fg", "cutout"])

    def test_options_validate(self) -> None:
        self.assertIsNone(KeyOptions().validate())
        self.assertEqual(KeyOptions(outputs=()).validate(), "no_outputs")

    def test_doctor_command(self) -> None:
        self.assertEqual(doctor_command("/py"), ["/py", "-m", "keymaster", "doctor", "--json"])


class MediaTest(TempEnv):
    def test_collect_inputs(self) -> None:
        video = self.make_video()
        frames = self.make_frames()
        loose = self.tmp / "clips" / "notes.txt"
        loose.write_text("x")
        videos_dir = self.tmp / "batch"
        videos_dir.mkdir()
        (videos_dir / "b.mov").write_bytes(b"x")
        (videos_dir / "a.MP4").write_bytes(b"x")
        found, skipped = collect_inputs([str(video), str(frames), str(next(frames.iterdir())), str(loose), str(videos_dir)])
        self.assertEqual(found, [str(video), str(frames), str(videos_dir / "a.MP4"), str(videos_dir / "b.mov")])
        self.assertEqual(skipped, [str(loose)])

    def test_output_dir(self) -> None:
        video = self.make_video("take 1.mp4")
        frames = self.make_frames("plate")
        self.assertEqual(output_dir_for(str(video)), str(video.parent / "take 1_keyed"))
        self.assertEqual(output_dir_for(str(frames)), str(frames.parent / "plate_keyed"))
        self.assertEqual(output_dir_for(str(video), str(self.tmp / "out")), str(self.tmp / "out" / "take 1_keyed"))

    def test_preview_source(self) -> None:
        seq = self.tmp / "out" / "shot_cutout"
        seq.mkdir(parents=True)
        (seq / "cutout_000005.png").write_bytes(b"x")
        outputs = [
            {"kind": "alpha", "type": "image_sequence", "path": str(self.tmp), "pattern": str(self.tmp / "nope_%06d.png")},
            {"kind": "cutout", "type": "image_sequence", "path": str(seq), "pattern": str(seq / "cutout_%06d.png"), "first_frame": 5},
        ]
        self.assertEqual(preview_source(outputs), str(seq / "cutout_000005.png"))
        self.assertIsNone(preview_source([{"kind": "cutout", "type": "video", "path": str(seq)}]))


class QueueTest(unittest.TestCase):
    def setUp(self) -> None:
        install(Translator("en"))

    def test_add_dedupes(self) -> None:
        q = clips.ClipQueue()
        self.assertEqual(len(q.add(["/a.mp4", "/b.mp4", "/a.mp4"])), 2)
        self.assertEqual(len(q.add(["/b.mp4"])), 0)
        self.assertEqual([c.id for c in q.clips], [1, 2])

    def test_lifecycle(self) -> None:
        q = clips.ClipQueue()
        a, b = q.add(["/a.mp4", "/b.mp4"])
        first = q.next_pending()
        self.assertIs(first, a)
        self.assertEqual(a.status, clips.RUNNING)
        self.assertEqual(q.remove([a.id]), [])
        q.apply(a.id, {"event": "start", "frames": 10})
        q.apply(a.id, {"event": "progress", "phase": "stage1", "fraction": 0.5, "message_key": "core.progress.stage1"})
        q.apply(a.id, {"event": "progress", "phase": "stage1", "fraction": 0.4, "message_key": "core.progress.stage1"})
        self.assertEqual(a.progress, 0.5)
        self.assertEqual(q.overall(), 0.25)
        tr = Translator("en")
        expected = tr("core.progress.stage1") if tr.has("core.progress.stage1") else "Keying, pass 1 of 2"
        self.assertEqual(status_text(a), expected)
        out = {"event": "output", "kind": "cutout", "type": "video", "path": "/o/a_cutout.mov"}
        q.apply(a.id, out)
        q.apply(a.id, {"event": "done", "outputs": [out], "seconds": 3})
        q.finish(a.id, RunResult(code=0, cancelled=False, events=[{"event": "done"}]))
        self.assertEqual(a.status, clips.DONE)
        self.assertEqual(q.overall(), 0.5)
        self.assertEqual(status_text(a), "Done")
        self.assertIs(q.next_pending(), b)
        q.apply(b.id, {"event": "error", "message_key": "core.error.no_gpu", "params": {}, "detail": "boom"})
        q.finish(b.id, RunResult(code=1, cancelled=False, events=[]))
        self.assertEqual(b.status, clips.FAILED)
        self.assertEqual(b.error["detail"], "boom")
        self.assertIsNone(q.next_pending())
        self.assertEqual(q.prepare_run(), 1)
        self.assertEqual(b.status, clips.QUEUED)
        self.assertIsNone(b.error)
        self.assertEqual(q.clear_finished(), [a.id])

    def test_cancel_and_launch_failure(self) -> None:
        q = clips.ClipQueue()
        a, b = q.add(["/a.mp4", "/b.mp4"])
        q.next_pending()
        q.finish(a.id, RunResult(code=-15, cancelled=True))
        self.assertEqual(a.status, clips.CANCELLED)
        q.next_pending()
        q.finish(b.id, RunResult(code=None, cancelled=False, launch_error="no such file"))
        self.assertEqual(b.status, clips.FAILED)
        self.assertEqual(status_text(b), Translator("en")("app.error.launch"))

    def test_set_hint(self) -> None:
        q = clips.ClipQueue()
        (a,) = q.add(["/a.mp4"])
        self.assertTrue(q.set_hint(a.id, "/h.png"))
        self.assertEqual(a.hint, os.path.abspath("/h.png"))
        self.assertTrue(q.set_hint(a.id, None))
        self.assertIsNone(a.hint)


class TextTest(unittest.TestCase):
    def setUp(self) -> None:
        install(Translator("en"))

    def tearDown(self) -> None:
        install(Translator("en"))

    def test_error_fallbacks(self) -> None:
        self.assertEqual(error_text({"message_key": "core.error.zzz_unknown", "params": {}}), "Failed (zzz_unknown)")
        self.assertIn("7", error_text({"message_key": "", "code": 7}))
        self.assertEqual(error_text(None), "Something went wrong")

    def test_core_keys_win_when_known(self) -> None:
        tr = install(Translator("en"))
        tr.table["core.error.no_gpu"] = "No GPU {name}"
        self.assertEqual(error_text({"message_key": "core.error.no_gpu", "params": {"name": "x"}}), "No GPU x")

    def test_doctor_fallback(self) -> None:
        self.assertEqual(check_text({"id": "gpu", "ok": True, "message_key": "core.doctor.zzz"}), "NVIDIA graphics card: ready")
        install(Translator("es-419"))
        self.assertEqual(check_text({"id": "ffmpeg", "ok": False, "message_key": "core.doctor.zzz"}), "FFmpeg: falta")


class ParseTest(unittest.TestCase):
    def test_parse_event(self) -> None:
        self.assertEqual(parse_event('{"event": "start", "frames": 1}\n'), {"event": "start", "frames": 1})
        self.assertIsNone(parse_event("loading torch...\n"))
        self.assertIsNone(parse_event('{"no": "event"}'))
        self.assertIsNone(parse_event("{broken"))


if __name__ == "__main__":
    unittest.main()
