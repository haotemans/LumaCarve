"""Layout checker regression tests; no file writes outside temporary folders."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "check_layout.py"
spec = importlib.util.spec_from_file_location("layout_checker", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class LayoutCheckerTests(unittest.TestCase):
    def sample(self, folder):
        root = Path(folder)
        source = root / "backend/lumacarve_server/app.py"
        doc = root / "docs/app.md"
        test = root / "backend/tests/test_app.py"
        for file in (source, doc, test):
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("# fixture\n", encoding="utf-8")
        (root / "backend/lumacarve_runtime").mkdir(parents=True)
        (root / ".gitignore").write_text(".venv/\nLumaCarveData/\n", encoding="utf-8")
        entry = {
            "id": "app",
            "source": ["backend/lumacarve_server/app.py"],
            "doc": "docs/app.md",
            "tests": ["backend/tests/test_app.py"],
            "verification": "backend-tests",
        }
        return root, {"schema_version": 1, "module": [entry]}

    def test_valid_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            root, config = self.sample(folder)
            self.assertEqual(checker.check_layout(root, config), [])

    def test_missing_markdown(self):
        with tempfile.TemporaryDirectory() as folder:
            root, config = self.sample(folder)
            config["module"][0]["doc"] = "docs/none.md"
            self.assertTrue(any("missing or unsafe doc" in s for s in checker.check_layout(root, config)))

    def test_duplicate_source_ownership(self):
        with tempfile.TemporaryDirectory() as folder:
            root, config = self.sample(folder)
            copied = dict(config["module"][0], id="duplicate")
            config["module"].append(copied)
            self.assertTrue(any("source also owned" in s for s in checker.check_layout(root, config)))

    def test_reject_path_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root, config = self.sample(folder)
            config["module"][0]["source"] = ["../outside.py"]
            self.assertTrue(any("escapes repository" in s for s in checker.check_layout(root, config)))

    def test_new_python_code_requires_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root, config = self.sample(folder)
            (root/"backend/lumacarve_runtime/new_adapter.py").write_text("pass\n", encoding="utf-8")
            self.assertTrue(any("Unregistered backend source" in s for s in checker.check_layout(root, config)))


if __name__ == "__main__":
    unittest.main()
