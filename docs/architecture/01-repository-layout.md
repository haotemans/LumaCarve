# 01 · 项目文件夹结构

## 当前与逐步迁移的目标

本项目使用 **Modular Monorepo（模块化单仓库）**。不是多个独立产品，也不为模型单独建仓库。以下树形结构中的部分目录是**规划位置**，尚未全部创建，详细状态见右侧说明。

```text
LumaCarve/
├── .github/workflows/                  # CI：前端、后端、目录规范
├── docs/
│   └── architecture/                   # 全局架构、技术栈、ADR
├── frontend/
│   ├── package.json
│   └── src/
│       ├── main.ts                     # Vue 3 入口
│       ├── vue/
│       │   ├── App.vue                  # 全局导航、工作台外壳
│       │   ├── router.ts                # Hash Router
│       │   ├── stores/studio.ts         # Pinia 工作流与真实任务状态
│       │   ├── views/                   # 生成、训练、画廊、模型、数据集、任务、系统
│       │   └── styles.css               # 静态设计系统
│       └── features/image-studio/      # 跨框架 API、workflow JSON、Runtime 解析
├── backend/
│   ├── pyproject.toml                  # 一个 Python 项目、可选依赖组
│   ├── lumacarve_server/
│   │   ├── app.py                      # FastAPI 装配
│   │   ├── config.py                   # 本地环境配置
│   │   ├── routers/                    # 仅 HTTP 请求/响应和错误映射
│   │   ├── services/                   # 规划：模型/下载/项目等业务服务
│   │   ├── storage/                    # 规划：SQLite、文件资产与缓存索引
│   │   └── adapters/                   # 规划：模型家族推理/训练适配器
│   ├── lumacarve_runtime/
│   │   ├── graph.py                    # DAG 执行规划
│   │   ├── executor.py                 # 执行循环接口
│   │   ├── residency.py                # GPU/RAM/磁盘驻留策略
│   │   ├── budget.py                   # 资源预算
│   │   └── attention.py                # Attention 后端选择策略
│   ├── docs/                           # 已有后端逐模块文档
│   └── tests/                          # 后端无 GPU 单元测试
├── scheduler/                          # Rust 调度核心（渐进接入；不是独立模型计算进程）
├── tools/                              # 安装、结构检查、将来诊断/基准脚本
├── project-layout.toml                 # 源码 ↔ Markdown ↔ 测试映射
├── .venv/                              # 唯一 Python 虚拟环境（Git 忽略）
└── LumaCarveData/                      # 当前默认用户数据（Git 忽略）
```

## 依赖方向

```text
Vue UI → HTTP /api/v1 → FastAPI Routers → 业务 Services
                                         ↓
                       Rust 工作流编译 / 资源调度（PyO3）
                                         ↓
                             模型 Adapter（按需导入）
                                         ↓
                        PyTorch / CUDA / 模型与缓存
```

- `frontend` **不直接导入** Python、PyTorch、CUDA 或 GPU 执行模块；业务状态由 API 同步。
- `routers` 不包含长时间运行的模型推理，不自行管理 GPU 驻留；仅做参数校验、调用业务服务、状态映射。
- `services` 调用 Rust 调度决策接口并触发 Python 模型执行；原有 `lumacarve_runtime` 仍承担过渡期策略、真实模型驻留适配。Rust 库本身不依赖 FastAPI。
- 模型适配器以统一协议承接 Qwen-Image、Anima、MOSS、Krea 等独立格式；不要在 `app.py` 中写每个模型的分支。
- 训练和推理未来共享一个 GPU 资源仲裁器；不把训练放进另一个不受控的 CUDA 进程。
- 当前 Vue 页面放在 `frontend/src/vue/views/`，可重用领域协议保留在 `frontend/src/features/image-studio/`；数据定义不依赖 Vue。

## 迁移规则

1. **新增功能进 Vue 目录**：不再新增 React TSX 或多套 UI 框架，应用导航统一交给 Vue Router。
2. 现有模块迁移采用小 commit，源码与导入路径同步改，CI 通过后再移下一个。
3. 用户数据不跟随源文件移动。需要改变磁盘布局时，必须先写兼容读取、迁移器、备份和 dry-run。
4. 公开 API、工作流 JSON 的 `format` 版本、环境变量名称不能因改文件夹而无声改变。
5. Markdown 同步更新；对于新增的有执行逻辑模块，要求对应测试、失败路径说明和资源占用说明。
