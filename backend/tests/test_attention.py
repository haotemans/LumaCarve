"""Lightweight backend-selection tests: no Torch/CUDA dependency required."""
import unittest
from lumacarve_runtime.attention import select_attention


class AttentionTests(unittest.TestCase):
    def test_cpu_sdpa(self):
        self.assertEqual(select_attention("sage",cuda_available=False,training=False,flash_installed=True,sage_installed=True).selected,"sdpa")

    def test_inference_sage_opt_in(self):
        self.assertEqual(select_attention("sage",cuda_available=True,training=False,flash_installed=False,sage_installed=True).selected,"sage")

    def test_training_never_defaults_to_sage(self):
        self.assertEqual(select_attention("auto",cuda_available=True,training=True,flash_installed=False,sage_installed=True).selected,"sdpa")
        self.assertEqual(select_attention("sage",cuda_available=True,training=True,flash_installed=False,sage_installed=True).selected,"sdpa")

    def test_flash_explicit(self):
        self.assertEqual(select_attention("flash",cuda_available=True,training=True,flash_installed=True,sage_installed=False).selected,"flash")

    def test_auto_flash_or_sdpa(self):
        self.assertEqual(select_attention("auto",cuda_available=True,training=False,flash_installed=True,sage_installed=True).selected,"flash")
        self.assertEqual(select_attention("auto",cuda_available=True,training=False,flash_installed=False,sage_installed=True).selected,"sdpa")

    def test_unsupported_fallback(self):
        self.assertEqual(select_attention("flash",cuda_available=True,training=False,flash_installed=True,sage_installed=False,flash_supported=False).selected,"sdpa")


if __name__=="__main__":
    unittest.main()
