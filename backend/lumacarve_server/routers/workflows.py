"""Validate a serialized image-studio graph without loading any model."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..workflows import WorkflowValidationError, validate_workflow

router = APIRouter(prefix="/api/v1/workflows", tags=["workflows"])


class WorkflowRequest(BaseModel):
    workflow: dict = Field(..., description="lumacarve.studio.workflow.v1 document")


@router.post("/validate")
def validate(payload: WorkflowRequest):
    try:
        result = validate_workflow(payload.workflow)
    except WorkflowValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "valid": True,
        "intent": result.intent,
        "model_id": result.model_id,
        "node_order": result.node_order,
        "exposed_fields": result.exposed_fields,
        "loras": [{"name": name, "strength": strength} for name, strength in result.loras],
        "references_required": result.references_required,
        "mask_required": result.mask_required,
    }
