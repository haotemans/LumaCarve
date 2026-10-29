"""Install policy tests must never download packages."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("project_installer", ROOT / "tools" / "setup.py")
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


class InstallerTests(unittest.TestCase):
    def test_single_root_venv(self):
        self.assertEqual(INSTALLER.VENV, ROOT / ".venv")
        self.assertEqual(INSTALLER.BACKEND, ROOT / "backend")

    def test_cpu_falls_back(self):
        packages, why=INSTALLER.plan_attention("both",system="Linux",cuda_available=False,toolkit=False)
        self.assertEqual(packages,[])
        self.assertIn("SDPA",why)

    def test_windows_skips_unsafe_builds(self):
        packages, why=INSTALLER.plan_attention("auto",system="Windows",cuda_available=True,toolkit=True)
        self.assertEqual(packages,[])
        self.assertIn("Windows",why)

    def test_linux_cuda_offers_both(self):
        packages, why=INSTALLER.plan_attention("auto",system="Linux",cuda_available=True,toolkit=True)
        self.assertEqual(packages,["flash-attn","sageattention"])
        self.assertIsNone(why)

    def test_cpu_wheel_index(self):
        self.assertEqual(INSTALLER.torch_index("cu128"),"https://download.pytorch.org/whl/cu128")
        self.assertEqual(INSTALLER.torch_index("cpu"),"https://download.pytorch.org/whl/cpu")


if __name__=="__main__":
    unittest.main()
