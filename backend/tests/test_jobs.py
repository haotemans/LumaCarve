import tempfile
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
