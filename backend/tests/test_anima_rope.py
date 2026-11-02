"""Anima fused RoPE: pure CPU policy tests + optional CUDA numerical checks."""
from __future__ import annotations

import importlib.util
import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import Mock, patch

from lumacarve_runtime.kernels import anima_rope


@dataclass(frozen=True)
class FakeDevice:
    type: str = "cuda"


class FakeTensor:
    def __init__(self, shape, *, dtype="torch.float16", device=None, last_stride=1, requires_grad=False):
        self.shape = tuple(shape)
        self.ndim = len(shape)
        self.dtype = dtype
        self.device = device if device is not None else FakeDevice()
        self.last_stride = last_stride
        self.requires_grad = requires_grad

    def stride(self, axis):
        return self.last_stride if axis == -1 else 4096

    def unflatten(self, axis, dims):
        assert axis == 2 and len(dims) == 2
        left, right = dims
        if right == -1:
            right = self.shape[axis] // left
        assert self.shape[axis] == left * right
        return FakeTensor(self.shape[:axis] + (left, right) + self.shape[axis + 1:], dtype=self.dtype, device=self.device)

    def transpose(self, a, b):
        shape = list(self.shape)
        shape[a], shape[b] = shape[b], shape[a]
        return FakeTensor(shape, dtype=self.dtype, device=self.device)

    def repeat_interleave(self, count, dim):
        shape = list(self.shape)
        shape[dim] *= count
        return FakeTensor(shape, dtype=self.dtype, device=self.device)

    def flatten(self, a, b):
        shape = list(self.shape)
        total = 1
        for item in shape[a : b + 1]:
            total *= item
        return FakeTensor(shape[:a] + [total] + shape[b + 1 :], dtype=self.dtype, device=self.device)

    def type_as(self, other):
        return self

    def size(self, dim):
        return self.shape[dim]


class FakeOriginalProcessor:
    def __init__(self):
        self.calls = []

    def __call__(self, attn, hidden_states, encoder_hidden_states=None, attention_mask=None, image_rotary_emb=None):
        self.calls.append((attn, hidden_states, encoder_hidden_states, attention_mask, image_rotary_emb))
        return "original"


class FakeAttention:
    def __init__(self, processor=None):
        self.heads = 2
        self._processor = processor if processor is not None else FakeOriginalProcessor()
        self.to_q = Mock(side_effect=lambda x: FakeTensor((1, 8, 128)))
        self.to_k = Mock(side_effect=lambda x: FakeTensor((1, 8, 128)))
        self.to_v = Mock(side_effect=lambda x: FakeTensor((1, 8, 128)))
        self.norm_q = Mock(side_effect=lambda x: x)
        self.norm_k = Mock(side_effect=lambda x: x)
        self.to_out = (Mock(side_effect=lambda x: x), Mock(side_effect=lambda x: x))

    def get_processor(self):
        return self._processor

    def set_processor(self, processor):
        self._processor = processor


class AnimaRoPEPolicyTests(unittest.TestCase):
    def test_metadata_checks_do_not_use_gpu(self):
        q = FakeTensor((1, 2, 8, 64))
        k = FakeTensor((1, 2, 8, 64))
        c = FakeTensor((8, 64), dtype="torch.float32")
        s = FakeTensor((8, 64), dtype="torch.float32")
        self.assertTrue(anima_rope._compatible(q, k, c, s))
        self.assertFalse(anima_rope._compatible(q, FakeTensor((1, 2, 9, 64)), c, s))
        self.assertFalse(anima_rope._compatible(q, k, c, FakeTensor((8, 64), dtype="torch.float16")))
        self.assertFalse(anima_rope._compatible(q, k, FakeTensor((9, 64), dtype="torch.float32"), s))
        self.assertFalse(anima_rope._compatible(FakeTensor((1, 2, 8, 63)), FakeTensor((1, 2, 8, 63)), c, s))
        self.assertFalse(anima_rope._compatible(FakeTensor((1, 2, 8, 64), device=FakeDevice("cpu")), k, c, s))
        self.assertFalse(anima_rope._compatible(FakeTensor((1, 2, 8, 64), last_stride=2), k, c, s))
        self.assertFalse(anima_rope._compatible(q, k, FakeTensor((8, 64), dtype="torch.float32", last_stride=2), s))

    def _install(self, pipeline):
        with patch.object(anima_rope, "_triton_available", return_value=True), patch.object(
            anima_rope, "_processor_class", return_value=FakeOriginalProcessor
        ), patch.object(anima_rope, "_dispatch_attention_fn", return_value=Mock(return_value=FakeTensor((1, 8, 2, 64)))):
            return anima_rope.install_anima_rope_triton(pipeline)

    def test_opt_in_install_only_self_attention_and_idempotent(self):
        attn1 = FakeAttention()
        attn2 = FakeAttention()
        pipe = SimpleNamespace(transformer=SimpleNamespace(transformer_blocks=[SimpleNamespace(attn1=attn1, attn2=attn2)]))
        self.assertEqual(self._install(pipe).installed, 1)
        self.assertIsInstance(attn1.get_processor(), anima_rope._FusedCosmosSelfAttention)
        self.assertIsInstance(attn2.get_processor(), FakeOriginalProcessor)
        self.assertEqual(self._install(pipe).installed, 0)

    def test_missing_triton_preserves_attention(self):
        attn = FakeAttention()
        pipe = SimpleNamespace(transformer=SimpleNamespace(transformer_blocks=[SimpleNamespace(attn1=attn)]))
        with patch.object(anima_rope, "_triton_available", return_value=False):
            self.assertEqual(anima_rope.install_anima_rope_triton(pipe).installed, 0)
        self.assertIsInstance(attn.get_processor(), FakeOriginalProcessor)

    def test_fused_route_calls_dispatch_and_original_fallback(self):
        attn = FakeAttention()
        original = attn.get_processor()
        dispatch = Mock(return_value=FakeTensor((1, 8, 2, 64)))
        wrapped = anima_rope._FusedCosmosSelfAttention(original, {"active": True}, dispatch)
        hidden = FakeTensor((1, 8, 128))
        freq = (FakeTensor((8, 64), dtype="torch.float32"), FakeTensor((8, 64), dtype="torch.float32"))
        with patch.object(anima_rope, "_forward_safe", return_value=True), patch.object(
            anima_rope, "fused_qk_rotary", side_effect=lambda q, k, c, s: (q, k)
        ) as fused:
            value = wrapped(attn, hidden, image_rotary_emb=freq)
            self.assertIsInstance(value, FakeTensor)
            fused.assert_called_once()
            dispatch.assert_called_once()
            self.assertEqual(original.calls, [])
            # Cross attention always falls back and bypasses custom projections.
            self.assertEqual(wrapped(attn, hidden, encoder_hidden_states=hidden, image_rotary_emb=freq), "original")
            self.assertEqual(len(original.calls), 1)

    def test_training_and_compile_guard_falls_back(self):
        attn = FakeAttention()
        original = attn.get_processor()
        wrapped = anima_rope._FusedCosmosSelfAttention(original, {"active": True}, Mock())
        hidden = FakeTensor((1, 8, 128))
        with patch.object(anima_rope, "_forward_safe", return_value=False):
            self.assertEqual(wrapped(attn, hidden, image_rotary_emb=(object(), object())), "original")
        hidden.requires_grad = True
        with patch.object(anima_rope, "_forward_safe", return_value=True):
            self.assertEqual(wrapped(attn, hidden, image_rotary_emb=(object(), object())), "original")
        attn.to_q.assert_not_called()

    def test_failed_kernel_disables_every_attn1_in_same_pipeline(self):
        first, second = FakeAttention(), FakeAttention()
        pipe = SimpleNamespace(transformer=SimpleNamespace(transformer_blocks=[
            SimpleNamespace(attn1=first), SimpleNamespace(attn1=second)
        ]))
        with patch.object(anima_rope, "_triton_available", return_value=True), patch.object(
            anima_rope, "_processor_class", return_value=FakeOriginalProcessor
        ), patch.object(anima_rope, "_dispatch_attention_fn", return_value=Mock()):
            self.assertEqual(anima_rope.install_anima_rope_triton(pipe).installed, 2)
        freq = (FakeTensor((8, 64), dtype="torch.float32"), FakeTensor((8, 64), dtype="torch.float32"))
        with patch.object(anima_rope, "_forward_safe", return_value=True), patch.object(
            anima_rope, "fused_qk_rotary", side_effect=RuntimeError("JIT compilation failure")
        ) as fused, patch.object(anima_rope.log, "exception"):
            self.assertEqual(first.get_processor()(first, FakeTensor((1, 8, 128)), image_rotary_emb=freq), "original")
            self.assertEqual(second.get_processor()(second, FakeTensor((1, 8, 128)), image_rotary_emb=freq), "original")
            self.assertEqual(fused.call_count, 1)


class AnimaRoPEGPUChecks(unittest.TestCase):
    def test_cuda_matches_cosmos_half_split_reference(self):
        if importlib.util.find_spec("torch") is None or importlib.util.find_spec("triton") is None:
            self.skipTest("Torch or Triton not installed")
        import torch

        if not torch.cuda.is_available():
            self.skipTest("CUDA GPU unavailable")
        for dtype in (torch.float16, torch.bfloat16, torch.float32):
            if dtype == torch.bfloat16 and not torch.cuda.is_bf16_supported():
                continue
            for batch, heads, tokens, dim in ((1, 4, 63, 64), (2, 3, 65, 128), (1, 8, 257, 256)):
                with self.subTest(dtype=str(dtype), shape=(batch, heads, tokens, dim)):
                    # The attention processor's transpose creates non-contiguous [B,H,S,D] views.
                    q = torch.randn(batch, tokens, heads, dim, dtype=dtype, device="cuda").transpose(1, 2)
                    k = torch.randn(batch, tokens, heads, dim, dtype=dtype, device="cuda").transpose(1, 2)
                    angles = torch.randn(tokens, dim // 2, device="cuda", dtype=torch.float32)
                    cos = angles.cos().repeat(1, 2)
                    sin = angles.sin().repeat(1, 2)

                    def reference(x):
                        rotated = torch.cat((-x[..., dim // 2 :], x[..., : dim // 2]), dim=-1)
                        return (x.float() * cos[None, None, :, :] + rotated.float() * sin[None, None, :, :]).to(dtype)

                    actual_q, actual_k = anima_rope.fused_qk_rotary(q, k, cos, sin)
                    atol, rtol = (2e-5, 2e-5) if dtype == torch.float32 else (2e-3, 2e-3) if dtype == torch.float16 else (2e-2, 2e-2)
                    torch.testing.assert_close(actual_q, reference(q), atol=atol, rtol=rtol)
                    torch.testing.assert_close(actual_k, reference(k), atol=atol, rtol=rtol)


if __name__ == "__main__":
    unittest.main()
