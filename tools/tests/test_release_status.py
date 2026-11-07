"""Release/source version and documentation drift regression tests."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.check_release_status import check_release_status, run


class ReleaseStatusTests(unittest.TestCase):
    def fixture(self, root):
        data = {
            "schema_version": 1,
            "checked_on": "2026-11-07",
            "source_version": "0.2.3",
            "releases": [
                {"platform": "Windows x64", "version": "0.2.3", "tag": "v0.2.3-portable-preview.1",
                 "asset": "portable.zip", "checksum": "SHA256SUMS-Windows.txt", "source_sha": "a" * 40},
                {"platform": "Linux x64", "version": "0.2.2", "tag": "v0.2.2-portable-preview.1",
                 "asset": "portable.AppImage", "checksum": "SHA256SUMS.txt", "source_sha": "b" * 40}
            ],
            "capabilities": [
                {"id": "api", "name": "API", "state": "CI 已验证",
                 "detail": "HTTP health tested", "evidence": ["backend/app.py"]}
            ],
        }
        contents = {
            "frontend/package.json": '{"version": "0.2.3"}',
            "frontend/src-tauri/tauri.conf.json": '{"version": "0.2.3"}',
            "frontend/src-tauri/Cargo.toml": '[package]\nversion = "0.2.3"\n',
            "docs/release-status.json": json.dumps(data, ensure_ascii=False),
            "docs/release-status.md": "0.2.3 portable.zip portable.AppImage "
                                      "v0.2.3-portable-preview.1 v0.2.2-portable-preview.1 API CI 已验证",
            "README.md": "See docs/release-status.md",
            "backend/app.py": "# fixture"
        }
        for name, text in contents.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return data

    def test_valid_platform_specific_history(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            self.assertEqual(run(root), [])

    def test_version_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            (root / "frontend/package.json").write_text('{"version": "0.2.4"}', encoding="utf-8")
            self.assertTrue(any("Version drift" in x for x in run(root)))

    def test_missing_release_asset_in_markdown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            (root / "docs/release-status.md").write_text("0.2.3", encoding="utf-8")
            self.assertTrue(any("Markdown missing" in x for x in run(root)))

    def test_installer_disallowed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.fixture(root)
            data["releases"][0]["asset"] = "LumaCarve-setup.exe"
            self.assertTrue(any("Non-portable" in x for x in check_release_status(root, data)))

    def test_missing_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = self.fixture(root)
            data["capabilities"][0]["evidence"] = ["backend/missing.py"]
            self.assertTrue(any("Missing evidence" in x for x in check_release_status(root, data)))


if __name__ == "__main__":
    unittest.main()
