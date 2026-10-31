"""Optional Rust graph planner in the SAME Python environment.

Only graph metadata passes the PyO3 boundary. Never ship CUDA tensor data or
model weights through the JSON adapter.
"""
from __future__ import annotations

import importlib
import json
from dataclasses import asdict
from typing import Iterable, Any

from .graph import ExecutionPlan, InvalidWorkflow, WorkflowNode, compile_workflow


def _extension() -> Any | None:
    try:
        return importlib.import_module("lumacarve_scheduler")
    except ModuleNotFoundError as exc:
        # Only an entirely absent optional package is a normal fallback.
        # Never conceal broken transitive imports or ABI mismatches.
        if exc.name == "lumacarve_scheduler":
            return None
        raise


def scheduler_backend() -> str:
    return "rust" if _extension() is not None else "python-fallback"


def compile_preferred(nodes: Iterable[WorkflowNode]) -> ExecutionPlan:
    original = tuple(nodes)
    extension = _extension()
    if extension is None:
        return compile_workflow(original)

    serialized = json.dumps([asdict(node) for node in original], ensure_ascii=False)
    try:
        payload = json.loads(extension.compile_graph_json(serialized))
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise InvalidWorkflow(f"Rust scheduler rejected graph: {exc}") from exc
    if not isinstance(payload, dict):
        raise InvalidWorkflow("Rust scheduler returned invalid plan")
    order = payload.get("order")
    by_id = {node.node_id: node for node in original}
    if not isinstance(order, list) or len(order) != len(original) or len(by_id) != len(original):
        raise InvalidWorkflow("Rust scheduler returned invalid node order")
    if any(not isinstance(id_, str) for id_ in order) or set(order) != set(by_id):
        raise InvalidWorkflow("Rust scheduler returned unknown or duplicate node IDs")

    last_output_use = payload.get("last_output_use")
    last_component_use = payload.get("last_component_use")
    output_nodes = payload.get("output_nodes")
    expected_components = {key for node in original for key in node.components}
    for label, values, keys in (
        ("outputs", last_output_use, set(by_id)),
        ("components", last_component_use, expected_components),
    ):
        if not isinstance(values, dict) or set(values) != keys:
            raise InvalidWorkflow(f"Rust scheduler returned incorrect {label} keys")
        if any(type(position) is not int or not 0 <= position < len(order)
               for position in values.values()):
            raise InvalidWorkflow(f"Rust scheduler returned invalid {label} positions")
    expected_sinks = {
        id_ for id_ in by_id if not any(
            id_ in node.depends_on for node in original
        )
    }
    if not isinstance(output_nodes, list) or len(output_nodes) != len(expected_sinks):
        raise InvalidWorkflow("Rust scheduler returned invalid outputs")
    if set(output_nodes) != expected_sinks:
        raise InvalidWorkflow("Rust scheduler returned incorrect terminal nodes")

    return ExecutionPlan(
        steps=tuple(by_id[id_] for id_ in order),
        last_output_use=last_output_use,
        output_nodes=frozenset(output_nodes),
        last_component_use=last_component_use,
    )
