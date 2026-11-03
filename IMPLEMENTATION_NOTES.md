# LumaCarve · Vue / FastAPI 本轮完善（2026-11-03）

## 已实现

| 部分 | 改动 |
|---|---|
| 数据集后端 | SQLite 索引、受控目录图片上传、SHA256 去重、同名 `.tags.txt`、重启保持、分页/修改/删除 API |
| Vue 数据集页 | 训练集创建/选择、多图导入（最多 3 路并发）、真实缩略图、Caption 显式保存/删除、未保存拦截、分页 |
| Vue 训练页 | 可读取已有训练集与前 8 张真实样本预览；训练 Worker 仍未接通，执行按钮继续禁用 |
| 任务后端 | 一个 SQL 查询读分页任务而非每条重新连接 SQLite；状态筛选/计数/队列容量，无 CUDA 采样 |
| Vue 任务/运行页 | 按状态筛选、计数与分页；显示来自 SQLite 的排队/运行作业数量 |
| Anima 模型保护 | 普通 `.safetensors` 与真实完整 ModularPipeline 快照明确区分；后端对工作流 `checkpoint` 进行真实路径一致性检查，不再静默忽略浏览器文件夹名 |
| Vue 模型/工作室 | 仅认可服务端已确认快照、显示后端就绪状态；未安装或选择不匹配时阻止真实生成 |
| 开发启动 | Windows `tools/start-dev.ps1`（使用 npm.cmd）、Linux `tools/start-dev.sh`，两端共用 `LumaCarveData` |
| 安全与文档 | PUT CORS 预检、图片/Caption/路径验证、源码-文档-测试映射、平台启动文档 |

## 运行检查

- `PYTHONPATH=backend python -m unittest discover -s backend/tests -q`：**128 项，121 通过，7 项跳过（无可选 Rust/CUDA）**。
- `python tools/check_layout.py`：**通过**。
- `sh -n tools/start-dev.sh`：**通过**。
- 全部前端 16 个 `.ts`/`.vue` Script Setup：**TypeScript 语法解析通过**；Vue 图标引用检查通过。
- **Vue/Vite 正式构建未验证**：当前执行环境无法解析 npm 域名，无 Vue/npm 依赖包，`npm install` 无法完成。请在能访问 npm 的环境执行 `cd frontend && npm install && npm run test && npm run build`。
- **GPU 真实 Anima 推理、Triton 性能/数值、训练 Worker、Tauri 发行包未验证**；所有相关功能保持原设计的禁用/实验状态。

## Windows 试运行

```powershell
# 根目录的 .venv 与依赖已按原 setup.py 安装后
cd frontend
npm.cmd install
cd ..
.\tools\start-dev.ps1
```

然后访问 `http://127.0.0.1:5173/#/datasets`。默认不自动下载模型、不启动 GPU 推理。显式启用 Anima 时先配置完整 Hugging Face ModularPipeline 快照。

本次交付基于上传的 ZIP 直接编辑，**没有改动 GitHub main 分支或创建远端 PR**；可通过同包附带的 `.patch` 对照原始 ZIP 查看变更。
