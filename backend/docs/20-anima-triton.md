# 20 · Anima Triton AdaLN-Zero 实验加速

**源码**：`lumacarve_runtime/kernels/anima_adaln.py`（懒加载、匹配及安全回退）、`lumacarve_runtime/kernels/_anima_adaln_triton.py`（GPU Kernel）；**测试**：`tests/test_anima_triton.py`；**基准工具**：`../tools/benchmark_anima_triton.py`。

## 范围与来源

针对目前 LumaCarve 使用的 Hugging Face Diffusers `AnimaModularPipeline`：`CosmosTransformer3DModel` 的每个 `CosmosTransformerBlock` 含三个 `CosmosAdaLayerNormZero`。参照 Diffusers 的公开实现，保持 SiLU、两层 Linear、`temb` 加法和 `gate` 不变，只将 `LayerNorm(eps=1e-6)`、`hidden_states * (1 + scale) + shift` 合并为单一 Triton Kernel。参考：[`transformer_cosmos.py`](https://github.com/huggingface/diffusers/blob/main/src/diffusers/models/transformers/transformer_cosmos.py)。新增实现为 LumaCarve 自有实现；Diffusers 源码使用 Apache-2.0，保留其原始版权与许可。

此优化仅涉及**推理前向**，不是 LoRA/全量训练的反向传播实现。它不替代 Attention、GEMM 或整个模型，也不保证全图加速。

## 默认关闭与启用

默认 `LUMACARVE_ANIMA_TRITON=off`：完全沿用 Diffusers，启动 API 时不加载 Torch、Diffusers 或 Triton。

设置 `LUMACARVE_ANIMA_TRITON=experimental`：首次实际模型加载后扫描该 Pipeline 的 Cosmos blocks，只 patch 精确的 `CosmosAdaLayerNormZero` 类型，且 LayerNorm `elementwise_affine=False`、`eps=1e-6`。不全局猴子补丁其它 Pipeline；不修改参数或 State Dict。

```powershell
$env:LUMACARVE_INFERENCE_BACKEND="anima"
$env:LUMACARVE_ANIMA_TRITON="experimental"
```

**条件**：有 CUDA GPU，安装匹配版本的 PyTorch / Triton，以及包含 Cosmos 模型的 Diffusers。Triton 不可用、模型结构不符时保留原计算路径；Triton 首次执行时若失败，会针对该 Pipeline 的全部已安装位置触发一次断路器，退回原始 forward，不在采样循环里重复编译失败内核。Windows Triton 兼容性需用户逐机验证；不要对所有 Windows 环境强装 Triton。

## Kernel 计算与正确性约束

输入 `x` 为 `[B, S, C]` 且 contiguous；`scale/shift` 为 `[B, 1, C]` 或 `[B, S, C]` 且最后一维连续（支持 `chunk` 返回的分片 Strided View，无需复制），同 GPU/同 dtype。支持 CUDA FP16/BF16/FP32，`1 <= C <= 8192`。按 `[B*S]` 行做 FP32 均值/方差归约，并保留 PyTorch LayerNorm 和后续逐元素运算的中间 dtype 舍入。任一条件不满足时调用原始 Diffusers forward。

本 Kernel 不使用 `triton.autotune`，不会自动对候选配置进行 GPU 试跑；首次执行仍要 JIT 编译，因此不适合作为未知显卡上的默认自动均衡路线。正常运行不开启后台预测、不会在每个采样步运行 profiling。

## 测试和性能核验

CPU/Mock 测试（不要求 CUDA / Triton）：

```shell
cd backend
python -m unittest discover -s tests -p test_anima_triton.py -v
```

在**用户明确选择** GPU 基准测试时运行，首次 JIT 成本在计时之前支付，输出单 Kernel PyTorch/Triton 毫秒和加速比例：

```shell
python tools/benchmark_anima_triton.py --tokens 4096 --channels 2048 --dtype bf16
```

GPU 数值测试在 `tests/test_anima_triton.py` 中，未安装 Torch/Triton 或无 CUDA 时会 skip。需要在目标显卡上先通过 FP16、BF16、FP32 正确性测试，再通过**同分辨率、同 seed、同模型权重的完整 Anima 生成对比**确认没有不可接受的画质偏差和端到端性能倒退，方可评估是否把实验开关改为自动启用。

**当前没有 GPU 实机数据**；不得以单个 Kernel 的理论加速声称整个 Anima 模型快了多少。
