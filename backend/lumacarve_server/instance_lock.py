"""Single local GPU queue owner across FastAPI processes.

The persistent lockfile is never deleted; deleting a locked inode can allow
two processes to acquire different locks at the same logical path.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import BinaryIO


class QueueOwnershipError(RuntimeError):
    """Another local process currently owns the GPU execution queue."""


class LocalQueueLock:
    def __init__(self, path: Path):
        self.path = path
        self._handle: BinaryIO | None = None

    def acquire(self) -> None:
        if self._handle is not None:
            raise QueueOwnershipError("Queue ownership already acquired")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise QueueOwnershipError(
                "Another LumaCarve backend owns the local GPU queue; "
                "stop that process before starting another"
            ) from exc
        self._handle = handle

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            self._handle = None
