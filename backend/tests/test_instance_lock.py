"""Exclusive GPU queue instance lock: no CUDA and no third-party packages."""
import tempfile
import unittest
from pathlib import Path

from lumacarve_server.instance_lock import LocalQueueLock, QueueOwnershipError
from lumacarve_server.jobs import DisabledInference, JobQueue, JobStore


class LocalQueueLockTests(unittest.TestCase):
    def test_only_one_local_owner_until_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "worker.lock"
            first, second = LocalQueueLock(path), LocalQueueLock(path)
            first.acquire()
            try:
                with self.assertRaises(QueueOwnershipError):
                    second.acquire()
            finally:
                first.release()
            second.acquire()
            second.release()
            self.assertTrue(path.is_file())  # lock file must not be unlinked

    def test_second_job_queue_cannot_start_while_owned(self):
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "jobs.sqlite3"
            first = JobQueue(JobStore(store_path), DisabledInference())
            first.start()
            try:
                second = JobQueue(JobStore(store_path), DisabledInference())
                with self.assertRaises(QueueOwnershipError):
                    second.start()
            finally:
                first.close()
            second.start()
            second.close()

    def test_orphaned_running_only_reset_after_owner_acquired(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "jobs.sqlite3"
            old = JobStore(path)
            job = old.create({}, {})
            old.transition(job["id"], "queued", "running")
            self.assertEqual(JobStore(path).get(job["id"])["state"], "running")
            queue = JobQueue(JobStore(path), DisabledInference())
            queue.start()
            try:
                self.assertEqual(queue.store.get(job["id"])["state"], "failed")
                self.assertEqual(queue.store.get(job["id"])["error"], "server_restarted")
            finally:
                queue.close()


if __name__ == "__main__":
    unittest.main()
