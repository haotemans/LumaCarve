"""Deterministic execution planning for typed, dependency-ordered workflow nodes.

React Flow provides editing; this module owns execution order, not the browser.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class WorkflowNode:
    node_id: str
    operation: str
    depends_on: tuple[str, ...] = ()
    components: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    steps: tuple[WorkflowNode, ...]
    # Output lifecycle: the last step index needing each node's output.
    last_output_use: dict[str, int]
    # Outputs with no downstream consumers are returned by the executor.
    output_nodes: frozenset[str]
    # Last use of each model component (advisory, not forced eviction).
    last_component_use: dict[str, int]


class InvalidWorkflow(ValueError):
    """Graph has duplicate IDs, missing dependencies, or a cycle."""


def compile_workflow(nodes: Iterable[WorkflowNode]) -> ExecutionPlan:
    original = tuple(nodes)
    lookup: dict[str, WorkflowNode] = {}
    children: dict[str, list[str]] = {}
    indegree: dict[str, int] = {}
    for node in original:
        if not node.node_id or not node.operation:
            raise InvalidWorkflow("Node ID and operation must not be empty.")
        if node.node_id in lookup:
            raise InvalidWorkflow(f"Duplicate node ID: {node.node_id}")
        lookup[node.node_id] = node
        children[node.node_id] = []
        indegree[node.node_id] = 0

    for node in original:
        for parent in set(node.depends_on):
            if parent not in lookup:
                raise InvalidWorkflow(f"{node.node_id}: missing dependency {parent}")
            children[parent].append(node.node_id)
            indegree[node.node_id] += 1

    queue = deque(node.node_id for node in original if indegree[node.node_id] == 0)
    ordered: list[WorkflowNode] = []
    while queue:
        node_id = queue.popleft()
        ordered.append(lookup[node_id])
        for child in children[node_id]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(ordered) != len(original):
        raise InvalidWorkflow("Workflow contains a dependency cycle.")

    index = {node.node_id: i for i, node in enumerate(ordered)}
    last_output_use = dict(index)
    last_component_use: dict[str, int] = {}
    for i, node in enumerate(ordered):
        for parent in node.depends_on:
            last_output_use[parent] = max(last_output_use[parent], i)
        for component in node.components:
            if not component:
                raise InvalidWorkflow(f"{node.node_id}: empty component key")
            last_component_use[component] = i

    return ExecutionPlan(
        steps=tuple(ordered),
        last_output_use=last_output_use,
        output_nodes=frozenset(node_id for node_id, dependents in children.items() if not dependents),
        last_component_use=last_component_use,
    )
