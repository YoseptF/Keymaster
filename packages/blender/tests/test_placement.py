import unittest

from keymaster import placement
from keymaster.placement import SourceTiming, Window


def src(start=10, frames=30, trim_start=0, trim_end=0, left=None, right=None, channel=2):
    content_start = start + trim_start
    content_end = start + frames - trim_end
    return SourceTiming(channel=channel, content_start=content_start, content_end=content_end, trim_start=trim_start,
                        left=content_start if left is None else left, right=content_end if right is None else right)


def output(kind, frames=30, first=0, kind_type="image_sequence"):
    item = {"event": "output", "kind": kind, "type": kind_type, "first_frame": first, "frames": frames}
    if kind_type == "image_sequence":
        item.update(path=f"/out/{kind}", pattern=f"/out/{kind}/{kind}_%06d.exr")
    else:
        item.update(path=f"/out/{kind}.mov")
    return item


class Window_(unittest.TestCase):
    def test_untrimmed_matches_source(self):
        self.assertEqual(placement.output_window(src(), 0, 30), Window(start=10, left=10, right=40))

    def test_handles_are_mirrored(self):
        self.assertEqual(placement.output_window(src(left=15, right=33), 0, 30), Window(10, 15, 33))

    def test_content_trim_keeps_frame_alignment(self):
        s = src(trim_start=3, left=16, right=35)
        self.assertEqual(s.content_start, 13)
        self.assertEqual(placement.output_window(s, 0, 30), Window(10, 16, 35))

    def test_holds_are_mirrored_when_output_covers_content(self):
        self.assertEqual(placement.output_window(src(left=4, right=50), 0, 30), Window(10, 4, 50))

    def test_partial_output_is_clamped(self):
        self.assertEqual(placement.output_window(src(left=4, right=50), 5, 10), Window(15, 15, 25))

    def test_output_shorter_than_visible_range(self):
        self.assertEqual(placement.output_window(src(left=16, right=35), 0, 25), Window(10, 16, 35))
        self.assertEqual(placement.output_window(src(left=16, right=35), 0, 20), Window(10, 16, 30))

    def test_nothing_visible(self):
        self.assertIsNone(placement.output_window(src(left=20, right=30), 0, 5))
        self.assertIsNone(placement.output_window(src(), 0, 0))


class FramesNeeded(unittest.TestCase):
    def test_full_strip(self):
        self.assertEqual(placement.frames_needed(src(), 30), 30)

    def test_end_trim_skips_unseen_frames(self):
        self.assertEqual(placement.frames_needed(src(trim_start=3, left=16, right=35), 30), 25)

    def test_end_hold_needs_everything(self):
        self.assertEqual(placement.frames_needed(src(right=60), 30), 30)

    def test_unknown_total(self):
        self.assertIsNone(placement.frames_needed(src(), 0))


class Channels(unittest.TestCase):
    def test_first_free_channel_above(self):
        occupied = [(2, 10, 40), (3, 0, 12), (4, 50, 60)]
        self.assertEqual(placement.free_channel(occupied, 2, 10, 40), 4)
        self.assertEqual(placement.free_channel(occupied, 2, 12, 40), 3)

    def test_touching_strips_do_not_overlap(self):
        self.assertEqual(placement.free_channel([(3, 0, 10)], 2, 10, 20), 3)

    def test_no_room(self):
        self.assertIsNone(placement.free_channel([(c, 0, 100) for c in range(1, 129)], 2, 10, 20))


class Plan(unittest.TestCase):
    def test_cutout_only_by_default(self):
        outs = [output("alpha"), output("fg"), output("cutout")]
        planned, skipped = placement.plan(outs, src(), [(2, 10, 40)], add_extra=False)
        self.assertEqual([p.kind for p in planned], ["cutout"])
        cut = planned[0]
        self.assertEqual((cut.channel, cut.blend, cut.mute, cut.straight_alpha), (3, "ALPHA_OVER", False, True))
        self.assertEqual(cut.path, "/out/cutout")
        self.assertEqual(cut.files[:2], ["cutout_000000.exr", "cutout_000001.exr"])
        self.assertEqual(len(cut.files), 30)
        self.assertEqual(skipped, [])

    def test_extras_stack_above_and_are_muted(self):
        outs = [output("alpha"), output("fg"), output("cutout"), output("checker")]
        planned, _ = placement.plan(outs, src(), [(2, 10, 40), (4, 0, 100)], add_extra=True)
        self.assertEqual([(p.kind, p.channel, p.mute) for p in planned],
                         [("cutout", 3, False), ("alpha", 5, True), ("fg", 6, True), ("checker", 7, True)])
        self.assertTrue(all(p.blend == "REPLACE" for p in planned[1:]))

    def test_video_outputs(self):
        planned, _ = placement.plan([output("cutout", kind_type="video")], src(), [], add_extra=False)
        self.assertEqual((planned[0].type, planned[0].path, planned[0].files), ("video", "/out/cutout.mov", []))

    def test_sequence_files_follow_first_frame(self):
        self.assertEqual(placement.sequence_files(output("alpha", frames=2, first=7)),
                         ["alpha_000007.exr", "alpha_000008.exr"])

    def test_unplaceable_outputs_are_reported(self):
        planned, skipped = placement.plan([output("cutout", frames=0)], src(), [], add_extra=False)
        self.assertEqual((planned, [o["kind"] for o in skipped]), ([], ["cutout"]))


if __name__ == "__main__":
    unittest.main()
