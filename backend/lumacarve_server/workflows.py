"""Strict compiler for frontend lumacarve.studio.workflow.v1 JSON."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumacarve_runtime import WorkflowNode, compile_workflow
from lumacarve_runtime.graph import InvalidWorkflow

FORMAT = "lumacarve.studio.workflow.v1"
ALLOWED = {
    "model": {"lora", "sampler"},
    "lora": {"lora", "sampler"},
    "prompt": {"sampler"},
    "references": {"sampler"},
    "mask": {"sampler"},
    "sampler": {"vae"},
    "vae": {"output"},
    "output": set(),
}
FIELDS = {
    "model": {"modelId"},
    "lora": {"loras"},
    "prompt": {"prompt", "negativePrompt"},
    "references": {"images"},
    "mask": {"mask"},
    "sampler": {"steps", "seed", "aspect", "guidance"},
    "vae": set(),
    "output": {"transparent"},
}
INTENTS = {"create", "reference", "inpaint"}
ASPECTS = {"1:1", "4:3", "3:4", "16:9", "9:16", "2:3", "3:2"}


class WorkflowValidationError(ValueError):
    pass


@dataclass(frozen=True)
class WorkflowSummary:
    intent: str
    model_id: str
    node_order: tuple[str, ...]
    exposed_fields: tuple[str, ...]
    loras: tuple[tuple[str, float], ...]
    references_required: bool
    mask_required: bool


def _fail(message: str):
    raise WorkflowValidationError(message)


def validate_workflow(data: dict[str, Any]) -> WorkflowSummary:
    if not isinstance(data, dict) or data.get("format") != FORMAT or data.get("intent") not in INTENTS:
        _fail("Unsupported workflow format or intent")
    nodes, edges = data.get("nodes"), data.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list) or not 1 <= len(nodes) <= 200 or len(edges) > 500:
        _fail("Invalid node/edge count")
    by_id: dict[str, dict[str, Any]] = {}
    all_exposed: list[str] = []
    model_ids: list[str] = []
    loras: list[tuple[str, float]] = []
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or len(node["id"]) > 128:
            _fail("Invalid node ID")
        kind = node.get("kind")
        if kind not in ALLOWED or node["id"] in by_id:
            _fail("Unsupported or duplicate node kind/ID")
        params = node.get("params", {})
        exposed = node.get("exposed", [])
        if not isinstance(params, dict) or not isinstance(exposed, list) or len(exposed) > 30:
            _fail("Invalid parameters or exposure")
        if any(key not in FIELDS[kind] for key in params) or any(key not in FIELDS[kind] for key in exposed):
            _fail(f"{kind}: unexpected parameter/exposure field")
        if kind == "model":
            model = params.get("modelId")
            if not isinstance(model, str) or not model or len(model) > 120:
                _fail("Invalid model ID")
            model_ids.append(model)
        if kind == "prompt":
            for field in ("prompt", "negativePrompt"):
                val = params.get(field, "")
                if not isinstance(val, str) or len(val) > 20_000:
                    _fail("Prompt must be text of length <= 20000")
        if kind == "lora":
            entries = params.get("loras", [])
            if not isinstance(entries, list) or len(entries) > 1000:
                _fail("Invalid LoRA list")
            for entry in entries:
                if not isinstance(entry, dict):
                    _fail("Invalid LoRA entry")
                name, weight, enabled = entry.get("name"), entry.get("strength"), entry.get("enabled")
                if not isinstance(name, str) or len(name) > 255 or not isinstance(weight, (int, float)) or isinstance(weight, bool) or not -2 <= weight <= 2 or not isinstance(enabled, bool):
                    _fail("Invalid LoRA entry values")
                if enabled:
                    if not name.strip():
                        _fail("Enabled LoRA requires a model name")
                    loras.append((name, float(weight)))
        if kind == "sampler":
            steps, seed, aspect, guidance = (params.get("steps", 28), params.get("seed", 0), params.get("aspect", "1:1"), params.get("guidance", 4))
            if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 150:
                _fail("Steps outside 1-150")
            if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32-1:
                _fail("Invalid seed")
            if aspect not in ASPECTS or isinstance(guidance, bool) or not isinstance(guidance, (int, float)) or not 0 <= guidance <= 20:
                _fail("Invalid aspect/guidance")
        if kind == "output" and not isinstance(params.get("transparent", False), bool):
            _fail("Invalid transparency flag")
        all_exposed.extend(f"{node['id']}.{field}" for field in exposed)
        by_id[node["id"]] = node

    parents: dict[str, list[str]] = {id: [] for id in by_id}
    children: dict[str, list[str]] = {id: [] for id in by_id}
    seen: set[tuple[str, str]] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            _fail("Invalid edge")
        source, target = edge.get("source"), edge.get("target")
        if source not in by_id or target not in by_id or source == target or (source, target) in seen:
            _fail("Missing, duplicate or self-looping edge")
        if by_id[target]["kind"] not in ALLOWED[by_id[source]["kind"]]:
            _fail("Incompatible node connection")
        parents[target].append(source)
        children[source].append(target)
        seen.add((source, target))
    if len(model_ids) != 1:
        _fail("Exactly one model node is required")
    outputs = [id for id, n in by_id.items() if n["kind"] == "output"]
    if len(outputs) != 1:
        _fail("Exactly one output node is required")
    if not any(by_id[n]["kind"] == "sampler" for n in by_id):
        _fail("Sampler node is required")
    if any(not children[id] and id not in outputs for id in children):
        _fail("Disconnected sink node; remove it or connect it to output")
    visited: set[str] = set()
    pending = [outputs[0]]
    while pending:
        node_id = pending.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        pending.extend(parents[node_id])
    if len(visited) != len(by_id):
        _fail("All nodes must contribute to output")
    kinds = {n["kind"] for n in nodes}
    intent = data["intent"]
    if intent != "create" and "references" not in kinds:
        _fail("Image editing requires a reference node")
    if intent == "inpaint" and "mask" not in kinds:
        _fail("Inpainting requires a mask node")
    if intent == "create" and ("references" in kinds or "mask" in kinds):
        _fail("Creation intent cannot include image-edit nodes")
    if intent == "reference" and "mask" in kinds:
        _fail("Mask node requires inpaint intent")
    if "prompt" not in kinds:
        _fail("Text condition is required")
    try:
        plan = compile_workflow(
            WorkflowNode(node_id=id, operation=by_id[id]["kind"], depends_on=tuple(parents[id]))
            for id in by_id
        )
    except InvalidWorkflow as exc:
        _fail(str(exc))
    return WorkflowSummary(
        intent=intent, model_id=model_ids[0], node_order=tuple(n.node_id for n in plan.steps),
        exposed_fields=tuple(all_exposed), loras=tuple(loras),
        references_required=intent != "create", mask_required=intent == "inpaint",
    )
