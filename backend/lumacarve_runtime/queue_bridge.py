"""Pick one SQLite-backed job using Rust's stateless priority policy.

Rust is a decision helper, never a second durable queue. Python owns SQLite
transactions and all model execution. No Torch/CUDA is imported here.
"""
from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from .rust_bridge import _extension

PRIORITIES = ("interactive", "normal", "background")


def require_compatible_queue_backend() -> str:
    """Reject outdated Rust wheels before recovering or starting GPU tasks."""
    engine = _extension()
    if engine is None:
        return "python-fallback"
    if not callable(getattr(engine, "choose_queued_job", None)):
        raise RuntimeError(
            "Outdated lumacarve_scheduler extension. Reinstall Rust scheduler "
            "with tools/setup.py --scheduler required."
        )
    return "rust"


def _python_choice(pending: Sequence[dict[str, Any]], streak: int) -> tuple[str, int] | None:
    if not pending:
        return None
    force_other = streak >= 3 and any(x["priority"] != "interactive" for x in pending)
    candidates = [x for x in pending if x["priority"] != "interactive"] if force_other else pending
    if force_other:
        chosen = min(candidates, key=lambda x: (x["sequence"], x["id"]))
    else:
        rank = {priority: index for index, priority in enumerate(PRIORITIES)}
        chosen = min(candidates, key=lambda x: (rank[x["priority"]], x["sequence"], x["id"]))
    return chosen["id"], (min(streak + 1, 3) if chosen["priority"] == "interactive" else 0)


def choose_pending_job(pending: Sequence[dict[str, Any]], streak: int) -> tuple[str, int] | None:
    """Choose without side effects. Store.claim_next() alone changes job state.

    Fail closed if the Rust extension exists but gives an invalid decision.
    """
    if not isinstance(streak, int) or isinstance(streak, bool) or streak < 0:
        raise ValueError("Invalid interactive job streak")
    seen: set[str] = set()
    for row in pending:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("id"), str)
            or not row["id"].strip()
            or row["id"] in seen
            or row.get("priority") not in PRIORITIES
            or type(row.get("sequence")) is not int
            or row["sequence"] < 0
        ):
            raise ValueError("Invalid durable job snapshot")
        seen.add(row["id"])
    engine = _extension()
    if engine is None:
        return _python_choice(pending, streak)

    if not callable(getattr(engine, "choose_queued_job", None)):
        raise RuntimeError("Rust queue selector missing; rebuild scheduler extension")
    result = engine.choose_queued_job(json.dumps(pending, separators=(",", ":")), streak)
    if not pending:
        if result is not None:
            raise ValueError("Rust scheduler returned a job from an empty queue")
        return None
    if (
        not isinstance(result, (list, tuple))
        or len(result) != 2
        or not isinstance(result[0], str)
        or result[0] not in seen
        or type(result[1]) is not int
        or not 0 <= result[1] <= 3
    ):
        raise ValueError("Rust scheduler returned an invalid queued-job decision")
    # This reference decision makes Python/Rust policy drift a visible failure,
    # not silent priority inversion in production.
    if tuple(result) != _python_choice(pending, streak):
        raise ValueError("Rust and Python durable queue policies disagree")
    return result[0], result[1]
