# check_layout.py · 源码与文档检查

对应代码：`../check_layout.py`，测试：`../tests/test_check_layout.py`，项目清单：`../../project-layout.toml`。

## 为什么需要它

用户要求**每份代码、对应 Markdown、测试和独立提交记录**。为避免以后新增模型适配器但忘记配文档，`project-layout.toml` 为代码模块指定唯一归属、文档和测试验证方式。

新增模块需要同步添加 `[[module]]`，填写 `id`、`source`（一个领域模块可含多个路由/服务文件）、`doc`、`tests`（Python 模块必须包含）、`verification`。脚本验证文件存在、不能重复归属、不能使用 `../` 越界、后端主要源码和 Image Studio 功能源码必须登记、隐私文件夹被 Git 忽略。

## 执行

在项目根目录：

```powershell
py -3.11 tools/check_layout.py
```

测试：

```powershell
py -3.11 -m unittest discover -s tools/tests -v
```

无 pip 依赖、无网络、无 GPU。由 `.github/workflows/layout-ci.yml` 作为独立工作流在 GitHub Actions 中运行。**通过结构检查≠真实 GPU 功能或性能测试通过。**

## 本次暂未检查的范围

旧的演示页面 `frontend/src/pages` 尚未逐个拆出。迁移时将相应路径纳入强制登记范围。工作流 JSON 的前后端字段一致性仍需契约测试和 API 集成验证。
