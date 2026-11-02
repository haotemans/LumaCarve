# 23 · Anima/Cosmos FFN 第一层 Linear + GELU Triton 融合候选

代码：
- `backend/lumacarve_runtime/kernels/anima_ffn.py`：严格的模块识别、推理限制、断路器和回退。
- `backend/lumacarve_runtime/kernels/_anima_ffn_triton.py`：第一次 FFN GEMM + 精确 GELU 的单 Kernel。
- `backend/lumacarve_server/config.py` 和 `backend/lumacarve_server/adapters/anima.py`：显式启用。
- `backend/tests/test_anima_ffn.py`：CPU Policy + 可选 CUDA 数值等价测试。
- `tools/benchmark_anima_ffn.py`：**手动启动** CUDA Eager/Triton/可选 TorchInductor 比较。

## 核心取舍：优先真实收益，不要盲目重写 FFN

Diffusers v0.42.1 中 Anima 使用 `CosmosTransformerBlock`，其 FFN 为 `FeedForward(hidden_size, mult=mlp_ratio, activation_fn="gelu")`，计算形态：

```text
h -> Linear(K -> N) -> GELU(exact/erf) -> Dropout(p=0) -> Linear(N -> K)
```

本阶段仅把第一个 `Linear` 与接下来的 **GELU(exact)** 合并为单个 Triton GEMM kernel，消除 Linear 输出在被 GELU 读取前的额外显存写回。第二个 Linear 和 Dropout 仍由 PyTorch、cuBLAS 等成熟后端执行；**不重写完整 DiT/Attention/LoRA**。

GELU 不是 tanh 近似，必须采用原版 `torch.nn.functional.gelu(..., approximate="none")` 的定义：

```text
GELU(x) = 0.5 * x * (1 + erf(x / sqrt(2)))
```

Triton 将 GEMM 的 FP32 累加结果转换回 FP16/BF16，再以 FP32 计算 GELU 并转换回输入 dtype。这一中间舍入边界用于接近独立的 PyTorch F.linear + F.gelu，但不同 GPU/CUBLAS Kernel 的累加顺序仍可能造成细微偏差。

**这不保证提速**：常规 cuBLAS GEMM 可能比手写 Triton 更快，TorchInductor 也可能完成有效融合。如果完整 Anima 实机对照显示没有收益，应停用或删除该候选，而非因使用 Triton 就默认启用。

参考：
- [Diffusers CosmosTransformerBlock](https://github.com/huggingface/diffusers/blob/v0.42.1/src/diffusers/models/transformers/transformer_cosmos.py)
- [Diffusers FeedForward](https://github.com/huggingface/diffusers/blob/v0.42.1/src/diffusers/models/attention.py)
- [Diffusers GELU](https://github.com/huggingface/diffusers/blob/v0.42.1/src/diffusers/models/activations.py)

## 功能控制与兼容性

`LUMACARVE_ANIMA_TRITON_FFN=off|experimental`，默认 `off`。**仅在 `LUMACARVE_INFERENCE_OFFLOAD=full` 下尝试安装**，避免 CPU Offload/组件驻留管理器的回调被 GPU 直连 GEMM 跳过。即使打开实验开关，`auto` / `model_cpu` 仍完整走原 FFN。

安装还要求：

1. 原始 `CosmosTransformerBlock` → 原始 `FeedForward`，恰好三段模块、标准 `GELU(approximate="none")`、零 Dropout、原始 `torch.nn.Linear`。
2. 不覆盖实例级 `forward` 包装；拒绝 PEFT LoRA wrapper、Accelerate hook、编译模块和已注册的 Linear 级 forward/backward hook。
3. 推理时无 autograd、Torch JIT tracing、ONNX export、TorchDynamo 编译和 CUDA autocast；模块处于 `eval()`。
4. Tensor 是 contiguous CUDA `[B,S,K]`，输入和权重均为 FP16/BF16 同 dtype，同 GPU；`K,N` 是 16 的倍数、位于安全范围内，`B*S >= 32`。
5. Optional Bias 必须与 CUDA、dtype、输出通道维度一致。

只 patch 当前模型的 **GELU Activation 模块实例**，不修改模型 checkpoint、权重、LoRA 或 Diffusers 全局函数。FFN 和原生 `Module.__call__` 仍被使用，运行时验证权重、执行钩子和后续注入的 LoRA。首次尝试失败后该模型所有已安装的 FFN 融合实例共享一次断路器，剩余步骤回退原始 `F.linear → F.gelu` 路径。

## 正常推理无额外性能预测

此实现：
- 不自动执行 `triton.autotune`、`torch.profiler`、GPU benchmark 或显存预测。
- 不引入新的神经网络预测器。
- 只在实验开关开启并满足条件时调用 Triton；第一次可能有 JIT 编译开销，之后复用内核缓存。
- 准备开销来自 CPU 元数据检查及运行时 Python 调用，尚未量化；是否值得应用须看真实端到端收益。

## 测试与验收

```powershell
# CPU/mock 自动验证；没有 CUDA 时数值测试自动 skip
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_anima_ffn.py -v

# 手动 CUDA microbenchmark：冷 JIT 与热启动统计分开
.\.venv\Scripts\python.exe tools\benchmark_anima_ffn.py --tokens 512 --in-features 1024 --out-features 4096 --dtype bf16

# 只有明确希望比较 TorchInductor 时才启用；编译开销可能很高
.\.venv\Scripts\python.exe tools\benchmark_anima_ffn.py --tokens 512 --in-features 1024 --out-features 4096 --dtype bf16 --compare-compile
```

## 必须满足的真实 GPU 验收

- 数值：BF16 / FP16、Bias 有无、Token 不是 32 的倍数及输入形状变化；与同版本 PyTorch 对照。
- 性能：Eager、TorchInductor、Triton 三种路径，在相同 GPU 和形状的冷启动成本及热时延。
- 整图：相同 Anima 权重、LoRA、Seed、分辨率，记录图像误差、全图延迟、峰值显存。
- 兼容：LoRA 热切换、低显存卸载以及已有的 AdaLN/RoPE/Residual 实验组合。

**当前状态：未有真实 CUDA / Anima GPU 出图结果，不提供性能加速承诺，也不推荐在日常自动均衡中默认启用。**
