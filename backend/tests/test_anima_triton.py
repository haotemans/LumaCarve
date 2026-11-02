"""CPU policy tests plus optional CUDA numerical tests for Anima AdaLN-Zero."""
from __future__ import annotations

import importlib.util
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from lumacarve_runtime.kernels import anima_adaln


class FakeTensor:
    def __init__(self, shape, *, device="cuda", dtype="torch.float16", requires_grad=False, contiguous=True):
        self.shape = tuple(shape)
        self.ndim = len(shape)
        self.device = SimpleNamespace(type=device)
        self.dtype = dtype
        self.requires_grad = requires_grad
        self.contiguous = contiguous

    def is_contiguous(self):
        return self.contiguous

    def stride(self, axis):
        return 1 if axis == -1 else self.shape[-1] * max(1, self.shape[-2])

    def chunk(self, n, dim=-1):
        assert dim == -1 and n == 3
        assert self.shape[-1] % n == 0
        shape = self.shape[:-1] + (self.shape[-1] // n,)
        return tuple(FakeTensor(shape, device=self.device.type, dtype=self.dtype) for _ in range(n))

    def unsqueeze(self, dim):
        shape = list(self.shape)
        shape.insert(dim, 1)
        return FakeTensor(shape, device=self.device.type, dtype=self.dtype)

    def __add__(self, other):
        return self


class FakeCosmosAdaZero:
    def __init__(self):
        self.norm = SimpleNamespace(elementwise_affine=False, eps=1e-6)
        self.activation = lambda value: value
        self.linear_1 = lambda value: value
        self.linear_2 = lambda value: value
        self.original_calls = 0

    def forward(self, hidden_states, embedded_timestep, temb=None):
        self.original_calls += 1
        return "reference", "gate"


class AnimaKernelPolicyTests(unittest.TestCase):
    def setUp(self):
        guard = patch.object(anima_adaln, "_grad_enabled", return_value=False)
        guard.start()
        self.addCleanup(guard.stop)

    def make_pipeline(self):
        blocks = [SimpleNamespace(**{f"norm{i}": FakeCosmosAdaZero() for i in (1, 2, 3)}) for _ in range(2)]
        return SimpleNamespace(transformer=SimpleNamespace(transformer_blocks=blocks))

    def install(self, pipeline):
        with patch.object(anima_adaln, "_triton_available", return_value=True), patch.object(
            anima_adaln, "_resolve_cosmos_zero_type", return_value=FakeCosmosAdaZero
        ):
            return anima_adaln.install_anima_adaln_triton(pipeline)

    def test_compatibility_requires_cuda_contiguous_matching_shapes_and_dtype(self):
        x = FakeTensor((2, 8, 512))
        self.assertTrue(anima_adaln._compatible(x, FakeTensor((2, 1, 512)), FakeTensor((2, 1, 512))))
        self.assertTrue(anima_adaln._compatible(x, FakeTensor((2, 8, 512)), FakeTensor((2, 8, 512))))
        self.assertFalse(anima_adaln._compatible(FakeTensor((2, 8, 512), device="cpu"), FakeTensor((2, 1, 512)), FakeTensor((2, 1, 512))))
        self.assertFalse(anima_adaln._compatible(FakeTensor((2, 8, 512), contiguous=False), FakeTensor((2, 1, 512)), FakeTensor((2, 1, 512))))
        self.assertFalse(anima_adaln._compatible(x, FakeTensor((2, 2, 512)), FakeTensor((2, 2, 512))))
        self.assertTrue(anima_adaln._compatible(x, FakeTensor((2, 1, 512), contiguous=False), FakeTensor((2, 1, 512), contiguous=False)))
        self.assertFalse(anima_adaln._compatible(x, FakeTensor((2, 1, 512), dtype="torch.bfloat16"), FakeTensor((2, 1, 512))))
        self.assertFalse(anima_adaln._compatible(FakeTensor((1, 8, 9000)), FakeTensor((1, 1, 9000)), FakeTensor((1, 1, 9000))))

    def test_no_triton_does_not_patch(self):
        pipeline = self.make_pipeline()
        with patch.object(anima_adaln, "_triton_available", return_value=False):
            result = anima_adaln.install_anima_adaln_triton(pipeline)
        self.assertEqual(result.installed, 0)
        self.assertFalse(hasattr(pipeline.transformer.transformer_blocks[0].norm1, "_lumacarve_original_forward"))

    def test_install_exact_sites_only_and_reuse(self):
        pipeline = self.make_pipeline()
        report = self.install(pipeline)
        self.assertEqual(report.installed, 6)
        norm = pipeline.transformer.transformer_blocks[0].norm1
        x, emb = FakeTensor((1, 32, 128)), FakeTensor((1, 3 * 128))
        with patch.object(anima_adaln, "fused_ada_layer_norm", return_value="fast") as fused:
            y, gate = norm.forward(x, emb)
            self.assertEqual(y, "fast")
            self.assertEqual(gate.shape, (1, 1, 128))
            self.assertEqual(norm.original_calls, 0)
            self.assertEqual(fused.call_count, 1)
        self.assertEqual(self.install(pipeline).installed, 0)

    def test_forward_cpu_and_grad_fallback_without_running_triton(self):
        pipeline = self.make_pipeline()
        self.install(pipeline)
        norm = pipeline.transformer.transformer_blocks[0].norm1
        with patch.object(anima_adaln, "fused_ada_layer_norm") as fused:
            self.assertEqual(norm.forward(FakeTensor((1, 12, 128), device="cpu"), FakeTensor((1, 384)))[0], "reference")
            self.assertEqual(norm.forward(FakeTensor((1, 12, 128), requires_grad=True), FakeTensor((1, 384)))[0], "reference")
            fused.assert_not_called()
        with patch.object(anima_adaln, "_grad_enabled", return_value=True):
            self.assertEqual(norm.forward(FakeTensor((1, 12, 128)), FakeTensor((1, 384)))[0], "reference")

    def test_runtime_failure_disables_all_sites(self):
        pipeline = self.make_pipeline()
        self.install(pipeline)
        one = pipeline.transformer.transformer_blocks[0].norm1
        two = pipeline.transformer.transformer_blocks[1].norm3
        with patch.object(anima_adaln, "fused_ada_layer_norm", side_effect=RuntimeError("jit compile error")) as fused, patch.object(anima_adaln.log, "exception") as logged:
            self.assertEqual(one.forward(FakeTensor((1, 12, 128)), FakeTensor((1, 384)))[0], "reference")
            self.assertEqual(two.forward(FakeTensor((1, 12, 128)), FakeTensor((1, 384)))[0], "reference")
            self.assertEqual(fused.call_count, 1)
            self.assertEqual(logged.call_count, 1)

    def test_unrelated_modules_not_patched(self):
        pipeline = SimpleNamespace(transformer=SimpleNamespace(transformer_blocks=[SimpleNamespace(norm1=object())]))
        self.assertEqual(self.install(pipeline).installed, 0)


class AnimaWiringTests(unittest.TestCase):
    def test_settings_default_and_validation(self):
        from pathlib import Path
        from lumacarve_server.config import Settings

        self.assertEqual(Settings(data_dir=Path(".")).anima_triton, "off")
        with self.assertRaisesRegex(ValueError, "anima_triton"):
            Settings(data_dir=Path("."), anima_triton="auto")
        with patch.dict("os.environ", {"LUMACARVE_ANIMA_TRITON": "experimental"}):
            self.assertEqual(Settings.from_env().anima_triton, "experimental")

    def test_adapter_build_is_opt_in_and_keeps_original_pipeline_default(self):
        from pathlib import Path
        from types import ModuleType
        from unittest.mock import Mock
        from lumacarve_server.adapters.anima import AnimaAdapter
        from lumacarve_server.config import Settings

        fake_torch = ModuleType("torch")
        fake_torch.cuda = SimpleNamespace(is_available=lambda: True, is_bf16_supported=lambda: True)
        fake_torch.bfloat16, fake_torch.float16 = object(), object()
        pipe = SimpleNamespace(load_components=Mock(), to=Mock(), transformer=SimpleNamespace(transformer_blocks=[]))
        fake_diffusers = ModuleType("diffusers")
        fake_diffusers.ComponentsManager = Mock()
        fake_diffusers.ModularPipeline = SimpleNamespace(from_pretrained=Mock(return_value=pipe))

        with patch.dict("sys.modules", {"torch": fake_torch, "diffusers": fake_diffusers}):
            with patch.object(anima_adaln, "install_anima_adaln_triton", return_value=SimpleNamespace(installed=0, reason="fixture")) as install:
                adapter = AnimaAdapter(Settings(data_dir=Path("."), inference_offload="full"))
                loaded, _ = adapter._build(Path("/fixture/anima"))
                self.assertIs(loaded, pipe)
                install.assert_not_called()
                adapter = AnimaAdapter(Settings(data_dir=Path("."), inference_offload="full", anima_triton="experimental"))
                loaded, _ = adapter._build(Path("/fixture/anima"))
                self.assertIs(loaded, pipe)
                install.assert_called_once_with(pipe)
        self.assertEqual(pipe.to.call_count, 2)


class AnimaTritonNumerics(unittest.TestCase):
    def test_cuda_equivalence(self):
        if importlib.util.find_spec("torch") is None or importlib.util.find_spec("triton") is None:
            self.skipTest("Torch or Triton not installed")
        import torch
        if not torch.cuda.is_available():
            self.skipTest("CUDA GPU not available")
        for dtype in (torch.float32, torch.float16, torch.bfloat16):
            if dtype == torch.bfloat16 and not torch.cuda.is_bf16_supported():
                continue
            for batch, tokens, channels, cond_tokens in (
                (1, 33, 128, 1), (2, 17, 257, 1), (1, 8, 1024, 8), (2, 5, 2048, 1)
            ):
                with self.subTest(dtype=dtype, shape=(batch, tokens, channels), cond_tokens=cond_tokens):
                    x = torch.randn((batch, tokens, channels), device="cuda", dtype=dtype)
                    shift = torch.randn((batch, cond_tokens, channels), device="cuda", dtype=dtype) * .3
                    scale = torch.randn((batch, cond_tokens, channels), device="cuda", dtype=dtype) * .3
                    expected = torch.nn.functional.layer_norm(x, (channels,), eps=1e-6) * (1 + scale) + shift
                    actual = anima_adaln.fused_ada_layer_norm(x, shift, scale, 1e-6)
                    # chunk(3) returns non-contiguous views on B>1; no extra copy should be necessary.
                    packed = torch.randn((batch, cond_tokens, 3 * channels), device="cuda", dtype=dtype)
                    shift_view, scale_view, _gate = packed.chunk(3, dim=-1)
                    expected_view = torch.nn.functional.layer_norm(x, (channels,), eps=1e-6) * (1 + scale_view) + shift_view
                    actual_view = anima_adaln.fused_ada_layer_norm(x, shift_view, scale_view, 1e-6)
                    if dtype == torch.float32:
                        rtol, atol = 2e-4, 2e-4
                    elif dtype == torch.float16:
                        rtol, atol = 8e-3, 8e-3
                    else:
                        rtol, atol = 2e-2, 3e-2
                    torch.testing.assert_close(actual, expected, rtol=rtol, atol=atol)
                    torch.testing.assert_close(actual_view, expected_view, rtol=rtol, atol=atol)


if __name__ == "__main__":
    unittest.main()
