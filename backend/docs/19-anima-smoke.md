# 19 · Anima 本地 GPU 烟雾测试（tools/anima_smoke.py）

代码：`../../tools/anima_smoke.py`；无 GPU 测试：`../tests/test_anima_smoke.py`。

在用户机器已经安装 Rust/PyTorch/Diffusers 并下载 Anima **完整 Diffusers ModularPipeline** 权重后，可不启动 WebUI，直接进行真实 Anima 生成。

```powershell
# 仓库根目录，使用唯一 .venv
.\.venv\Scripts\python.exe tools/anima_smoke.py `
    --prompt "masterpiece, best quality, 1girl, solo, city lights" `
    --steps 30 --seed 2026 --aspect 1:1 --guidance 4 --offload auto
```

也可增加 `--model-path "D:\AI\Anima-Base-v1.0-Diffusers"` 指向已经存在的完整本地 Diffusers 模型目录，无需从 GitHub/ModelScope 重新下载。

脚本先验证 Graph 格式、所需权重文件以及依赖，然后使用**真正的 PyTorch + CUDA** 执行模型，生成 PNG 并输出绝对路径、随机种子、分辨率和采样步数。没有 GPU/权重时会报错，**绝不返回虚构样张**。

注意目前未在实际 8GB/16GB/24GB GPU 上测过性能；`--offload auto` 使用 Diffusers `ComponentsManager` 动态 CPU 卸载。初次测试建议使用 1:1、30 步；显存不足可优先试低分辨率、关闭其他 GPU 应用，勿将未经验证的 CUDA 精度/注意力库自动打开。

如果调用失败，请保留 Python 异常、GPU 名称、驱动版本、`pip show diffusers torch` 输出、可用显存，并对照 [17-anima-adapter.md](17-anima-adapter.md) 排查。
