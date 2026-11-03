"""Real event ledger tests; no GPU or PyTorch dependency."""
import unittest
from types import SimpleNamespace

from lumacarve_server.execution_monitor import ExecutionMonitor


class FakeCuda:
    def memory_allocated(self):
        return 1024

    def memory_reserved(self):
        return 2048


class ExecutionMonitorTests(unittest.TestCase):
    def test_empty_snapshot_does_not_invent_events(self):
        monitor = ExecutionMonitor()
        value = monitor.snapshot()
        self.assertFalse(value["measured"])
        self.assertEqual(value["active"], [])
        self.assertEqual(value["events"], [])
        self.assertEqual(value["phase_detail"]["te"], "instrumentation_not_connected")

    def test_real_job_identity_timing_and_allocator(self):
        monitor = ExecutionMonitor()
        torch = SimpleNamespace(cuda=FakeCuda())
        with monitor.bind_job("job-test"):
            with monitor.phase("model_load", model_id="anima-base-1"):
                pass
            with monitor.phase("inference", model_id="anima-base-1", torch_provider=lambda: torch):
                active = monitor.snapshot()["active"]
                self.assertEqual(active[0]["job_id"], "job-test")
                self.assertEqual(active[0]["status"], "running")
        result = monitor.snapshot()
        self.assertTrue(result["measured"])
        events = result["events"]
        self.assertEqual([e["stage"] for e in events], ["inference", "model_load"])
        self.assertEqual(events[0]["job_id"], "job-test")
        self.assertGreaterEqual(events[0]["duration_ms"], 0)
        self.assertEqual(events[0]["allocated_bytes"], 1024)
        self.assertEqual(events[0]["reserved_bytes"], 2048)
        self.assertEqual(events[0]["allocator_source"], "pytorch_process_allocator")
        self.assertIsNone(events[1]["allocated_bytes"])
        self.assertNotIn("_started_monotonic", str(events))

    def test_failed_and_cancelled_phases_are_reported(self):
        monitor = ExecutionMonitor()
        with self.assertRaises(ValueError):
            with monitor.phase("output_save"):
                raise ValueError("save failed")
        with self.assertRaises(InterruptedError):
            with monitor.phase("inference"):
                raise InterruptedError("cancel")
        events = monitor.snapshot()["events"]
        self.assertEqual(events[0]["status"], "cancelled")
        self.assertEqual(events[1]["status"], "failed")

    def test_invalid_phase_and_unknown_token_do_not_corrupt_state(self):
        monitor = ExecutionMonitor()
        with self.assertRaises(ValueError):
            monitor.begin("synthetic")
        with self.assertRaises(KeyError):
            monitor.finish("does-not-exist")
        self.assertEqual(monitor.snapshot()["events"], [])

    def test_hook_observation_retains_real_execution_timestamps(self):
        monitor = ExecutionMonitor()
        with monitor.bind_job("real-job"):
            monitor.record_observation("dit", model_id="anima-base-1",
                                       started_at=100.25, ended_at=101.5,
                                       duration_ms=800.75, timing_source="cuda_events_sum",
                                       calls=3)
        event = monitor.snapshot()["events"][0]
        self.assertEqual(event["job_id"], "real-job")
        self.assertEqual(event["started_at"], 100.25)
        self.assertEqual(event["ended_at"], 101.5)
        self.assertEqual(event["duration_ms"], 800.75)
        self.assertEqual(event["calls"], 3)
        self.assertEqual(event["timing_source"], "cuda_events_sum")

    def test_event_history_is_bounded(self):
        monitor = ExecutionMonitor(max_events=3)
        for _ in range(8):
            with monitor.phase("job"):
                pass
        self.assertEqual(len(monitor.snapshot()["events"]), 3)


if __name__ == "__main__":
    unittest.main()
