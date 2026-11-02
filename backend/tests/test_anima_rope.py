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

    def numel(self):
        total = 1
        for dim in self.shape:
            total *= dim
        return total

    def element_size(self):
        return 4 if self.dtype == "torch.float32" else 2


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


class FakeRotaryPositionEmbedding:
    def __init__(self):
        self.patch_size = (1, 2, 2)
        self.max_size = (1, 128, 128)
        self.base_fps = 24
        self.dim_h, self.dim_w, self.dim_t = 42, 42, 44
        self.h_ntk_factor = self.w_ntk_factor = self.t_ntk_factor = 1.0
        self.calls = 0

    def forward(self, x, fps=None):
        self.calls += 1
        tokens = (x.shape[2] // self.patch_size[0]) * (x.shape[3] // self.patch_size[1]) * (x.shape[4] // self.patch_size[2])
        return (FakeTensor((tokens, 128), dtype="torch.float32", device=x.device),
                FakeTensor((tokens, 128), dtype="torch.float32", device=x.device))


class AnimaRotaryTableCacheTests(unittest.TestCase):
    def install(self, rotary, state=None):
        state = state if state is not None else {"active": True}
        transformer = SimpleNamespace(rope=rotary)
        with patch.object(anima_rope, "_rotary_pos_embed_class", return_value=FakeRotaryPositionEmbedding):
            return anima_rope._install_rotary_table_cache(transformer, state)

    def test_same_shape_cached_but_different_shapes_do_not_collide(self):
        rope = FakeRotaryPositionEmbedding()
        state = {"active": True}
        self.assertTrue(self.install(rope, state))
        image = FakeTensor((1, 16, 1, 128, 128))
        first = rope.forward(image)
        self.assertEqual(rope.calls, 1)
        self.assertIs(first[0], rope.forward(FakeTensor((2, 16, 1, 128, 128)))[0])
        self.assertEqual(rope.calls, 1)
        self.assertIsNot(first[0], rope.forward(image, fps=24)[0])
        self.assertEqual(rope.calls, 2)
        rope.h_ntk_factor = 1.05
        rope.forward(image)
        self.assertEqual(rope.calls, 3)
        self.assertEqual(rope.calls, 3)  # current model parameters are part of the cache key

    def test_disabled_gradient_or_cpu_does_not_cache(self):
        rope = FakeRotaryPositionEmbedding()
        state = {"active": True}
        self.install(rope, state)
        cpu = FakeTensor((1, 16, 1, 128, 128), device=FakeDevice("cpu"))
        with patch.object(anima_rope, "_forward_safe", return_value=True):
            rope.forward(cpu)
            rope.forward(cpu)
            self.assertEqual(rope.calls, 2)
        with patch.object(anima_rope, "_forward_safe", return_value=False):
            rope.forward(FakeTensor((1, 16, 1, 128, 128)))
            rope.forward(FakeTensor((1, 16, 1, 128, 128)))
            self.assertEqual(rope.calls, 4)
        state["active"] = False
        with patch.object(anima_rope, "_forward_safe", return_value=True):
            rope.forward(FakeTensor((1, 16, 1, 128, 128)))
            self.assertEqual(rope.calls, 5)

    def test_cache_is_bounded_and_old_entry_evicted(self):
        rope = FakeRotaryPositionEmbedding()
        self.install(rope)
        with patch.object(anima_rope, "_forward_safe", return_value=True):
            image1 = FakeTensor((1, 16, 1, 128, 128))
            image2 = FakeTensor((1, 16, 1, 64, 64))
            image3 = FakeTensor((1, 16, 1, 96, 96))
            rope.forward(image1)
            rope.forward(image2)
            rope.forward(image3)
            self.assertEqual(rope.calls, 3)
            rope.forward(image1)
            self.assertEqual(rope.calls, 4)  # max two entries
            large = FakeTensor((1, 16, 1, 512, 512))
            rope.forward(large)
            rope.forward(large)
            self.assertEqual(rope.calls, 6)  # >16 MiB, never cached

class AnimaRoPEWiringTests(unittest.TestCase):
    def test_configuration_default_and_environment(self):
        from pathlib import Path
        from lumacarve_server.config import Settings

        self.assertEqual(Settings(data_dir=Path(".")).anima_triton_rope, "off")
        self.assertEqual(Settings(data_dir=Path("."), anima_triton="experimental").anima_triton_rope, "off")
        with self.assertRaisesRegex(ValueError, "anima_triton_rope"):
            Settings(data_dir=Path("."), anima_triton_rope="auto")
        with patch.dict("os.environ", {"LUMACARVE_ANIMA_TRITON_ROPE": "experimental"}):
            self.assertEqual(Settings.from_env().anima_triton_rope, "experimental")

    def test_anima_pipeline_build_wires_rope_only_when_enabled(self):
        from pathlib import Path
        from types import ModuleType
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
            anima_rope, "install_anima_rope_triton",
            return_value=anima_rope.AnimaRoPEReport(1, "test"),
        ) as install:
            AnimaAdapter(Settings(data_dir=Path("."), inference_offload="full"))._build(Path("/fixture/anima"))
            install.assert_not_called()
            AnimaAdapter(Settings(
                data_dir=Path("."), inference_offload="full", anima_triton_rope="experimental",
            ))._build(Path("/fixture/anima"))
            install.assert_called_once_with(fake_pipe)


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
