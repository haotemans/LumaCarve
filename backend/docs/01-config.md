# 01 · 配置与数据目录（config.py）

对应代码：\`lumacarve_server/config.py\`。对应测试：\`tests/test_server.py\`。

- 默认数据目录是仓库根目录的 \`LumaCarveData/\`；可以通过 \`LUMACARVE_DATA_DIR\` 改到外部 SSD，代码目录不会混入用户权重。
- 目录分别是 \`model/{dit,te,vae,lora,checkpoints}\`、\`assets/\`、\`outputs/\` 与 SQLite 数据库。
- \`LUMACARVE_HOST=127.0.0.1\`、\`LUMACARVE_PORT=8000\`。当前只允许来自 \`localhost:5173\` 和 \`127.0.0.1:5173\` 的浏览器跨域请求。
- \`LUMACARVE_INFERENCE_OFFLOAD=auto|full|model_cpu\` 供后续 GPU 适配器使用；不是已经测量的优化结果。
- `LUMACARVE_ANIMA_TRITON=off|experimental`：默认 `off`。显式启用时仅在真实加载 Anima 后安装可回退的 Cosmos AdaLN-Zero 实验性 Triton Kernel，详见 [20-anima-triton.md](20-anima-triton.md)。
- \`LUMACARVE_ALLOW_MODEL_DOWNLOAD=0\` 默认拒绝联网下载；首次下载必须由用户显式开启并接受模型许可。
- 默认文件上限 25 MiB、图像解码上限 4000 万像素、最大排队任务 16。

**安全边界：**默认仅本机访问，未实现账号认证；不要通过端口映射把本地 API 暴露到互联网。多用户部署需另加身份鉴权、限流与隔离。


## 默认目录和旧项目兼容

全新安装的数据目录是仓库根目录 `LumaCarveData/`。若已有旧版 `backend/LumaCarveData/`，新版自动继续使用原位置，不会迁移模型、数据集、生成图或 SQLite 数据库。当两个目录同时存在，也优先沿用旧目录，除非通过 `LUMACARVE_DATA_DIR` 显式选择新位置。安装器依赖报告固定在根目录，可能和旧后端数据目录不同。
