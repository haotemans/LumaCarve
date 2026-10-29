# 11 · 国内下载源策略 / Download Source Policy

对应代码：`lumacarve_server/download_sources.py`、`tools/setup.py` 和 `config.py`；测试：`tests/test_installer.py`。

## 分源原则

| 类型 | 中国大陆 `--region cn` | 国际 `--region global` |
|---|---|---|
| Python 常规依赖 | 清华 TUNA PyPI 镜像 `https://pypi.tuna.tsinghua.edu.cn/simple` | PyPI 官方 |
| PyTorch CUDA/CPU wheel | CERNET 教育网镜像 `https://mirrors.cernet.edu.cn/pytorch/whl/<tag>` | 官方 `https://download.pytorch.org/whl/<tag>` |
| 模型权重 | ModelScope Hub SDK | Hugging Face Hub（下一模块） |
| 虚拟环境 | 根目录 `.venv` | 同一根目录 `.venv` |

魔搭不能代替 PyPI。PyTorch 的 wheel 存储按 CUDA 版本分区；**不能仅设置普通 PyPI 镜像后就假设安装了 CUDA 版 PyTorch**。

## 使用示例

```powershell
# 在项目根目录
py -3.11 tools/setup.py --region cn --torch cu128 --attention auto

# 如果教育网 CUDA wheel 镜像缺少某个版本，仅切换 PyTorch 官方源
py -3.11 tools/setup.py --region cn --torch cu128 --torch-source official
```

`--region auto` 根据明确配置 `LUMACARVE_DOWNLOAD_REGION` 或系统语言决定，不获取位置、不探测 IP。若识别不准确，用户总可以指定 `--region cn/global`。安装器为单次命令传入 pip 的 `--index-url`，**不会更改系统级 pip 配置**。

`--profile full` 在 cn 模式自动装 `modelscope-hub` 的轻量客户端下载组件；`--profile api` 也可安装此依赖用于模型管理。API 通过 `LUMACARVE_DOWNLOAD_REGION=cn` 选择默认模型源。

警告：镜像站可能滞后或缺失 CUDA wheel。如果指定 CUDA wheel 却安装到了 CPU torch，安装器报错，不悄悄切换计算平台。最终以驱动、wheel 兼容性和目标 GPU 真实检测为准。

参考：清华软件镜像站 PyPI 帮助、MirrorZ PyTorch 镜像帮助、PyTorch 官方安装文档。
