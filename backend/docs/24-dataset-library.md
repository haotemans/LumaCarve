# 24 · Persistent Dataset Library / 数据集持久化

**源码**：`lumacarve_server/datasets.py` + `routers/datasets.py`  
**测试**：`tests/test_datasets.py`  
**前端**：`frontend/src/vue/views/DatasetsView.vue`、`TrainingView.vue`

## 已实现的用户闭环

- 用户在 Vue 页面创建具名数据集并上传 PNG、JPEG、WebP 图片；可同时选取配对的 `.txt` 或 `image.tags.txt`。浏览器按文件名关联 caption，并发上传至多三个请求；每个请求都是完整的服务端事务。
- 服务端流式读取图片（单文件默认上限 25 MiB）、检查 Pillow 格式/尺寸和图像有效性，内容 SHA-256 用于同一训练集内去重。
- 真实存储位置是 `LumaCarveData/datasets/<id>/<sha256>.<ext>`，同目录 `LumaCarveData/datasets/<id>/<sha256>.tags.txt`。图片和标签一一对应，文件不会散落到全系统任意目录。
- `LumaCarveData/datasets.sqlite3` 存储数据集名称、图片原始文件名、尺寸/大小、caption 与时间戳，列表使用有界分页。纯元数据调用不导入 Torch、不初始化 CUDA、不访问 GPU。
- 更新 Caption 原子写入 sidecar；删除图片同步删除文本与索引；应用重启后能重新读取数据集。
- 当前训练 Worker 未接入：训练页可预览真实数据集，**不会虚假启动训练**。

## REST API

| Method | URL | 功能 |
|---|---|---|
| `GET` | `/api/v1/datasets` | 数据集与真实样本数量 |
| `POST` | `/api/v1/datasets` | `{id,title}` 建立数据集，slug 限制 1–48 字符 |
| `GET` | `/api/v1/datasets/{id}/images?limit=48&offset=0` | 分页获得 caption/文件元信息 |
| `POST` | `/api/v1/datasets/{id}/images` | Multipart `file` 与可选 `caption` |
| `GET` | `/api/v1/datasets/{id}/images/{sha256}` | 同源图片访问，强制 nosniff |
| `PUT` | `/api/v1/datasets/{id}/images/{sha256}/caption` | `{caption}` 更新 UTF-8 标签 |
| `DELETE` | `/api/v1/datasets/{id}/images/{sha256}` | 删除图片及对应 caption |

`limit` 为 1–100，`offset` 为 0–1000000。数据集标识只允许小写字母/数字、`_`、`-`；图片只通过长度严格的 SHA-256 ID 访问，拒绝 `../` 与符号链接逃逸。

## 性能与一致性

- 使用一个持久 SQLite 索引与按请求短连接，读页数有界；图片本体由 FileResponse 流式提供。
- 上传写入所在数据集的临时文件，再校验、按哈希去重、原子搬迁并保存 sidecar，写入索引。无效图片、超额文件和重复内容不会进入数据集索引。
- Caption 是显式保存：UI 有未保存提示，切换图片/数据集/翻页会提示避免覆盖用户编辑。
- 现版本没有实现高级训练数据分桶、标签自动优化、全量数据集批量导出、跨用户权限，后续扩展应单独设模块与测试。

## 验收

```bash
PYTHONPATH=backend python -m unittest discover -s backend/tests -p 'test_datasets.py' -v
```

测试覆盖 CRUD、标签持久化、进程重建、内容去重、非法上传、跨目录引用及跨站 Origin 拦截；无需 GPU。
