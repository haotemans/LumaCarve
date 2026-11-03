"""Supervised, lazy one-GPU Python executor process.

The API never imports Torch: only the spawned child imports the Anima adapter.
One command at a time is issued by the existing JobQueue thread, which keeps
SQLite queue ownership and cancellation semantics. All event messages are
received on the owner thread; there is no second competing pipe reader.
Windows spawn semantics are required. Child process exit is the hard CUDA
release boundary; failures never trigger overlapping worker starts.
"""
from __future__ import annotations

import multiprocessing as mp
from multiprocessing.connection import Connection
import threading
import time
from typing import Any, Callable

from .config import Settings
from .execution_monitor import ExecutionMonitor

HEARTBEAT_INTERVAL = 2.0
MAX_HEARTBEAT_GAP = 180.0
CANCEL_GRACE = 12.0
TERMINATE_GRACE = 5.0


def _worker_main(settings: Settings, connection: Connection, cancel: Any) -> None:
    """Child target: importing this parent module never imports Torch."""
    import traceback
    from .adapters.anima import AnimaAdapter

    lock = threading.Lock()
    living = threading.Event()
    living.set()
    heartbeat_active = threading.Event()

    def send(message: dict[str, Any]) -> None:
        with lock:
            connection.send(message)

    # Event.wait() returns True when stopped; do not busy-loop.
    def heartbeat_loop() -> None:
        while living.is_set():
            if heartbeat_active.is_set():
                try:
                    send({"type": "heartbeat", "at": time.monotonic()})
                except (BrokenPipeError, EOFError, OSError):
                    return
            for _ in range(20):
                if not living.is_set():
                    return
                time.sleep(HEARTBEAT_INTERVAL / 20)

    class ChildMonitor(ExecutionMonitor):
        def update_components(self, components: list[dict[str, Any]], phase_status: dict[str, str]) -> None:
            super().update_components(components, phase_status)
            send({"type": "components", "components": components, "phase_detail": phase_status})

    monitor = ChildMonitor(event_sink=lambda event: send({"type": "event", "event": event}))
    adapter = AnimaAdapter(settings)
    adapter.monitor = monitor
    thread = threading.Thread(target=heartbeat_loop, name="gpu-executor-heartbeat", daemon=True)
    thread.start()
    try:
        send({"type": "ready"})
        while True:
            try:
                command = connection.recv()
            except (EOFError, OSError):
                return
            if not isinstance(command, dict):
                send({"type": "error", "error": "Invalid worker command"})
                continue
            operation = command.get("type")
            if operation == "shutdown":
                send({"type": "stopped"})
                return
            if operation == "status":
                send({"type": "result", "result": adapter.residency})
                continue
            if operation == "unload":
                heartbeat_active.set()
                try:
                    result = adapter.unload_idle()
                    send({"type": "result", "result": result, "residency": adapter.residency})
                except Exception as exc:
                    send({"type": "error", "error": f"{type(exc).__name__}: {exc}"[:300]})
                finally:
                    heartbeat_active.clear()
                return  # Always exit to release the entire CUDA context.
            if operation != "run":
                send({"type": "error", "error": "Unsupported worker operation"})
                continue
            cancel.clear()
            heartbeat_active.set()
            try:
                with monitor.bind_job(str(command["job_id"])):
                    with monitor.phase("job", model_id=adapter.model_id):
                        result = adapter.run(command["workflow"], command["inputs"], cancel)
                send({"type": "result", "result": result, "residency": adapter.residency})
            except BaseException as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                send({"type": "error", "error": f"{type(exc).__name__}: {exc}"[:300],
                      "cancelled": isinstance(exc, InterruptedError), "residency": adapter.residency})
                # A partial model load / failed LoRA update is unsafe to reuse.
                if adapter.residency.get("error"):
                    return
            finally:
                heartbeat_active.clear()
    finally:
        living.clear()
        thread.join(timeout=1.0)
        connection.close()


class GpuExecutorSupervisor:
    """Queue-thread-owned supervisor for a single lazy child GPU process."""

    model_id = "anima-base-1"
    remote_monitored = True

    def __init__(self, settings: Settings, monitor: ExecutionMonitor | None = None,
                 worker_target: Callable[..., None] = _worker_main) -> None:
        self.settings = settings
        self.monitor = monitor
        self._target = worker_target
        self._ctx = mp.get_context("spawn")
        self._process: Any = None
        self._conn: Connection | None = None
        self._cancel: Any = None
        self._lock = threading.RLock()
        self._last_heartbeat: float | None = None
        self._state = "stopped"
        self._residency: dict[str, Any] = {
            "model_id": None, "path": None, "state": "unloaded",
            "verified_release": True, "error": None, "components": [],
        }

    @property
    def ready(self) -> bool:
        # Deliberately import no PyTorch, query no GPU and start no process.
        from .adapters.anima import dependencies_available, find_anima_snapshot
        return find_anima_snapshot(self.settings) is not None and dependencies_available()

    @property
    def residency(self) -> dict[str, Any]:
        with self._lock:
            data = dict(self._residency)
            data["executor"] = {
                "mode": "subprocess", "state": self._state,
                "pid": self._process.pid if self._process and self._process.is_alive() else None,
                "heartbeat_age_seconds": (round(time.monotonic() - self._last_heartbeat, 1)
                                          if self._last_heartbeat is not None else None),
            }
            return data

    def _terminate(self) -> None:
        process, conn = self._process, self._conn
        # Keep ownership until OS process exit is confirmed. If kill/reap
        # fails, the reference must survive so no replacement can be spawned.
        if process is not None:
            process.join(timeout=0.2)
            if process.is_alive():
                process.terminate()
                process.join(timeout=TERMINATE_GRACE)
            if process.is_alive():
                process.kill()
                process.join(timeout=TERMINATE_GRACE)
            if process.is_alive():
                self._state = "failed"
                raise RuntimeError("GPU executor did not terminate; refusing to reload another model")
            process.close()
        self._process = None
        self._conn = None
        self._cancel = None
        self._last_heartbeat = None
        if conn is not None:
            conn.close()
        if process is not None and self.monitor is not None:
            self.monitor.fail_remote_active()
        self._state = "stopped"
        self._residency = {
            "model_id": None, "path": None, "state": "unloaded",
            "verified_release": True, "error": None, "components": [],
        }
        if self.monitor is not None:
            self.monitor.update_components([
                {"key": key, "state": "unloaded", "gpu_weight_bytes": 0,
                 "cpu_weight_bytes": 0, "source": "executor_terminated"}
                for key in ("te", "vae", "dit")
            ], {})

    def _start(self) -> None:
        if self._state == "failed":
            # A previous teardown could not confirm process exit.
            self._terminate()
        if self._process is not None and self._process.is_alive():
            return
        # Any prior process must be fully reaped before a new CUDA context is made.
        self._terminate()
        parent, child = self._ctx.Pipe(duplex=True)
        self._cancel = self._ctx.Event()
        process = self._ctx.Process(target=self._target, args=(self.settings, child, self._cancel))
        try:
            process.start()
        except BaseException:
            parent.close()
            child.close()
            raise
        child.close()
        self._process, self._conn = process, parent
        self._state = "starting"
        self._last_heartbeat = time.monotonic()
        try:
            self._receive(expected="ready", timeout=30.0)
        except BaseException:
            self._terminate()
            raise
        self._state = "ready"

    def _receive(self, *, expected: str, timeout: float | None,
                 cancel: threading.Event | None = None) -> dict[str, Any]:
        started = time.monotonic()
        cancel_at: float | None = None
        while True:
            if self._conn is None or self._process is None:
                raise RuntimeError("GPU executor connection unavailable")
            if not self._process.is_alive() and not self._conn.poll(0):
                raise RuntimeError("GPU executor crashed or exited")
            if cancel is not None and cancel.is_set():
                if cancel_at is None:
                    cancel_at = time.monotonic()
                    if self._cancel is not None:
                        self._cancel.set()
                elif time.monotonic() - cancel_at > CANCEL_GRACE:
                    self._terminate()
                    raise InterruptedError("GPU executor terminated after cancellation timeout")
            if self._last_heartbeat is not None and time.monotonic() - self._last_heartbeat > MAX_HEARTBEAT_GAP:
                self._terminate()
                raise RuntimeError("GPU executor heartbeat lost; process terminated")
            if timeout is not None and time.monotonic() - started > timeout:
                self._terminate()
                raise RuntimeError("GPU executor command timed out")
            if not self._conn.poll(0.1):
                continue
            try:
                message = self._conn.recv()
            except (EOFError, OSError) as exc:
                self._terminate()
                raise RuntimeError("GPU executor disconnected") from exc
            kind = message.get("type") if isinstance(message, dict) else None
            if kind == "heartbeat":
                self._last_heartbeat = time.monotonic()
            elif kind == "event":
                if self.monitor is not None and isinstance(message.get("event"), dict):
                    self.monitor.accept_remote_event(message["event"])
            elif kind == "components":
                if self.monitor is not None:
                    self.monitor.update_components(message.get("components", []),
                                                   message.get("phase_detail", {}))
            elif kind == "error":
                if isinstance(message.get("residency"), dict):
                    self._residency = dict(message["residency"])
                if message.get("cancelled"):
                    raise InterruptedError(message.get("error", "Cancelled"))
                raise RuntimeError(message.get("error", "Worker failed"))
            elif kind == expected:
                return message
            elif kind in ("result", "ready", "stopped"):
                raise RuntimeError(f"Unexpected executor reply: {kind}")

    def run(self, workflow: dict[str, Any], inputs: dict[str, Any],
            cancel: threading.Event, job_id: str | None = None) -> dict[str, Any]:
        if cancel.is_set():
            raise InterruptedError("Cancelled before GPU executor startup")
        with self._lock:
            self._start()
            if self._conn is None:
                raise RuntimeError("GPU executor unavailable")
            self._state = "running"
            self._last_heartbeat = time.monotonic()
            self._cancel.clear()
            try:
                self._conn.send({"type": "run", "workflow": workflow, "inputs": inputs,
                                 "job_id": job_id or "unknown"})
                data = self._receive(expected="result", timeout=None, cancel=cancel)
                if isinstance(data.get("residency"), dict):
                    self._residency = dict(data["residency"])
                return data["result"]
            finally:
                if self._process is None or not self._process.is_alive():
                    self._terminate()
                elif self._state != "failed":
                    self._state = "ready"

    def unload_idle(self) -> dict[str, Any]:
        with self._lock:
            if self._process is None:
                return self.residency
            self._last_heartbeat = time.monotonic()
            try:
                self._conn.send({"type": "unload"})
                self._receive(expected="result", timeout=30.0)
            finally:
                self._terminate()
            return self.residency

    def close(self) -> None:
        with self._lock:
            if self._conn is not None and self._process is not None and self._process.is_alive():
                try:
                    self._conn.send({"type": "shutdown"})
                    self._receive(expected="stopped", timeout=2.0)
                except Exception:
                    pass
            self._terminate()
