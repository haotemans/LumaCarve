"""CPU-only persistent-queue choice / Rust parity tests."""
import unittest
from unittest.mock import patch

from lumacarve_runtime.queue_bridge import choose_pending_job
from lumacarve_runtime.rust_bridge import scheduler_backend


def pending():
    return [
        {"id": "background", "priority": "background", "sequence": 1},
        {"id": "normal", "priority": "normal", "sequence": 2},
        {"id": "interactive-old", "priority": "interactive", "sequence": 3},
        {"id": "interactive-new", "priority": "interactive", "sequence": 4},
    ]


class QueueBridgeTests(unittest.TestCase):
    def test_python_priority_and_starvation_protection(self):
        with patch("lumacarve_runtime.queue_bridge._extension", return_value=None):
            self.assertEqual(choose_pending_job(pending(), 0), ("interactive-old", 1))
            self.assertEqual(choose_pending_job(pending(), 3), ("background", 0))
            self.assertEqual(choose_pending_job([], 2), None)

    def test_rejects_corrupt_snapshot(self):
        bad = pending() + [dict(pending()[0])]
        with self.assertRaises(ValueError):
            choose_pending_job(bad, 0)

    def test_corrupt_extension_refused(self):
        class Broken:
            @staticmethod
            def choose_queued_job(raw, streak):
                return ("not-in-sqlite", 1)
        with patch("lumacarve_runtime.queue_bridge._extension", return_value=Broken()):
            with self.assertRaises(ValueError):
                choose_pending_job(pending(), 0)

    def test_installed_rust_matches_python(self):
        if scheduler_backend() != "rust":
            self.skipTest("Optional Rust extension not installed")
        for streak in (0, 1, 2, 3, 4):
            self.assertEqual(choose_pending_job(pending(), streak),
                             (("background", 0) if streak >= 3 else ("interactive-old", streak + 1)))
        self.assertIsNone(choose_pending_job([], 0))


if __name__ == "__main__":
    unittest.main()
