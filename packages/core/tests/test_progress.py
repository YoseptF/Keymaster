from __future__ import annotations

import unittest

from keymaster.progress import PHASES, Tracker


class TrackerTest(unittest.TestCase):
    def test_monotonic_and_bounded(self):
        events = []
        tracker = Tracker(events.append)
        tracker.update("load", 0.0)
        tracker.update("load", 1.0)
        tracker.update("stage2", 0.5)
        tracker.update("stage1", 0.2)
        tracker.update("stage1", 0.1)
        tracker.update("prepass", 1.0)
        tracker.finish("write")
        fractions = [e["fraction"] for e in events]
        self.assertEqual(fractions, sorted(fractions))
        self.assertEqual(fractions[-1], 1.0)
        self.assertTrue(all(0.0 <= f <= 1.0 for f in fractions))

    def test_event_shape(self):
        events = []
        Tracker(events.append).update("stage1", 0.5)
        self.assertEqual(set(events[0]), {"event", "phase", "fraction", "message_key"})
        self.assertEqual(events[0]["message_key"], PHASES["stage1"]["message_key"])

    def test_throttles_tiny_steps(self):
        events = []
        tracker = Tracker(events.append)
        for i in range(1001):
            tracker.update("stage2", i / 1000)
        self.assertLess(len(events), 100)
