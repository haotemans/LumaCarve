# 22 · Anima Cosmos 三段 Gated Residual Triton Fusion

- 实现：`backend/lumacarve_runtime/kernels/anima_residual.py`（局部安装、选择、回退）。
- GPU Kernel：`backend/lumacarve_runtime/kernels/_anima_residual_triton.py`。
- 测试：`backend/tests/test_anima_residual.py`（CPU/Mock + 可选 CUDA 数值一致性）。
- 显式基准：`tools/benchmark_anima_residual.py`。
- 接入：`backend/lumacarve_server/config.py` 与 `backend/lumacarve_server/adapters/anima.py`。

## 模型专用的优化点

Diffusers v0.42.1 的 `CosmosTransformerBlock` 在自注意力、交叉注意力、FeedForward 的每一步之后都执行相同操作：

```python
hidden_states = hidden_states + gate * branch_output
```

这通常需要一个 gate 乘法和一个 residual 加法以及一个中间张量。本实现用一个 Triton Kernel 替换**三个阶段各自的乘加**，避免中间乘积写回，不改 Q/K/V 投影、注意力算法、GELU、GEMM、模型参数或 LoRA。

核心执行流（只在可兼容的推理路径采用）：

```text
norm1 → Attention → fused(residual, gate, attn)
norm2 → CrossAttention → fused(residual, gate, cross)
norm3 → GELU FeedForward → fused(residual, gate, ff)
```

`GELU` 和 `Linear` 仍由 Diffusers/PyTorch 调度：GELU 本身通常已经是单一逐元素 Kernel，盲目引入一个 Triton GELU 可能毫无收益。只有在真实 GPU Profile 确认 FFN 瓶颈并证明端到端收益后，才考虑融合 GELU + GEMM epilogue。

## 默认安全与选择条件

`LUMACARVE_ANIMA_TRITON_RESIDUAL=off|experimental`；默认 `off`，需明确启用。

必须符合：
- 完整 Anima 模型加载成功、拥有原生未被其他工具包装的 `CosmosTransformerBlock`；
- 没有 `before_proj` / `after_proj`、没有 ControlNet residual；
- 无训练梯度、ONNX、Torch JIT tracing、`torch.compile` 捕获；
- 三个操作数 `residual`、`gate`、`branch_output` 都是 CUDA，具有相同 FP16/BF16/FP32 dtype；
- `residual`、`branch_output` 是相同的 `[B,S,C]`；`gate` 为 `[B,1,C]` 或 `[B,S,C]`，最后一维 stride=1（包括 Diffusers `chunk(3)` 的非连续 gate view）；
- Channel 数不超过 8192；其它不匹配场景保持原生 PyTorch。

融合 Kernel 以 FP32 暂存乘加，同时在 `gate * branch_output` 后按原 Tensor dtype 舍入，再加 residual，以尽可能贴近 PyTorch 的 FP16/BF16 行为；禁用 `enable_fp_fusion`，不进行 Triton Autotune。

Patch **只作用于当前 Pipeline 的确切 block 实例**，不替换 Diffusers 类全局方法，亦不干扰 AdaLN 和 RoPE 两项先前实验（各自独立开关）。GPU 首次实际使用才触发 JIT，没有预测网络或运行期候选竞赛。

## 异常处理和限制

- 无 Triton、类型不兼容或存在预先注册的 forward wrapper，安装阶段直接跳过。
- 每个 Pipeline 使用共享断路器。首次直接 Kernel/JIT 调用出错后禁用当前 Pipeline 的 residual 加速，当前 block 用原生的 `residual + gate * branch` 接着计算，后续 block 调回原始 `forward`。
- **CUDA 异步错误不一定能被当前调用捕获**，因此不能以此机制替代 GPU 数值验收或可靠性测试。
- 当前方案不是完整 FFN Triton 重写，不承诺 GELU/Linear 加速百分比。真实目标是更少的 Kernel 启动和临时内存写回。
- **尚未完成实机 GPU/模型整图画质和性能验证**，默认不可作为用户稳定路径启用。

## 测试与手动基准

```powershell
# CPU/Mock 可在普通 CI 上执行，CUDA 检查在无 GPU 时 skip
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_anima_residual.py -v

# 有 CUDA/Triton 的机器，用户主动运行；JIT 时间与热运行时间单独汇报
.\.venv\Scripts\python.exe tools\benchmark_anima_residual.py --batch 1 --tokens 4096 --channels 2048 --dtype bf16
```

验收需要在同一模型/权重/随机种子/分辨率下比较完整 Anima 的冷启动耗时、热运行耗时、峰值显存、图像误差，以及同时启用 AdaLN + RoPE + Residual 时的交互影响。

## 源码与参考

Diffusers CosmosTransformerBlock：<https://github.com/huggingface/diffusers/blob/v0.42.1/src/diffusers/models/transformers/transformer_cosmos.py>。原项目为 Apache-2.0；本模块是对计算语义的独立实现，保留相关第三方归属和许可义务。
