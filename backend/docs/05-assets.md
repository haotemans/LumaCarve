# 05 · 图片素材管理（assets.py）

对应代码：\`lumacarve_server/assets.py\`、\`routers/assets.py\`；测试：\`tests/test_assets.py\`。

接口：
- \`POST /api/v1/assets\`：\`multipart/form-data\`，字段名 \`file\`，上传 PNG、JPEG、WebP。
- \`GET /api/v1/assets/{sha256}\`：通过内容哈希获取图片。

上传采用分块写入磁盘，限制总字节数，Pillow 验证完整图片解码与像素数量，避免仅依赖上传时的 MIME 字段。相同内容只保存一次，文件名为 \`sha256.ext\`，外界不能指定存储路径。导入的图片保留原始字节，方便后续读取图像元数据。

**限制：**该 API 面向可信的本地桌面工作台；还未加入用户身份、配额、历史清理或媒体隔离，不允许直接暴露公网。只有通过该接口登记的图片能作为后续生成任务输入。蒙版单独作为 PNG 上传，后端还需在执行时验证尺寸匹配。
