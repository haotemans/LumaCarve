# graph.rs · Deterministic DAG 编译

`compile(&[NodeSpec]) -> Result<ExecutionPlan,SchedulerError>` 验证唯一 ID、依赖存在、无环、组件标识有效，采用稳定 Kahn 拓扑排序。对无依赖节点保持输入顺序；记录 `last_output_use`、`last_component_use` 和输出端节点。

**重要：** Graph 目前的 JSON v1 以节点和边表达依赖，尚无明确类型化输入/输出端口。Rust 这个模型采用归一化 `NodeSpec {node_id,operation,depends_on,components}`；Python 在入 Rust 前仍需做节点类型/参数验证，不能单靠 Rust 完成模型兼容检查。

测试：`scheduler/tests/core.rs` 的 DAG 顺序和无环/缺失依赖错误。与 `backend/lumacarve_runtime/graph.py` 的行为对齐后再切换正式 Graph 计划编译器。
