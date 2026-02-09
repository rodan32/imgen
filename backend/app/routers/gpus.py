"""GPU status routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..models.schemas import GPUStatusResponse

router = APIRouter(prefix="/api/gpus", tags=["gpus"])


@router.get("", response_model=list[GPUStatusResponse])
async def get_gpu_status(request: Request):
    """Get status of all registered GPU nodes."""
    registry = request.app.state.gpu_registry
    return [
        GPUStatusResponse(
            id=node.id,
            name=node.name,
            tier=node.tier.value,
            vram_gb=node.vram_gb,
            healthy=node.healthy,
            current_queue_length=node.current_queue_length,
            capabilities=sorted(node.capabilities),
            last_response_ms=node.last_response_ms,
        )
        for node in registry.get_all_nodes()
    ]


@router.get("/{gpu_id}", response_model=GPUStatusResponse)
async def get_gpu_detail(gpu_id: str, request: Request):
    """Get detailed status of a specific GPU node."""
    registry = request.app.state.gpu_registry
    node = registry.get_node(gpu_id)
    if not node:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"GPU '{gpu_id}' not found")

    return GPUStatusResponse(
        id=node.id,
        name=node.name,
        tier=node.tier.value,
        vram_gb=node.vram_gb,
        healthy=node.healthy,
        current_queue_length=node.current_queue_length,
        capabilities=sorted(node.capabilities),
        last_response_ms=node.last_response_ms,
    )
