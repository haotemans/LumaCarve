"""Guarantee the package includes nested API routers in a normal wheel."""
import tomllib
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


class PackagingTests(unittest.TestCase):
    def test_recursive_python_package_discovery(self):
        with PROJECT.open("rb") as stream:
            cfg = tomllib.load(stream)
        packages = cfg["tool"]["setuptools"]["packages"]["find"]
        self.assertIn("lumacarve_server*", packages["include"])
        self.assertIn("lumacarve_runtime*", packages["include"])
        self.assertEqual(packages["where"], ["."])

    def test_optional_groups_do_not_embed_in_core(self):
        with PROJECT.open("rb") as stream:
            cfg = tomllib.load(stream)
        core = cfg["project"]["dependencies"]
        self.assertFalse(any(dep.startswith("torch") for dep in core))
        self.assertIn("inference", cfg["project"]["optional-dependencies"])
        self.assertIn("training", cfg["project"]["optional-dependencies"])


if __name__ == "__main__":
    unittest.main()
