"""LumaCarve low-overhead execution-planning and model-residency foundation."""
from .attention import AttentionSelection, check_packages, select_attention
from .budget import BudgetEstimate, ComponentSpec, MemoryBudget, preflight
from .executor import run_plan
from .graph import ExecutionPlan, InvalidWorkflow, WorkflowNode, compile_workflow
from .rust_bridge import compile_preferred, scheduler_backend
from .residency import (
    InsufficientMemory,
    BaseModelBusy, ReleaseNotVerified,
    ModelBackend,
    ModelResidencyManager,
    ResidencySnapshot,
    Tier,
)

__all__ = [
    "AttentionSelection", "check_packages", "select_attention",
    "compile_preferred", "scheduler_backend",
    "BudgetEstimate", "ComponentSpec", "MemoryBudget", "preflight",
    "run_plan", "ExecutionPlan", "InvalidWorkflow", "WorkflowNode",
    "compile_workflow", "InsufficientMemory", "BaseModelBusy", "ReleaseNotVerified", "ModelBackend",
    "ModelResidencyManager", "ResidencySnapshot", "Tier",
]
