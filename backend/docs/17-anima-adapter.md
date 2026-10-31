# 17 · Anima Base 1.0 本地推理 Adapter

对应源码：`lumacarve_server/adapters/anima.py`；测试：`tests/test_anima.py`。本 Adapter 是 LumaCarve 第一个真正调用 PyTorch 模型的可选后端，**尚未有 GPU 实机通过的端到端基准结果**。

## 架构来源

采用 [Diffusers 官方 Anima ModularPipeline](https://huggingface.co/docs/diffusers/main/en/api/pipelines/anima)，对应 CosmosTransformer3DModel、Qwen3 0.6B Text Encoder、AnimaTextConditioner、T5 Tokenizer、AutoencoderKLQwenImage VAE。Diffusers 通过 `ModularPipeline.from_pretrained(local_directory)` 解析配置，`load_components(dtype=torch.bfloat16)` 加载权重，然后运行 `pipe(prompt=...)`。无需引入 ComfyUI 执行代码。

## 目标模型目录

下载器配置详见 [12-modelscope-downloads.md](12-modelscope-downloads.md)：

- 当前可执行的版本是 `model/bundles/anima-base-1/huggingface/main/`（完整 Diffusers ModularPipeline，标记 `.lumacarve-complete`）。
- 也能通过 `LUMACARVE_ANIMA_MODEL_PATH` 选择已有**完整 ModularPipeline** 本地目录。
- 魔搭 `circlestone-labs/Anima` 是原始 ComfyUI split 模型；本 Adapter 不把这些单文件权重错误当成 ModularPipeline。
- 完整目录必须有 `modular_model_index.json` 及 transformer、vae、text_encoder、text_conditioner、tokenizer、t5_tokenizer、scheduler 七个组件目录。

## 选择并启动

安装完成且已下载模型后，设置 `LUMACARVE_INFERENCE_BACKEND=anima`，再启动 API。**未设置时仍保持 DisabledInference，HTTP 503，不会自动下载。**

```powershell
$env:LUMACARVE_INFERENCE_BACKEND="anima"
$env:LUMACARVE_INFERENCE_OFFLOAD="auto"
cd backend
..\.venv\Scripts\python.exe -m uvicorn lumacarve_server.app:app --host 127.0.0.1 --port 8000
```

只有用户提交真实工作流任务后，Worker 才 import Torch、初始化 CUDA 和载入本地权重。常规健康检查不会加载模型。`ready` 只验证文件结构与已安装依赖，GPU 真实兼容性在运行时检查。

## 低显存与速度

- `inference_offload=auto`（默认）或 `model_cpu`：采用 Diffusers `ComponentsManager.enable_auto_cpu_offload(device="cuda")`，由组件管理器自动在系统内存与 GPU 间调度。
- `inference_offload=full`：把整个 pipeline 常驻 CUDA；仅推荐显存充足的 GPU。
- 默认 BF16，当前 GPU 不支持时退回 FP16；不主动请求 FP32。实际 Qwen3/Text Conditioner 与 GPU 的兼容性仍需实机验证。
- 同一个 Python Adapter 实例缓存已加载 pipeline；连续生成不重复加载基础模型。
- LoRA Stack 使用 `model/lora/*.safetensors` 文件，按提交顺序调用 `load_lora_weights`、`set_adapters`，调整列表时先 unload 再重新装载；不复制基础模型。
- 当前通过官方 `pipe(...)` 完整采样后才能检查取消。没有逐扩散步回调的取消保障，**不能宣传为即时中断**。
- 输出存储在 `outputs/{uuid}.png`，成功提交后 SQLite Job 保存生成的 `output_id` 与真实参数；任务失败不会返回伪造图像。

## 工作流限制

第一阶段**仅支持文字生成**（intent=create），不是 Anima 的完整图像编辑能力。Graph 负责校验模型 ID、Prompt、Negative Prompt、Sampler、LoRA、VAE、Output。参考图、蒙版、透明背景提交会明确失败。尺寸选项保留当前 7 个画幅，按 16 的倍数选择接近的分辨率。图像生成会使用一颗固定 seed 的 CPU Generator。

未来迭代：独立原生魔搭 Adapter、图生图与遮罩编辑、SageAttention/FlashAttention 的真实兼容性测试、逐步取消、输出 API/前端画廊及 8GB/16GB/24GB 显存基准。

## 开发与测试

```powershell
py -3.11 -m unittest discover -s backend/tests -p test_anima.py -v
```

CPU 单元测试通过可证明工作流转换、加载生命周期和保存行为，不证明任何显卡已经实际生成图片。Diffusers ModularPipeline Anima 支持依赖现行版本（建议先固定已验证的 0.40+），不能使用过旧的 Diffusers 自动安装后宣称可用。


## 测试覆盖

`backend/tests/test_anima.py` 使用可控的 Mock Pipeline（真正写出 PNG 文件）验证：本地目录完整性、来源隔离、Graph 参数编译、连续生成复用同一模型、两个 LoRA 与清空堆栈、取消不发布文件，以及 API → SQLite → Adapter → PNG 输出端到端链路。该测试**不加载真实权重，不能替代 GPU 烟雾测试**。
