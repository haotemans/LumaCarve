import tempfile
import sqlite3
import threading
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from lumacarve_server.app import create_app
from lumacarve_server.config import Settings
from lumacarve_server.jobs import DisabledInference, JobQueue, JobStore
from test_workflows import sample


class FakeAdapter:
    ready = True
    def run(self, workflow, inputs, cancel):
        return {"output": "fixture-not-a-real-image"}


class JobsTests(unittest.TestCase):
    def test_unconfigured_engine_rejects_without_enqueuing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TestClient(create_app(Settings(data_dir=Path(tmp)))) as client:
                response = client.post("/api/v1/jobs", json={"workflow": sample()})
                self.assertEqual(response.status_code,503,response.text)
                self.assertEqual(client.get("/api/v1/jobs").json()["jobs"], [])

    def test_worker_completes_only_when_real_adapter_injected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp)/"queue.sqlite3")
            queue = JobQueue(store, FakeAdapter())
            queue.start()
            try:
                job = queue.submit(sample(), {"asset_ids": []})
                for _ in range(100):
                    status = store.get(job["id"])["state"]
                    if status == "completed":
                        break
                    time.sleep(0.01)
                self.assertEqual(status, "completed")
                self.assertEqual(store.get(job["id"])["result"]["output"],"fixture-not-a-real-image")
            finally:
                queue.close()

    def test_disabled_worker_leaves_persisted_queued_items_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp)/"queue.sqlite3")
            pending = store.create(sample(), {})
            queue = JobQueue(store, DisabledInference())
            queue.start()
            try:
                time.sleep(0.15)
                self.assertEqual(store.get(pending["id"])["state"], "queued")
            finally:
                queue.close()

    def test_claim_priority_is_fair_across_reopened_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.sqlite3"
            store = JobStore(path)
            background = store.create(sample(), {}, priority="background")["id"]
            interactive = [store.create(sample(), {}, priority="interactive")["id"] for _ in range(4)]
            store.create(sample(), {}, priority="normal")
            for expected in interactive[:3]:
                job_id, _, _ = store.claim_next()
                self.assertEqual(job_id, expected)
                self.assertTrue(store.transition(job_id, "running", "completed"))
            store = JobStore(path)
            job_id, _, _ = store.claim_next()
            self.assertEqual(job_id, background)
            self.assertTrue(store.transition(job_id, "running", "completed"))
            self.assertEqual(store.claim_next()[0], interactive[3])

    def test_sqlite_atomic_claim_prevents_two_workers(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.sqlite3"
            store1, store2 = JobStore(path), JobStore(path)
            first = store1.create(sample(), {})
            second = store1.create(sample(), {})
            self.assertEqual(store1.claim_next()[0], first["id"])
            self.assertIsNone(store2.claim_next())
            store1.transition(first["id"], "running", "completed")
            self.assertEqual(store2.claim_next()[0], second["id"])

    def test_migrate_old_sqlite_without_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.sqlite3"
            with sqlite3.connect(path) as conn:
                conn.execute("""CREATE TABLE jobs (
                    id TEXT PRIMARY KEY, state TEXT NOT NULL,
                    workflow TEXT NOT NULL, inputs TEXT NOT NULL,
                    result TEXT, error TEXT,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL
                )""")
            store = JobStore(path)
            job = store.create(sample(), {})
            self.assertEqual(store.get(job["id"])["priority"], "normal")
            self.assertEqual(store.claim_next()[0], job["id"])

    def test_restarts_fail_inflight_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"queue.sqlite3"
            store=JobStore(path)
            entry=store.create(sample(),{})
            store.transition(entry["id"],"queued","running")
            store=JobStore(path)
            self.assertEqual(store.get(entry["id"])["error"],"server_restarted")
            self.assertEqual(store.get(entry["id"])["state"],"failed")


if __name__ == "__main__":
    unittest.main()
