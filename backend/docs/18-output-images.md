# 18 · Anima 输出 PNG 安全读取 API

对应源码：`lumacarve_server/routers/outputs.py`；测试：`tests/test_outputs.py`。

`GET /api/v1/outputs/{output_id}` 仅允许 32 位十六进制 UUID 输出 ID，读取 `Settings.outputs_dir/{output_id}.png` 中已经保存的真实结果。路径不可包含分隔符、绝对路径、任意扩展名；不存在则返回 404。

图片由 `AnimaAdapter.run()` 使用临时文件加 `os.replace` 原子发布，任务结果只存 `output_id` 等可审计元信息。API 不返回完整本地绝对文件路径，也不会打开下载中的模型文件。响应仅在本地 FastAPI Host/Origin 保护下使用。

此 API 已准备供前端图像工作台和作品画廊读取。当前 UI 尚未连接该接口；不要把演示画廊当成模型输出。
