# 10 · Attention 选择策略（attention.py）

对应代码：`lumacarve_runtime/attention.py`；测试：`tests/test_attention.py`。

## 设计

- 所有 GPU 可用环境都可退回到 PyTorch `scaled_dot_product_attention` (SDPA)，无需额外 `flash-attn` 依赖。
- 明确分离**包已安装**、**GPU/精度/张量形状兼容**与**当前模型适配器已经接线**三种状态。仅凭 `importlib.find_spec` 存在，不代表可以安全调用对应内核。
- 用户选择 `flash` 后先确认能力，再使用 FlashAttention；不满足要求则回退 SDPA。
- `sage` 必须显式选择且只考虑推理任务；默认不将其用于反向传播训练。
- `auto` 优先已验证的 FlashAttention；否则 SDPA。不会仅因为 SageAttention 可导入就无条件改成低比特近似注意力。
- **FlashAttention 与 SageAttention 不会在同一注意力调用中同时执行。** 安装两个是供选择，不是将它们叠加。
- 后续每个模型适配器需要对显卡架构、BF16/FP16、head_dim、掩码、Dropout、训练反向支持进行独立检查；真实性能选择需在目标设备跑基准。

目前完成的是**决策代码与单元测试**，并非 Diffusers/Qwen/Anima 的真实 attention processor 替换。请勿把这一模块视为已证实提速。
