# 07 · Graph 执行计划与模型驻留策略（lumacarve_runtime）

对应代码：`lumacarve_runtime/graph.py`、`budget.py`、`residency.py`、`executor.py`；测试：`tests/test_runtime.py`。

先前已实现独立于 PyTorch 的调度层：

- `compile_workflow`：依赖验证、拓扑排序、每个结果最后使用位置。
- `preflight`：预估同时需要的模型权重字节数；**不等价于 CUDA 峰值显存**，需为激活和传输保留空间。
- `ModelResidencyManager`：GPU HOT、RAM WARM、磁盘 COLD 三级；已有 GPU 模型按需复用，LRU 压力淘汰；任务持有 lease 时禁止卸载。
- `run_plan`：按顺序执行节点，释放不再使用的中间输出；调用者需提供真实节点执行函数。

与 `lumacarve_server/jobs.py` 的关系：后续真实模型适配器实现 `ModelBackend` 协议，并通过 JobQueue 串行调度 GPU 任务；当前 JobQueue 仍是 DisabledInference，尚未把任何 GPU 模型接入上述驻留层。

**性能优先级**：先原生驻留、复用组件与 Text Encoder 缓存，再在压力下整组件卸载；逐层卸载、异步预取或 CUDA 图编译都应基于硬件实测启用，而不是为了降低静态显存读数牺牲性能。
