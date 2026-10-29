# 12 · 魔搭 ModelScope 模型下载（model_downloads.py）

对应代码：`lumacarve_server/model_downloads.py`、`routers/downloads.py`；测试：`tests/test_downloads.py`。

## 工作方式

- `LUMACARVE_DOWNLOAD_REGION=cn`：默认魔搭 ModelScope。选择 `global`：默认 Hugging Face。请求允许显式覆盖 `provider`。
- **必须**设置 `LUMACARVE_ALLOW_MODEL_DOWNLOAD=1` 才能通过 HTTP API 发起下载。只读模型目录和健康检查不会联网。
- `GET /api/v1/downloads/catalog` 返回模型条目、来源及许可说明。
- `POST /api/v1/downloads` 接收 `{"model_id":"qwen-image-2.1","revision":"master"}`，返回任务 ID。
- `GET /api/v1/downloads/{id}` 返回 `queued/running/completed/failed`，只有 SDK 完成后才标记完成；失败保留 `.partial` 目录用于续传。
- 下载路径：`LumaCarveData/model/bundles/<model-id>/<revision>/`。限制目录名、仓库白名单、一次只下载一个，避免占满带宽和 SSD。
- SDK 调用：`modelscope_hub.HubApi().download_repo(repo_id,"model",revision,local_dir,max_workers=4)`；国际模式用 `huggingface_hub.snapshot_download`。
- 明确保留整套 Diffusers 权重文件及配置，不能只下载单个 DiT safetensors 就宣称模型可运行。

## 已核实初版目录

| LumaCarve ID | 魔搭 ModelScope | 国际 Hugging Face |
|---|---|---|
| `qwen-image-2.1` | `Qwen/Qwen-Image-2.1` | `Qwen/Qwen-Image-2.1` |
| `moss-image-base` | `openmoss/MOSS-Image-Base` | `OpenMOSS-Team/MOSS-Image-Base` |

Anima Base、Krea 2 RAW 需要核实可用仓库版本与具体许可后再添加。**不猜模型仓库名称，不使用未经审核的第三方镜像下载器。**

ModelScope SDK 提供断点续传和可用的 SHA-256 校验。**若上游没有提供可信 hash 则不能承诺端到端完整性校验**；下一阶段可加入固定提交 ID、权重 manifest 与 SHA-256 签名约束。失败的 `.partial` 仅供重试，不允许进入推理。

## 资源与安全

模型可达数十 GB；下载会消耗磁盘容量并保留暂存版本。当前任务状态存于进程内，服务重启后可重新提交任务以继续保留的部分文件，尚未实现持久化下载进度统计或取消 API。首次下载前用户应自行确认模型许可、磁盘空间和版本。

参考：[ModelScope Hub](https://github.com/modelscope/modelscope_hub)、[Qwen-Image-2.1](https://modelscope.cn/models/Qwen/Qwen-Image-2.1)、[MOSS-Image-Base](https://modelscope.cn/models/openmoss/MOSS-Image-Base)。
