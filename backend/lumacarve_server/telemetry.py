"""On-demand, cached NVML device telemetry with no Torch or CUDA context.

The UI owns refresh cadence. This module only samples when requested, caches
briefly, and reports device-wide metrics (never per-app GPU allocations).
Unavailable sensors remain None; there are no synthetic measurements.
"""
from __future__ import annotations

import threading
import time
from typing import Any


class GpuTelemetrySampler:
    def __init__(self, nvml: Any | None = None, ttl_seconds: float = 2.0):
        self._nvml = nvml
        self._initialized = False
        self._ttl = max(2.0, ttl_seconds)
        self._lock = threading.RLock()
        self._cache: dict[int, tuple[float, dict[str, Any]]] = {}
        self._error: str | None = None

    def _connect(self) -> Any:
        if self._error is not None:
            raise RuntimeError(self._error)
        if self._nvml is None:
            try:
                import pynvml  # pure Python NVML binding, no torch import
                self._nvml = pynvml
            except ImportError as exc:
                self._error = "NVML Python bindings are unavailable"
                raise RuntimeError(self._error) from exc
        if not self._initialized:
            try:
                self._nvml.nvmlInit()
                self._initialized = True
            except Exception as exc:
                self._error = "NVIDIA driver/NVML unavailable"
                raise RuntimeError(self._error) from exc
        return self._nvml

    @staticmethod
    def _optional(call):
        try:
            return call()
        except Exception:
            return None

    @staticmethod
    def _name(value: Any) -> str:
        return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)

    def sample(self, device_index: int = 0) -> dict[str, Any]:
        """Return measured GPU values or an explicit unavailable status.

        Cache is per GPU index. Access to NVML is serialized and rate-limited,
        even when multiple browser clients request the same device.
        """
        with self._lock:
            now = time.monotonic()
            cached = self._cache.get(device_index)
            if cached is not None and now - cached[0] < self._ttl:
                return dict(cached[1])
            values: dict[str, Any] = {
                "status": "unavailable", "reason": None,
                "scope": "physical_device", "source": "nvml",
                "sampled_at": None, "device_index": device_index,
                "devices": [], "gpu": {
                    "name": None, "used_bytes": None, "total_bytes": None,
                    "utilization_percent": None, "temperature_c": None, "power_w": None,
                },
            }
            try:
                nvml = self._connect()
                count = int(nvml.nvmlDeviceGetCount())
                devices = []
                for index in range(count):
                    handle = nvml.nvmlDeviceGetHandleByIndex(index)
                    name = self._name(nvml.nvmlDeviceGetName(handle))
                    devices.append({"index": index, "name": name})
                values["devices"] = devices
                if device_index >= count:
                    values["reason"] = "GPU device index is unavailable"
                else:
                    handle = nvml.nvmlDeviceGetHandleByIndex(device_index)
                    memory = self._optional(lambda: nvml.nvmlDeviceGetMemoryInfo(handle))
                    utilization = self._optional(lambda: nvml.nvmlDeviceGetUtilizationRates(handle))
                    temperature = self._optional(
                        lambda: nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
                    )
                    power = self._optional(lambda: nvml.nvmlDeviceGetPowerUsage(handle))
                    values["gpu"] = {
                        "name": devices[device_index]["name"],
                        "used_bytes": int(memory.used) if memory is not None else None,
                        "total_bytes": int(memory.total) if memory is not None else None,
                        "utilization_percent": int(utilization.gpu) if utilization is not None else None,
                        "temperature_c": int(temperature) if temperature is not None else None,
                        "power_w": round(float(power) / 1000, 1) if power is not None else None,
                    }
                    values["status"] = "ok"
                    values["sampled_at"] = time.time()
            except Exception as exc:
                # Keep private driver exceptions out of user-facing API payloads.
                values["reason"] = str(exc) if isinstance(exc, RuntimeError) else "NVML sampling failed"
            self._cache[device_index] = (now, values)
            return dict(values)

    def close(self) -> None:
        with self._lock:
            if self._initialized:
                try:
                    self._nvml.nvmlShutdown()
                finally:
                    self._initialized = False
