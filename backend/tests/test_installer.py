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

    def test_china_mirrors(self):
        self.assertEqual(INSTALLER.resolve_region("cn"), "cn")
        self.assertEqual(INSTALLER.torch_index("cu128", region="cn", source="auto"),
                         "https://mirrors.cernet.edu.cn/pytorch/whl/cu128")
        self.assertEqual(INSTALLER.torch_index("cu128", region="cn", source="official"),
                         "https://download.pytorch.org/whl/cu128")

    def test_rust_scheduler_policy(self):
        self.assertEqual(INSTALLER.plan_rust_scheduler("auto", cargo_available=False),
                         (False, "Cargo not found; using Python fallback"))
        self.assertEqual(INSTALLER.plan_rust_scheduler("auto", cargo_available=True),
                         (True, None))
        self.assertEqual(INSTALLER.plan_rust_scheduler("python", cargo_available=True)[0], False)
        with self.assertRaises(RuntimeError):
            INSTALLER.plan_rust_scheduler("required", cargo_available=False)

    def test_cpu_wheel_index(self):
        self.assertEqual(INSTALLER.torch_index("cu128"),"https://download.pytorch.org/whl/cu128")
        self.assertEqual(INSTALLER.torch_index("cpu"),"https://download.pytorch.org/whl/cpu")


if __name__=="__main__":
    unittest.main()
