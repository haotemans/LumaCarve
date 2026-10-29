"""SQLite job ledger and single-worker GPU task queue.

The worker consumes tasks sequentially. No fake image is ever returned.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

STATUS = ("queued", "running", "completed", "failed", "cancelled")


class EngineUnavailable(RuntimeError):
    pass


class QueueFull(RuntimeError):
    pass


class JobNotFound(LookupError):
    pass


class InferenceAdapter(Protocol):
    @property
    def ready(self) -> bool: ...
    def run(self, workflow: dict[str, Any], inputs: dict[str, Any], cancel: threading.Event) -> dict[str, Any]: ...


class DisabledInference:
    @property
    def ready(self) -> bool:
        return False

    def run(self, workflow: dict[str, Any], inputs: dict[str, Any], cancel: threading.Event) -> dict[str, Any]:
        raise EngineUnavailable("No CUDA image inference adapter has been configured")


class JobStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    workflow TEXT NOT NULL,
                    inputs TEXT NOT NULL,
                    result TEXT,
                    error TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            # Restarted process cannot magically resume in-flight CUDA tasks.
            connection.execute(
                "UPDATE jobs SET state='failed', error='server_restarted', updated_at=? WHERE state='running'",
                (time.time(),)
            )

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def create(self, workflow: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        job_id = uuid.uuid4().hex
        now = time.time()
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO jobs (id,state,workflow,inputs,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                (job_id, "queued", json.dumps(workflow, ensure_ascii=False),
                 json.dumps(inputs, ensure_ascii=False), now, now),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT id,state,result,error,created_at,updated_at FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()
        if row is None:
            raise JobNotFound(job_id)
        return {
            "id": row["id"], "state": row["state"],
            "result": json.loads(row["result"]) if row["result"] else None,
            "error": row["error"], "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def count_active(self) -> int:
        with self._lock, self._connect() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM jobs WHERE state IN ('queued','running')"
            ).fetchone()[0]

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            ids = [row[0] for row in connection.execute(
                "SELECT id FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()]
        return [self.get(job_id) for job_id in ids]

    def transition(self, job_id: str, current: str, target: str, *, result: dict | None = None, error: str | None = None) -> bool:
        if target not in STATUS:
            raise ValueError("Invalid target status")
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE jobs SET state=?, result=?, error=?, updated_at=? WHERE id=? AND state=?",
                (target, json.dumps(result,ensure_ascii=False) if result is not None else None,
                 error, time.time(), job_id, current),
            )
        return cursor.rowcount == 1


class JobQueue:
    """One worker serializes GPU operations, avoiding training/inference contention.

    A queue never accepts a job unless a real adapter reports ready=True.
    """
    def __init__(self, store: JobStore, adapter: InferenceAdapter, max_active: int = 16):
        self.store, self.adapter, self.max_active = store, adapter, max_active
        self._lock = threading.RLock()
        self._wakeup = threading.Event()
        self._shutdown = threading.Event()
        self._cancel: dict[str, threading.Event] = {}
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="lumacarve-gpu-worker", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._shutdown.set()
        self._wakeup.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def submit(self, workflow: dict[str, Any], inputs: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if not self.adapter.ready:
                raise EngineUnavailable("GPU inference adapter is not configured; job was not enqueued")
            if self.store.count_active() >= self.max_active:
                raise QueueFull("Maximum number of active tasks reached")
            job = self.store.create(workflow, inputs)
            self._wakeup.set()
            return job

    def cancel(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self.store.get(job_id)
            if job["state"] == "queued":
                self.store.transition(job_id, "queued", "cancelled")
            elif job["state"] == "running":
                self._cancel.setdefault(job_id, threading.Event()).set()
            return self.store.get(job_id)

    def _next(self):
        with self.store._lock, self.store._connect() as connection:
            row = connection.execute(
                "SELECT id,workflow,inputs FROM jobs WHERE state='queued' ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
            return None if row is None else (row["id"], json.loads(row["workflow"]), json.loads(row["inputs"]))

    def _run(self) -> None:
        while not self._shutdown.is_set():
            self._wakeup.wait(timeout=0.25)
            self._wakeup.clear()
            while not self._shutdown.is_set():
                task = self._next()
                if task is None:
                    break
                job_id, workflow, inputs = task
                if not self.store.transition(job_id, "queued", "running"):
                    continue
                cancel = self._cancel.setdefault(job_id, threading.Event())
                try:
                    result = self.adapter.run(workflow, inputs, cancel)
                    if cancel.is_set():
                        self.store.transition(job_id, "running", "cancelled")
                    else:
                        self.store.transition(job_id, "running", "completed", result=result)
                except Exception as exc:
                    self.store.transition(job_id, "running", "cancelled" if cancel.is_set() else "failed", error=str(exc)[:500])
                finally:
                    with self._lock:
                        self._cancel.pop(job_id, None)
