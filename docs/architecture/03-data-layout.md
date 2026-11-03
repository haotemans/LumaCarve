# 03 · 用户数据目录与缓存结构

**下方树是未来完整统一数据规范，而非已经完成的迁移。** 当前已实现数据仍位于 `LumaCarveData/model/`、`assets/`、`outputs/`、根部 `jobs.sqlite3`。**新增持久化数据集**已经采用 `LumaCarveData/datasets/{dataset_id}/{sha256}.{png|jpg|webp}` 与同目录 `{sha256}.tags.txt`，元数据存储在根部 `datasets.sqlite3`。未来正式目录规划须保留当前已写入数据，不能未经迁移就更换路径。详见 [数据集模块](../../backend/docs/24-dataset-library.md)。

```text
LumaCarveData/                                # 默认位置，可由 LUMACARVE_DATA_DIR 自定义
├── models/
│   ├── bundles/
│   │   └── {provider}/{model_id}/{revision}/  # 不混淆 ModelScope 与 HF
│   ├── loras/{model_family}/
│   ├── components/{content_hash}/              # 规划：验证哈希后再共享
│   └── registry.sqlite3                       # 规划：元信息索引，非模型权重
├── downloads/
│   ├── partial/{download_id}/
│   └── manifests/{download_id}.json
├── projects/{project_id}/
│   ├── project.json
│   └── workflows/{workflow_id}.json
├── datasets/{dataset_id}/
│   ├── images/                                # 原图，不擅自压缩或重命名
│   ├── captions/                              # 一图一 txt / 来源元数据
│   └── manifest.json
├── cache/
│   ├── text-embeddings/
│   ├── latents/
│   └── previews/
├── assets/{sha256}.{ext}
├── outputs/{year}-{month}/{job_id}/
│   ├── result.png
│   └── metadata.json
├── db/jobs.sqlite3
└── logs/
```

## 存储约束

- **模型文件 = 不可变内容**：以 provider/repo/revision 为来源标识；用 SHA-256 验证完全一致后才能跨模型共用组件。
- **缓存必须可删除**：缓存索引必须包含模型修订、数据预处理参数、原图哈希、精度和 Tokenizer 版本；超预算使用有界 LRU 清理。
- **下载中 ≠ 已安装**：临时目录与正式模型目录分离，完整校验后原子标记完成；失败记录保留以支持安全重试。
- **项目可移植**：项目工作流用稳定 `format` 版本和逻辑模型 ID，而不是强制绝对磁盘路径。
- **训练集保持原始图片 + Caption**：导入后只增加索引/缓存，不覆盖用户源数据；导出支持图片与同名文本。
- **生成输出可追踪**：结果保存任务 ID、工作流版本、模型修订、LoRA 权重、Seed、预处理选项。隐私敏感信息不写入对外共享图片。
- **临时文件有预算**：下载进度与缓存提供回收机制，不允许无限占用磁盘。

## 将来迁移步骤

1. 写出实际扫描旧目录的 dry-run 清单、空间需求与冲突检测。
2. 先支持旧目录和新目录双读取，默认新写入仍保持旧位置，保证回滚。
3. 复制/硬链接（仅当同盘且内容完整）到新目录，并核验大小/哈希；不能擅自删除用户旧文件。
4. 更新下载器和模型扫描器，使二者识别同一规范目录。
5. 由用户确认后切换新写入布局；确认完成前旧目录保持只读保留。

不要只改 `Settings.models_dir` 就认为迁移完成，这会让用户现有模型“消失”。
