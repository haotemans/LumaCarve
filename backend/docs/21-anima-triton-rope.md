# 21 · Anima Cosmos Self-Attention Q/K RoPE Triton Fusion

**代码**：`lumacarve_runtime/kernels/anima_rope.py`、`lumacarve_runtime/kernels/_anima_rope_triton.py`；
**测试**：`tests/test_anima_rope.py`；
**自选 GPU 基准**：`../../tools/benchmark_anima_rope.py`；
**接入**：`lumacarve_server/config.py`、`lumacarve_server/adapters/anima.py`。

## 目的与适用范围

当前 LumaCarve Anima 适配器使用 Hugging Face Diffusers ModularPipeline，底层是 CosmosTransformer3DModel。
其 `CosmosTransformerBlock.attn1` 使用 `CosmosAttnProcessor2_0`：
Q/K 线性投影和归一化后，对 Q 与 K 分别调用 Diffusers
`apply_rotary_emb(..., use_real=True, use_real_unbind_dim=-2)`。
本 PR 用**一个独立 Triton Kernel**同时执行这两个 RoPE 变换。

计算公式是半维拆分（不是相邻维度交错）：

```text
rotated(x) = concat(-x[..., D/2:], x[..., :D/2])
rope(x) = (float32(x) * cos + float32(rotated(x)) * sin).to(x.dtype)
```

保留 Diffusers 已有的 QKV 投影、Q/K 归一化、GQA 展开、Attention 后端、输出投影与 LoRA 结构，不对其他模型或 Cross Attention 做全局补丁。参考：[Diffusers Cosmos Processor](https://github.com/huggingface/diffusers/blob/main/src/diffusers/models/transformers/transformer_cosmos.py) 与 [RoPE reference](https://github.com/huggingface/diffusers/blob/main/src/diffusers/models/embeddings.py)。

## 控制与兼容

`LUMACARVE_ANIMA_TRITON_ROPE=off|experimental`，**默认 off**，和上一个 AdaLN 选项 `LUMACARVE_ANIMA_TRITON` 独立：

```powershell
$env:LUMACARVE_INFERENCE_BACKEND = "anima"
$env:LUMACARVE_ANIMA_TRITON_ROPE = "experimental"
```

满足以下全部条件才走 Triton：
- 实际已经加载 Anima Pipeline，`attn1.get_processor()` **类型精确等于** `CosmosAttnProcessor2_0`；
- 只有 forward-only CUDA 推理，不处于 autograd/ONNX/tracing/torch.compile，非 cross-attention；
- Q 与 K 均为 `[B,H,S,D]`，相同 GPU / dtype，最后一维 stride=1；
- `D` 是 16~256 之间的偶数（Anima Cosmos 常见为 128），cos/sin 均为 GPU FP32 的 `[S,D]`；
- 输入长度和设备匹配，且已安装与当前系统兼容的 Triton。

原版 `attn2` Cross Attention、条件不匹配的 Q/K 和所有训练路径保持 Diffusers 原计算。

此补丁只改当前 Pipeline 的 `attn1.processor` 实例，不修改 Diffusers 全局方法；再次调用安装器不会重复包裹。
首次 Kernel launch 可能 JIT 编译。运行时出错后，当前 Pipeline 全部已安装的 RoPE 处理器共享一次断路器，后续调用恢复原来的 Diffusers 计算，避免每次采样重复尝试失败的 Kernel。

## 性能与安全约束

- GPU Kernel 不进行 autotune、显存预测或基准试跑；只有用户明确执行基准命令才做 GPU 测速。
- CPU/Mock 测试无需模型文件、CUDA 或 Triton；不在导入包时触发 Torch/Triton。
- GPU CUDA 数值测试覆盖 FP16/BF16/FP32、非连续 Q/K Tensor，以及不同 Token 数/Head 数。
- 开销主要来自重复进行的独立 Q/K RoPE：合成一个 launch，并共享 cos/sin 读取；但不是把 Attention 也融合进同一个 Kernel。
- **尚未真实 GPU 验证和测量**。默认不启用；需要同时通过整图模型输出、完整生成时延、冷启动 JIT 开销、峰值显存等实机对照，才能考虑进入 `auto`。

## 运行测试

```powershell
# CPU/mock tests; CUDA 数值测试会在没有 Triton 或 CUDA 时 skip
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_anima_rope.py -v

# 在显式选择 CUDA 基准测试时才执行；并在计时前完成首次 JIT
.\.venv\Scripts\python.exe tools\benchmark_anima_rope.py --tokens 4096 --heads 16 --channels 128 --dtype bf16
```

注意：与单个 Kernel 的输出数值一致，并不代表已经在全部模型版本和设备上验证完整生成画质。性能比较必须在同一 GPU、同一 seed、同一模型/LoRA、相同输入上进行。
