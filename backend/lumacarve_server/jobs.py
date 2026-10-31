"""SQLite job ledger and single-worker GPU task queue.

The worker consumes tasks sequentially. No fake image is ever returned.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from lumacarve_runtime.queue_bridge import (
    PRIORITIES, choose_pending_job, require_compatible_queue_backend,
)
from .instance_lock import LocalQueueLock

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
            # Upgrade databases from before priority-based scheduling.
            columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
            if "priority" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'")
            connection.execute("""
                CREATE TABLE IF NOT EXISTS scheduler_state (
                    key TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                )
            """)
            connection.execute(
                "INSERT OR IGNORE INTO scheduler_state(key,value) VALUES ('interactive_streak',0)"
            )

    def recover_interrupted(self) -> None:
        """Only the process owning the OS queue lock may call this."""
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE jobs SET state='failed', error='server_restarted', updated_at=? "
                "WHERE state='running'",
                (time.time(),),
            )

    @contextmanager
    def _connect(self):
        """Commit/rollback AND close the SQLite handle on every platform.

        sqlite3.Connection.__exit__ manages transactions but does not close
        the file descriptor; leaked handles block Windows temp-file cleanup.
        """
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, workflow: dict[str, Any], inputs: dict[str, Any],
               priority: str = "normal") -> dict[str, Any]:
        if priority not in PRIORITIES:
            raise ValueError("Unsupported job priority")
        job_id = uuid.uuid4().hex
        now = time.time()
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO jobs (id,state,workflow,inputs,priority,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                (job_id, "queued", json.dumps(workflow, ensure_ascii=False),
                 json.dumps(inputs, ensure_ascii=False), priority, now, now),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT id,state,priority,result,error,created_at,updated_at FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()
        if row is None:
            raise JobNotFound(job_id)
        return {
            "id": row["id"], "state": row["state"], "priority": row["priority"],
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

    def claim_next(self) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
        """Atomically claim one task from the SQLite queue.

        SQLite owns both priority history and task state. Rust/queue_bridge only
        chooses an ID from this transaction's consistent candidate snapshot.
        """
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM jobs WHERE state='running' LIMIT 1"
            ).fetchone():
                return None
            rows = connection.execute(
                "SELECT rowid AS sequence,id,priority,workflow,inputs "
                "FROM jobs WHERE state='queued' ORDER BY rowid"
            ).fetchall()
            streak = connection.execute(
                "SELECT value FROM scheduler_state WHERE key='interactive_streak'"
            ).fetchone()[0]
            choice = choose_pending_job(
                [{"id": row["id"], "priority": row["priority"],
                  "sequence": row["sequence"]} for row in rows], streak
            )
            if choice is None:
                return None
            job_id, next_streak = choice
            selected = next(row for row in rows if row["id"] == job_id)
            updated = connection.execute(
                "UPDATE jobs SET state='running',updated_at=? "
                "WHERE id=? AND state='queued'",
                (time.time(), job_id),
            ).rowcount
            if updated != 1:
                raise RuntimeError("SQLite claim changed unexpected row count")
            connection.execute(
                "UPDATE scheduler_state SET value=? WHERE key='interactive_streak'",
                (next_streak,),
            )
            return (job_id, json.loads(selected["workflow"]), json.loads(selected["inputs"]))

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
        self._owner = LocalQueueLock(store.path.with_name('gpu-worker.lock'))
        self.queue_backend = "not_started"
        self.fatal_error: str | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._owner.acquire()
        try:
            # Validate the installed PyO3 ABI BEFORE changing any SQLite state.
            self.queue_backend = require_compatible_queue_backend()
            self.store.recover_interrupted()
            self._thread = threading.Thread(
                target=self._run, name="lumacarve-gpu-worker", daemon=True
            )
            self._thread.start()
        except BaseException:
            self._owner.release()
            self._thread = None
            raise

    def close(self) -> None:
        self._shutdown.set()
        self._wakeup.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise RuntimeError("GPU worker is still active; refusing to release queue ownership")
        self._owner.release()

    def submit(self, workflow: dict[str, Any], inputs: dict[str, Any], priority: str = "normal") -> dict[str, Any]:
        with self._lock:
            if self.fatal_error is not None:
                raise EngineUnavailable(f"GPU scheduler unavailable: {self.fatal_error}")
            if not self.adapter.ready:
                raise EngineUnavailable("GPU inference adapter is not configured; job was not enqueued")
            if self.store.count_active() >= self.max_active:
                raise QueueFull("Maximum number of active tasks reached")
            job = self.store.create(workflow, inputs, priority=priority)
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
        return self.store.claim_next()

    def _run(self) -> None:
        while not self._shutdown.is_set():
            self._wakeup.wait(timeout=0.25)
            self._wakeup.clear()
            # Never consume persisted work until a real adapter is ready.
            if not self.adapter.ready:
                continue
            while not self._shutdown.is_set() and self.adapter.ready:
                # Keep cancellation and the queued-to-running claim atomic
                # with respect to this process's API cancellation requests.
                try:
                    with self._lock:
                        task = self._next()
                        if task is not None:
                            cancel = self._cancel.setdefault(task[0], threading.Event())
                except Exception as exc:
                    # Keep queued tasks in SQLite; surface fatal scheduler errors
                    # rather than silently killing the worker thread.
                    with self._lock:
                        self.fatal_error = f"{type(exc).__name__}: {exc}"[:500]
                    return
                if task is None:
                    break
                job_id, workflow, inputs = task
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
