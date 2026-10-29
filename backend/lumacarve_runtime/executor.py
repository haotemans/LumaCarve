"""Executor scaffolding: leases models per node and drops dead intermediates."""
from __future__ import annotations

from typing import Any, Callable, Mapping

from .graph import ExecutionPlan, WorkflowNode
from .residency import ModelResidencyManager

NodeFn = Callable[[WorkflowNode, Mapping[str, Any], Mapping[str, Any]], Any]


def run_plan(
    plan: ExecutionPlan, manager: ModelResidencyManager, execute_node: NodeFn,
) -> dict[str, Any]:
    """Execute a compiled workflow with a user-supplied node callback.

    This is not an inference implementation. execute_node must synchronize
    outstanding GPU work before its lease closes and must not retain model
    handles outside the lease. Nodes should not retain unnecessary tensors.
    """
    results: dict[str, Any] = {}
    for index, node in enumerate(plan.steps):
        inputs = {key: results[key] for key in node.depends_on}
        with manager.lease(node.components) as handles:
            value = execute_node(node, handles, inputs)
        results[node.node_id] = value
        # Intermediate outputs no longer needed by downstream nodes can be
        # released promptly; sink outputs remain for the caller.
        for key in tuple(results):
            if key not in plan.output_nodes and plan.last_output_use[key] <= index:
                del results[key]
    return results
