"""Desktop sidecar authentication is strict and opt-in for the WebUI."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from lumacarve_server.app import create_app
from lumacarve_server.config import Settings


class DesktopAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.token = "0123456789abcdef" * 4
        self.settings = Settings(
            data_dir=Path(self.tmp.name),
            desktop_token=self.token,
            allowed_origins=("http://tauri.localhost", "tauri://localhost"),
        )

    def test_desktop_requires_token_even_for_health(self):
        with TestClient(create_app(self.settings)) as client:
            self.assertEqual(client.get("/api/v1/health").status_code, 403)
            self.assertEqual(client.get("/api/v1/runtime", headers={"X-LumaCarve-Token": "wrong"}).status_code, 403)
            allowed = client.get("/api/v1/health", headers={"X-LumaCarve-Token": self.token})
            self.assertEqual(allowed.status_code, 200)
            self.assertEqual(allowed.json()["status"], "ok")

    def test_image_url_can_authorize_with_query(self):
        with TestClient(create_app(self.settings)) as client:
            response = client.get("/api/v1/health", params={"desktop_token": self.token})
            self.assertEqual(response.status_code, 200)

    def test_origin_restrictions_and_tauri_preflight(self):
        with TestClient(create_app(self.settings)) as client:
            headers = {"X-LumaCarve-Token": self.token, "Origin": "https://evil.example"}
            self.assertEqual(client.get("/api/v1/health", headers=headers).status_code, 403)
            for origin in self.settings.allowed_origins:
                response = client.get("/api/v1/health", headers={"X-LumaCarve-Token": self.token, "Origin": origin})
                self.assertEqual(response.status_code, 200)
                preflight = client.options(
                    "/api/v1/jobs", headers={
                        "Origin": origin, "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "x-lumacarve-token,content-type",
                    },
                )
                self.assertEqual(preflight.status_code, 200)
                self.assertEqual(preflight.headers.get("access-control-allow-origin"), origin)

    def test_normal_browser_and_secret_redaction(self):
        self.assertNotIn(self.token, repr(self.settings))
        with TestClient(create_app(Settings(data_dir=Path(self.tmp.name)))) as client:
            self.assertEqual(client.get("/api/v1/health").status_code, 200)

    def test_reject_weak_desktop_token(self):
        with self.assertRaises(ValueError):
            Settings(data_dir=Path(self.tmp.name), desktop_token="short")


if __name__ == "__main__":
    unittest.main()
