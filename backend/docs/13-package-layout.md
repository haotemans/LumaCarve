# 13 · Python 包分层和 Wheel 完整性

对应配置：`../pyproject.toml`；测试：`../tests/test_packaging.py`；构建检查：`.github/workflows/backend-ci.yml`。

## 问题和修复

旧配置使用 `[tool.setuptools] packages=["lumacarve_runtime","lumacarve_server"]`，只声明顶层 Python 包。如果用户正常构建 wheel 再部署，`lumacarve_server/routers/` 子包可能被漏掉，导致运行期模块导入失败。

现在使用 `[tool.setuptools.packages.find]` 自动递归发现 `lumacarve_runtime*` 和 `lumacarve_server*` 子包，路由和后续 adapter 包无需每次手写新路径。

## 原则

- **HTTP API 与纯调度策略的包边界分开**：`lumacarve_server` 持有 FastAPI 和业务逻辑；`lumacarve_runtime` 无需在导入时初始化 GPU。
- `pyproject.toml` 的 `inference`、`training`、`china`、`flash`、`sage` 是依赖组，不是不同虚拟环境。
- 不把大型权重、下载缓存、用户数据、输出等打进 wheel。
- CI 安装 API 依赖、运行测试，并临时生成 wheel 检查路由代码与 runtime 文件齐备。
- 未来每个新增子包应包含 `__init__.py` 并纳入架构清单 `project-layout.toml`，保证代码、Markdown、测试都有对应关系。

测试：`python -m unittest discover -s backend/tests -v`；打包：`python -m pip wheel --no-deps ./backend`。验证包完整性不等于 GPU 模型支持。
