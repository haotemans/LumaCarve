# Image Studio · 图像工作室

LumaCarve 采用**参数式创作界面 + 内部 Graph 数据结构**。Graph JSON 仍是 API 的唯一执行配置来源，但用户不需要查看或操作节点图。公开界面以模型/LoRA/参数/预览/任务状态为主，尽可能降低 React 对 CPU 和 GPU 的占用。

| 源码 | 文档 | 职责 |
|---|---|---|
| `ImageStudioPage.tsx` | [ImageStudioPage.md](docs/ImageStudioPage.md) | 参数式工作台、输入素材、结果及任务控制 |
| `workflow.ts` | [workflow.md](docs/workflow.md) | 唯一可序列化 Graph JSON，服务端校验兼容 |
| `api.ts` | [api.md](docs/api.md) | Anima 作业提交、状态、取消、真实 PNG 输出 |
| `runtime.ts` + `RuntimeStatusPanel.tsx` | [runtime-status.md](docs/runtime-status.md) | 严格读取只读状态，无 GPU 探测/自动轮询 |
| `image-studio.css` | [image-studio-css.md](docs/image-studio-css.md) | 响应式轻量参数 UI 和状态面板 |
| `GraphCanvas.tsx`（保留） | [GraphCanvas.md](docs/GraphCanvas.md) | 旧节点编辑器代码，仅内部备用；不在工作台导入 |

## 功能真实性

- Anima Base 1.0 文字生成已接入本地 FastAPI/SQLite 作业和真实 PNG 输出，但仍需用户自行安装完整权重及兼容 CUDA，未进行 GPU 实测。
- Qwen 等模型、图像编辑和训练仍处于前端能力预设/后端开发阶段；不显示假的成功结果。
- `GET /api/v1/runtime` 提供配置状态，不代表 GPU 已运行；`auto` CPU 卸载并非尚未实现的 AMEP 智能自动均衡；Triton 实验开关不等于经过测试的性能提升。

验证命令：`cd frontend && npm run test:runtime && npm run build`。后端测试：`python -m unittest discover -s backend/tests -v`。
