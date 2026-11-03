"""Process isolation contracts without importing Torch or requiring a GPU."""
import tempfile
import unittest
from pathlib import Path

from lumacarve_server.config import Settings
from lumacarve_server.execution_monitor import ExecutionMonitor
from lumacarve_server.gpu_executor import GpuExecutorSupervisor


class ExecutorTests(unittest.TestCase):
    def test_defaults_to_isolated_executor(self):
        settings = Settings(inference_backend="anima")
        self.assertEqual(settings.gpu_executor_mode, "subprocess")
        with self.assertRaises(ValueError):
            Settings(gpu_executor_mode="invalid")

    def test_lazy_spawn_heartbeat_and_hard_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(data_dir=Path(tmp))
            monitor = ExecutionMonitor()
            supervisor = GpuExecutorSupervisor(settings, monitor)
            self.assertEqual(supervisor.residency["executor"]["state"], "stopped")
            self.assertIsNone(supervisor.residency["executor"]["pid"])
            try:
                supervisor._start()
                self.assertEqual(supervisor.residency["executor"]["state"], "ready")
                self.assertIsNotNone(supervisor.residency["executor"]["pid"])
                self.assertTrue(supervisor._process.is_alive())
            finally:
                supervisor.close()
            self.assertIsNone(supervisor.residency["executor"]["pid"])
            self.assertEqual(supervisor.residency["state"], "unloaded")
            self.assertEqual(supervisor.residency["executor"]["state"], "stopped")

    def test_idle_unload_terminates_child_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            supervisor = GpuExecutorSupervisor(Settings(data_dir=Path(tmp)), ExecutionMonitor())
            try:
                supervisor._start()
                result = supervisor.unload_idle()
                self.assertEqual(result["state"], "unloaded")
                self.assertEqual(result["executor"]["state"], "stopped")
                self.assertIsNone(result["executor"]["pid"])
            finally:
                supervisor.close()


if __name__ == "__main__":
    unittest.main()
