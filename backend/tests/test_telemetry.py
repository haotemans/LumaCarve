"""CPU-only NVML sampler contract tests."""
import unittest
from types import SimpleNamespace
from lumacarve_server.telemetry import GpuTelemetrySampler


class FakeNVML:
    NVML_TEMPERATURE_GPU = 0

    def __init__(self):
        self.init_calls = 0
        self.memory_calls = 0

    def nvmlInit(self):
        self.init_calls += 1

    def nvmlDeviceGetCount(self):
        return 1

    def nvmlDeviceGetHandleByIndex(self, index):
        return index

    def nvmlDeviceGetName(self, handle):
        return b"Fake GPU"

    def nvmlDeviceGetMemoryInfo(self, handle):
        self.memory_calls += 1
        return SimpleNamespace(used=1024, total=2048)

    def nvmlDeviceGetUtilizationRates(self, handle):
        return SimpleNamespace(gpu=50)

    def nvmlDeviceGetTemperature(self, handle, sensor):
        return 60

    def nvmlDeviceGetPowerUsage(self, handle):
        return 123000

    def nvmlShutdown(self):
        pass


class TelemetryTests(unittest.TestCase):
    def test_device_sample_is_real_and_cached(self):
        driver = FakeNVML()
        sampler = GpuTelemetrySampler(driver, ttl_seconds=2)
        first = sampler.sample()
        second = sampler.sample()
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["scope"], "physical_device")
        self.assertEqual(first["gpu"]["used_bytes"], 1024)
        self.assertEqual(first["gpu"]["utilization_percent"], 50)
        self.assertEqual(first["gpu"]["temperature_c"], 60)
        self.assertEqual(first["gpu"]["power_w"], 123.0)
        self.assertEqual(second["sampled_at"], first["sampled_at"])
        self.assertEqual(driver.memory_calls, 1)
        sampler.close()

    def test_unavailable_device_not_fabricated(self):
        sampler = GpuTelemetrySampler(FakeNVML())
        sample = sampler.sample(1)
        self.assertEqual(sample["status"], "unavailable")
        self.assertIsNone(sample["gpu"]["used_bytes"])
        self.assertEqual(len(sample["devices"]), 1)

    def test_failed_nvml_is_unavailable(self):
        class BrokenNVML:
            def nvmlInit(self):
                raise RuntimeError("driver error")
        result = GpuTelemetrySampler(BrokenNVML()).sample()
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["sampled_at"])
        self.assertIsNone(result["gpu"]["utilization_percent"])


if __name__ == "__main__":
    unittest.main()
