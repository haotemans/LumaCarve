"""Anima gated-residual Triton: CPU policy and optional CUDA numerics."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from lumacarve_runtime.kernels import anima_residual


class FakeDevice:
    def __init__(self, kind="cuda"):
        self.type = kind

    def __eq__(self, other):
        return isinstance(other, FakeDevice) and self.type == other.type


class FakeTensor:
    """Symbolic tensors for validating dispatch without importing PyTorch."""
    def __init__(
        self, shape=(2, 5, 128), *, dtype="torch.bfloat16",
        device=None, last_stride=1, requires_grad=False,
    ):
        self.shape = tuple(shape)
        self.ndim = len(self.shape)
        self.dtype = dtype
        self.device = device if device is not None else FakeDevice()
        self._last_stride = last_stride
        self.requires_grad = requires_grad

    def stride(self, axis):
        return self._last_stride if axis == -1 else 1024

    def __add__(self, other):
        return FakeTensor(self.shape, dtype=self.dtype, device=self.device)

    def __mul__(self, other):
        return FakeTensor(self.shape, dtype=self.dtype, device=self.device)


class FakeNorm:
    def __init__(self):
        self.calls = 0

    def __call__(self, hidden, timestep, temb=None):
        self.calls += 1
        return hidden, FakeTensor((hidden.shape[0], 1, hidden.shape[2]), dtype=hidden.dtype, device=hidden.device)


class FakeBlock:
    def __init__(self):
        self.norm1, self.norm2, self.norm3 = FakeNorm(), FakeNorm(), FakeNorm()
        self.attn1 = Mock(side_effect=lambda tensor, **kwargs: tensor)
        self.attn2 = Mock(side_effect=lambda tensor, **kwargs: tensor)
        self.ff = Mock(side_effect=lambda tensor: tensor)
        self.before_proj = None
        self.after_proj = None
        self.original_calls = 0

    def forward(
        self, hidden_states, encoder_hidden_states, embedded_timestep,
        temb=None, image_rotary_emb=None, extra_pos_emb=None,
        attention_mask=None, controlnet_residual=None, latents=None,
        block_idx=None,
    ):
        self.original_calls += 1
        return "original-forward"


class ResidualPolicyTests(unittest.TestCase):
    def test_metadata_checks_without_gpu(self):
        residual = FakeTensor()
        branch = FakeTensor()
        gate = FakeTensor((2, 1, 128))
        self.assertTrue(anima_residual._compatible(residual, gate, branch))
        self.assertTrue(anima_residual._compatible(residual, FakeTensor((2, 5, 128)), branch))
        self.assertFalse(anima_residual._compatible(residual, FakeTensor((2, 3, 128)), branch))
        self.assertFalse(anima_residual._compatible(residual, FakeTensor((1, 1, 128)), branch))
        self.assertFalse(anima_residual._compatible(residual, FakeTensor((2, 1, 127)), branch))
        self.assertFalse(anima_residual._compatible(residual, gate, FakeTensor((2, 6, 128))))
        self.assertFalse(anima_residual._compatible(FakeTensor(device=FakeDevice("cpu")), gate, branch))
        self.assertFalse(anima_residual._compatible(residual, gate, FakeTensor(dtype="torch.float32")))
        self.assertFalse(anima_residual._compatible(residual, gate, FakeTensor(last_stride=2)))
        self.assertFalse(anima_residual._compatible(FakeTensor(shape=(2, 5, 9000)), FakeTensor((2, 1, 9000)), FakeTensor((2, 5, 9000))))

    def make_pipeline(self, *, blocks=2):
        return SimpleNamespace(transformer=SimpleNamespace(transformer_blocks=[FakeBlock() for _ in range(blocks)]))

    def install(self, pipe):
        with patch.object(anima_residual, "_triton_available", return_value=True), patch.object(
            anima_residual, "_cosmos_block_class", return_value=FakeBlock,
        ):
            return anima_residual.install_anima_residual_triton(pipe)

    def test_install_only_exact_blocks_and_idempotent(self):
        pipe = self.make_pipeline(blocks=2)
        self.assertEqual(self.install(pipe).installed, 2)
        self.assertEqual(self.install(pipe).installed, 0)
        self.assertTrue(hasattr(pipe.transformer.transformer_blocks[0], "_lumacarve_residual_original"))
        different = SimpleNamespace(transformer=SimpleNamespace(transformer_blocks=[object()]))
        self.assertEqual(self.install(different).installed, 0)

    def test_missing_triton_and_specialized_controlnet_not_patched(self):
        pipe = self.make_pipeline(blocks=1)
        with patch.object(anima_residual, "_triton_available", return_value=False):
            self.assertEqual(anima_residual.install_anima_residual_triton(pipe).installed, 0)
        block = pipe.transformer.transformer_blocks[0]
        block.before_proj = object()
        self.assertEqual(self.install(pipe).installed, 0)

    def test_three_branches_fused_without_changing_operators(self):
        pipe = self.make_pipeline(blocks=1)
        self.install(pipe)
        block = pipe.transformer.transformer_blocks[0]
        tensor = FakeTensor()
        with patch.object(anima_residual, "_torch_inference_safe", return_value=True), patch.object(
            anima_residual, "fused_gated_residual", side_effect=lambda residual, gate, branch: residual,
        ) as fuse:
            output = block.forward(tensor, "text", "time", image_rotary_emb="rope")
        self.assertIs(output, tensor)
        self.assertEqual(fuse.call_count, 3)
        self.assertEqual(block.attn1.call_count, 1)
        self.assertEqual(block.attn2.call_count, 1)
        self.assertEqual(block.ff.call_count, 1)
        self.assertEqual(block.original_calls, 0)
        self.assertEqual(block.attn1.call_args.kwargs["image_rotary_emb"], "rope")
        self.assertEqual(block.attn2.call_args.kwargs["encoder_hidden_states"], "text")

    def test_training_cpu_and_controlnet_use_unmodified_original(self):
        pipe = self.make_pipeline(blocks=1)
        self.install(pipe)
        block = pipe.transformer.transformer_blocks[0]
        with patch.object(anima_residual, "_torch_inference_safe", return_value=False), patch.object(
            anima_residual, "fused_gated_residual",
        ) as fuse:
            self.assertEqual(block.forward(FakeTensor(), "text", "time"), "original-forward")
            fuse.assert_not_called()
        with patch.object(anima_residual, "_torch_inference_safe", return_value=True):
            self.assertEqual(block.forward(FakeTensor(device=FakeDevice("cpu")), "text", "time"), "original-forward")
            self.assertEqual(block.forward(FakeTensor(), "text", "time", controlnet_residual="res"), "original-forward")
            self.assertEqual(block.forward(FakeTensor(requires_grad=True), "text", "time"), "original-forward")
            self.assertEqual(block.original_calls, 4)

    def test_failure_circuits_breaker_for_all_blocks_and_keeps_intermediates(self):
        pipe = self.make_pipeline(blocks=2)
        self.install(pipe)
        first, second = pipe.transformer.transformer_blocks
        with patch.object(anima_residual, "_torch_inference_safe", return_value=True), patch.object(
            anima_residual, "fused_gated_residual", side_effect=RuntimeError("compile failed"),
        ) as fused, patch.object(anima_residual.log, "exception") as logged:
            result = first.forward(FakeTensor(), "text", "time")
            self.assertIsInstance(result, FakeTensor)
            self.assertEqual(first.original_calls, 0)
            self.assertEqual(first.attn1.call_count, 1)
            self.assertEqual(first.attn2.call_count, 1)
            self.assertEqual(first.ff.call_count, 1)
            self.assertEqual(fused.call_count, 1)
            self.assertEqual(logged.call_count, 1)
            self.assertEqual(second.forward(FakeTensor(), "text", "time"), "original-forward")
            self.assertEqual(fused.call_count, 1)


class AnimaResidualWiringTests(unittest.TestCase):
    def test_settings_default_env_and_validation(self):
        from lumacarve_server.config import Settings

        self.assertEqual(Settings(data_dir=Path(".")).anima_triton_residual, "off")
        with self.assertRaisesRegex(ValueError, "anima_triton_residual"):
            Settings(data_dir=Path("."), anima_triton_residual="auto")
        with patch.dict("os.environ", {"LUMACARVE_ANIMA_TRITON_RESIDUAL": "experimental"}):
            self.assertEqual(Settings.from_env().anima_triton_residual, "experimental")

    def test_build_installs_only_when_explicitly_enabled(self):
        from lumacarve_server.adapters.anima import AnimaAdapter
        from lumacarve_server.config import Settings

        fake_torch = ModuleType("torch")
        fake_torch.cuda = SimpleNamespace(is_available=lambda: True, is_bf16_supported=lambda: True)
        fake_torch.bfloat16, fake_torch.float16 = object(), object()
        fake_pipe = SimpleNamespace(load_components=Mock(), to=Mock())
        fake_diffusers = ModuleType("diffusers")
        fake_diffusers.ComponentsManager = Mock()
        fake_diffusers.ModularPipeline = SimpleNamespace(from_pretrained=Mock(return_value=fake_pipe))
        with patch.dict("sys.modules", {"torch": fake_torch, "diffusers": fake_diffusers}), patch.object(
            anima_residual, "install_anima_residual_triton",
            return_value=anima_residual.AnimaResidualReport(1, "fixture"),
        ) as install:
            AnimaAdapter(Settings(data_dir=Path("."), inference_offload="full"))._build(Path("/fixture/anima"))
            install.assert_not_called()
            AnimaAdapter(Settings(
                data_dir=Path("."), inference_offload="full",
                anima_triton_residual="experimental",
            ))._build(Path("/fixture/anima"))
            install.assert_called_once_with(fake_pipe)


class AnimaResidualCUDAEquivalence(unittest.TestCase):
    def test_fp16_bf16_fp32_broadcast_and_strided_inputs(self):
        if importlib.util.find_spec("torch") is None or importlib.util.find_spec("triton") is None:
            self.skipTest("Torch or Triton not installed")
        import torch

        if not torch.cuda.is_available():
            self.skipTest("CUDA unavailable")
        for dtype in (torch.float16, torch.bfloat16, torch.float32):
            if dtype == torch.bfloat16 and not torch.cuda.is_bf16_supported():
                continue
            for batch, seq, width, gate_seq in (
                (1, 33, 128, 1),
                (2, 17, 1024, 1),
                (2, 7, 257, 7),
                (1, 4, 2048, 4),
            ):
                with self.subTest(dtype=str(dtype), shape=(batch, seq, width), gate_seq=gate_seq):
                    # B,S,C tensors with nontrivial batch/sequence strides.
                    residual = torch.randn((seq, batch, width), device="cuda", dtype=dtype).transpose(0, 1)
                    branch = torch.randn((seq, batch, width), device="cuda", dtype=dtype).transpose(0, 1)
                    packed = torch.randn((batch, gate_seq, 3 * width), device="cuda", dtype=dtype)
                    gate = packed.chunk(3, dim=-1)[2]
                    native = residual + gate * branch
                    result = anima_residual.fused_gated_residual(residual, gate, branch)
                    atol, rtol = (2e-5, 2e-5) if dtype == torch.float32 else (
                        (4e-3, 4e-3) if dtype == torch.float16 else (3e-2, 3e-2)
                    )
                    torch.testing.assert_close(result, native, rtol=rtol, atol=atol)


if __name__ == "__main__":
    unittest.main()
