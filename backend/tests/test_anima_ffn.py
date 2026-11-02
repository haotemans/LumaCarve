"""Anima FFN GEMM+exact GELU: CPU contracts plus opt-in CUDA correctness.

CPU tests run without torch/triton/models and exercise installer, module hooks,
LoRA wrappers, conservative compatibility, fault recovery and API wiring.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from lumacarve_runtime.kernels import anima_ffn


class FakeDevice:
    def __init__(self, kind="cuda"):
        self.type = kind

    def __eq__(self, other):
        return isinstance(other, FakeDevice) and self.type == other.type


class FakeTensor:
    def __init__(self, shape=(1, 128, 1024), *, dtype="torch.bfloat16", device=None,
                 contiguous=True, requires_grad=False):
        self.shape = tuple(shape)
        self.ndim = len(shape)
        self.dtype = dtype
        self.device = device if device is not None else FakeDevice()
        self.contiguous = contiguous
        self.requires_grad = requires_grad

    def is_contiguous(self):
        return self.contiguous


class FakeLinear:
    def __init__(self, input_size, output_size, *, bias=False):
        self.weight = FakeTensor((output_size, input_size))
        self.bias = FakeTensor((output_size,)) if bias else None
        self._forward_hooks = {}
        self._forward_pre_hooks = {}
        self._backward_hooks = {}
        self._backward_pre_hooks = {}
        self.calls = 0
        self.training = False

    def forward(self, x):
        self.calls += 1
        return FakeTensor(x.shape[:-1] + (self.weight.shape[0],), dtype=x.dtype, device=x.device)

    def __call__(self, x):
        return self.forward(x)


class FakeDropout:
    def __init__(self, p=0):
        self.p = p

    def __call__(self, value):
        return value


class FakeGELU:
    def __init__(self, *, approximate="none"):
        self.proj = FakeLinear(1024, 4096)
        self.approximate = approximate
        self.calls = 0
        self.training = False

    def forward(self, x):
        self.calls += 1
        return self.proj(x)

    def __call__(self, x):
        return self.forward(x)


class FakeFeedForward:
    def __init__(self):
        self.net = [FakeGELU(), FakeDropout(), FakeLinear(4096, 1024)]
        self.training = False

    def forward(self, x):
        for layer in self.net:
            x = layer(x)
        return x


class FakeBlock:
    def __init__(self):
        self.ff = FakeFeedForward()


class FfnPolicyTests(unittest.TestCase):
    def make_pipe(self, count=2):
        return SimpleNamespace(transformer=SimpleNamespace(transformer_blocks=[FakeBlock() for _ in range(count)]))

    def install(self, pipe):
        with patch.object(anima_ffn, "_triton_available", return_value=True), patch.object(
            anima_ffn, "_resolve_model_types",
            return_value=(FakeBlock, FakeFeedForward, FakeGELU, FakeLinear, FakeDropout),
        ):
            return anima_ffn.install_anima_ffn_triton(pipe)

    def test_metadata_checks_are_cpu_only(self):
        x = FakeTensor()
        projection = FakeLinear(1024, 4096, bias=True)
        self.assertTrue(anima_ffn._compatible(x, projection))
        self.assertFalse(anima_ffn._compatible(FakeTensor(contiguous=False), projection))
        self.assertFalse(anima_ffn._compatible(FakeTensor(device=FakeDevice("cpu")), projection))
        self.assertFalse(anima_ffn._compatible(FakeTensor(dtype="torch.float32"), projection))
        self.assertFalse(anima_ffn._compatible(FakeTensor((1, 8, 1024)), projection))
        self.assertFalse(anima_ffn._compatible(FakeTensor((1, 128, 1000)), projection))
        self.assertFalse(anima_ffn._compatible(FakeTensor(), FakeLinear(1024, 4097)))
        projection.weight = FakeTensor((4096, 1024), contiguous=False)
        self.assertFalse(anima_ffn._compatible(x, projection))
        projection.weight = FakeTensor((4096, 1024))
        projection.bias = FakeTensor((4096,), device=FakeDevice("cpu"))
        self.assertFalse(anima_ffn._compatible(x, projection))

    def test_installs_only_exact_cosmos_ffn_and_is_idempotent(self):
        pipe = self.make_pipe(2)
        self.assertEqual(self.install(pipe).installed, 2)
        activation = pipe.transformer.transformer_blocks[0].ff.net[0]
        self.assertTrue(hasattr(activation, "_lumacarve_ffn_original_forward"))
        self.assertEqual(self.install(pipe).installed, 0)

    def test_triton_source_is_python_syntax_valid_and_never_autotunes(self):
        # CI intentionally avoids importing optional Torch/Triton GPU modules.
        # Still parse the exact kernel source and verify no runtime autotuning.
        import ast

        source = (
            Path(__file__).resolve().parents[1]
            / "lumacarve_runtime"
            / "kernels"
            / "_anima_ffn_triton.py"
        ).read_text(encoding="utf-8")
        ast.parse(source)
        self.assertNotIn("@triton.autotune", source)
        self.assertNotIn("triton.testing.do_bench(", source)

    def test_missing_triton_never_modifies_ffn(self):
        pipe = self.make_pipe(1)
        with patch.object(anima_ffn, "_triton_available", return_value=False):
            self.assertEqual(anima_ffn.install_anima_ffn_triton(pipe).installed, 0)
        self.assertFalse(hasattr(pipe.transformer.transformer_blocks[0].ff.net[0], "_lumacarve_ffn_original_forward"))

    def test_rejects_dropout_approximation_and_training(self):
        for mutation in (
            lambda ff: setattr(ff.net[1], "p", 0.25),
            lambda ff: setattr(ff.net[0], "approximate", "tanh"),
            lambda ff: setattr(ff.net[0], "training", True),
            lambda ff: setattr(ff, "training", True),
        ):
            with self.subTest(mutation=mutation):
                pipe = self.make_pipe(1)
                mutation(pipe.transformer.transformer_blocks[0].ff)
                self.assertEqual(self.install(pipe).installed, 0)

    def test_skips_peft_wrappers_and_offload_hooks(self):
        pipe = self.make_pipe(1)
        projection = pipe.transformer.transformer_blocks[0].ff.net[0].proj
        projection._hf_hook = object()
        self.assertEqual(self.install(pipe).installed, 0)
        del projection._hf_hook
        projection._forward_pre_hooks = {1: lambda *_: None}
        self.assertEqual(self.install(pipe).installed, 0)
        projection._forward_pre_hooks = {}
        class LoRALinear(FakeLinear):
            pass
        pipe.transformer.transformer_blocks[0].ff.net[0].proj = LoRALinear(1024, 4096)
        self.assertEqual(self.install(pipe).installed, 0)

    def test_successful_forward_preserves_rest_of_feedforward(self):
        pipe = self.make_pipe(1)
        self.install(pipe)
        ff = pipe.transformer.transformer_blocks[0].ff
        x = FakeTensor()
        expected = FakeTensor((1, 128, 4096))
        with patch.object(anima_ffn, "_inference_safe", return_value=True), patch.object(
            anima_ffn, "fused_ffn_linear_gelu", return_value=expected
        ) as fused:
            out = ff.forward(x)
        self.assertEqual(out.shape, (1, 128, 1024))
        self.assertEqual(ff.net[0].calls, 0)
        self.assertEqual(ff.net[0].proj.calls, 0)
        self.assertEqual(ff.net[2].calls, 1)
        self.assertEqual(fused.call_count, 1)

    def test_late_installed_adapter_forces_original_path(self):
        pipe = self.make_pipe(1)
        self.install(pipe)
        ff = pipe.transformer.transformer_blocks[0].ff
        with patch.object(anima_ffn, "_inference_safe", return_value=True), patch.object(
            anima_ffn, "fused_ffn_linear_gelu"
        ) as fused:
            class WrappedLinear(FakeLinear):
                pass

            ff.net[0].proj = WrappedLinear(1024, 4096)  # late LoRA-like replacement
            result = ff.net[0].forward(FakeTensor())
            self.assertIsInstance(result, FakeTensor)
            self.assertEqual(ff.net[0].calls, 1)
            fused.assert_not_called()

    def test_failure_disables_all_sites_after_one_attempt(self):
        pipe = self.make_pipe(2)
        self.install(pipe)
        first, second = [b.ff.net[0] for b in pipe.transformer.transformer_blocks]
        with patch.object(anima_ffn, "_inference_safe", return_value=True), patch.object(
            anima_ffn, "fused_ffn_linear_gelu", side_effect=RuntimeError("Triton failed")
        ) as fused, patch.object(anima_ffn.log, "exception") as logged:
            self.assertIsInstance(first.forward(FakeTensor()), FakeTensor)
            self.assertIsInstance(second.forward(FakeTensor()), FakeTensor)
            self.assertEqual(fused.call_count, 1)
            self.assertEqual(logged.call_count, 1)
            self.assertEqual(first.calls, 1)
            self.assertEqual(second.calls, 1)


class FfnWiringTests(unittest.TestCase):
    def test_configuration_defaults_and_rejects_unknown_modes(self):
        from lumacarve_server.config import Settings

        self.assertEqual(Settings(data_dir=Path(".")).anima_triton_ffn, "off")
        with self.assertRaisesRegex(ValueError, "anima_triton_ffn"):
            Settings(data_dir=Path("."), anima_triton_ffn="auto")
        with patch.dict("os.environ", {"LUMACARVE_ANIMA_TRITON_FFN": "experimental"}):
            self.assertEqual(Settings.from_env().anima_triton_ffn, "experimental")

    def test_adapter_wires_only_for_full_gpu_residency(self):
        from lumacarve_server.adapters.anima import AnimaAdapter
        from lumacarve_server.config import Settings

        torch_mod = ModuleType("torch")
        torch_mod.bfloat16 = object()
        torch_mod.float16 = object()
        torch_mod.cuda = SimpleNamespace(is_available=lambda: True, is_bf16_supported=lambda: True)
        diffusers_mod = ModuleType("diffusers")
        fake_pipe = SimpleNamespace(load_components=Mock(), to=Mock())
        diffusers_mod.ModularPipeline = SimpleNamespace(from_pretrained=Mock(return_value=fake_pipe))
        diffusers_mod.ComponentsManager = Mock()
        with patch.dict("sys.modules", {"torch": torch_mod, "diffusers": diffusers_mod}), patch.object(
            anima_ffn, "install_anima_ffn_triton", return_value=anima_ffn.AnimaFFNReport(1, "fixture")
        ) as install:
            AnimaAdapter(Settings(data_dir=Path("."), inference_offload="full"))._build(Path("/model"))
            install.assert_not_called()
            AnimaAdapter(Settings(
                data_dir=Path("."), inference_offload="full", anima_triton_ffn="experimental",
            ))._build(Path("/model"))
            install.assert_called_once_with(fake_pipe)
            install.reset_mock()
            AnimaAdapter(Settings(
                data_dir=Path("."), inference_offload="auto", anima_triton_ffn="experimental",
            ))._build(Path("/model"))
            install.assert_not_called()


class FfnCudaTests(unittest.TestCase):
    def test_fused_linear_exact_gelu_dtype_bias_and_nondivisible_tokens(self):
        if importlib.util.find_spec("torch") is None or importlib.util.find_spec("triton") is None:
            self.skipTest("torch/triton not installed")
        import torch
        import torch.nn.functional as functional
        if not torch.cuda.is_available():
            self.skipTest("CUDA unavailable")
        for dtype in (torch.float16, torch.bfloat16):
            if dtype == torch.bfloat16 and not torch.cuda.is_bf16_supported():
                continue
            for batch, tokens, k, n, has_bias in (
                (1, 37, 128, 256, True),
                (2, 33, 256, 512, False),
                (1, 65, 512, 1024, True),
            ):
                with self.subTest(dtype=str(dtype), shape=(batch, tokens, k, n), bias=has_bias):
                    x = torch.randn((batch, tokens, k), dtype=dtype, device="cuda")
                    weight = torch.randn((n, k), dtype=dtype, device="cuda") * 0.1
                    bias = torch.randn((n,), dtype=dtype, device="cuda") * 0.1 if has_bias else None
                    expected = functional.gelu(functional.linear(x, weight, bias), approximate="none")
                    result = anima_ffn.fused_ffn_linear_gelu(x, weight, bias)
                    atol, rtol = ((0.012, 0.015) if dtype == torch.float16 else (0.06, 0.055))
                    torch.testing.assert_close(result, expected, atol=atol, rtol=rtol)


if __name__ == "__main__":
    unittest.main()
