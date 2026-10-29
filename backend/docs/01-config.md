# 01 · 配置与数据目录（config.py）

对应代码：\`lumacarve_server/config.py\`。对应测试：\`tests/test_server.py\`。

- 默认数据目录是仓库根目录的 \`LumaCarveData/\`；可以通过 \`LUMACARVE_DATA_DIR\` 改到外部 SSD，代码目录不会混入用户权重。
- 目录分别是 \`model/{dit,te,vae,lora,checkpoints}\`、\`assets/\`、\`outputs/\` 与 SQLite 数据库。
- \`LUMACARVE_HOST=127.0.0.1\`、\`LUMACARVE_PORT=8000\`。当前只允许来自 \`localhost:5173\` 和 \`127.0.0.1:5173\` 的浏览器跨域请求。
- \`LUMACARVE_INFERENCE_OFFLOAD=auto|full|model_cpu\` 供后续 GPU 适配器使用；不是已经测量的优化结果。
- \`LUMACARVE_ALLOW_MODEL_DOWNLOAD=0\` 默认拒绝联网下载；首次下载必须由用户显式开启并接受模型许可。
- 默认文件上限 25 MiB、图像解码上限 4000 万像素、最大排队任务 16。

**安全边界：**默认仅本机访问，未实现账号认证；不要通过端口映射把本地 API 暴露到互联网。多用户部署需另加身份鉴权、限流与隔离。
