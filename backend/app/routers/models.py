"""Model sync and cache management routes."""

from __future__ import annotations

import logging
from typing import Dict, Any, List

from fastapi import APIRouter, Request, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/sync-status", response_model=Dict[str, Any])
async def get_sync_status(request: Request):
    """
    Get model sync status across all nodes.

    Returns:
    - NAS model counts
    - Per-node cache status
    - Hot models (frequently used)
    """
    model_sync = request.app.state.model_sync
    return model_sync.get_sync_status()


@router.get("/recommend-cache", response_model=Dict[str, List[str]])
async def recommend_cache(
    request: Request,
    node_id: str = Query(..., description="GPU node ID (e.g., gpu-premium)"),
    max_items: int = Query(10, description="Max items to recommend per type"),
):
    """
    Get cache recommendations for a specific node.

    Based on:
    - Node constraints (SD1.5 only for 3050Ti)
    - Usage frequency
    - Cache capacity

    Returns: {
        "checkpoints": [names...],
        "loras": [names...]
    }
    """
    model_sync = request.app.state.model_sync
    return model_sync.recommend_cache_for_node(node_id, max_items)


@router.get("/hot-models", response_model=Dict[str, List[str]])
async def get_hot_models(
    request: Request,
    days: int = Query(7, description="Number of days to look back"),
    min_uses: int = Query(3, description="Minimum uses to be considered hot"),
):
    """
    Get frequently used models (cache candidates).

    Returns: {
        "checkpoints": [names...],
        "loras": [names...]
    }
    """
    model_sync = request.app.state.model_sync
    return model_sync.get_hot_models(days, min_uses)


@router.get("/nas-models", response_model=Dict[str, List[str]])
async def get_nas_models(request: Request):
    """
    Get all models available on NAS.

    Returns: {
        "checkpoints": [names...],
        "loras": [names...]
    }
    """
    model_sync = request.app.state.model_sync
    return {
        "checkpoints": list(model_sync.nas_checkpoints.keys()),
        "loras": list(model_sync.nas_loras.keys()),
    }


@router.get("/node-cache/{node_id}", response_model=Dict[str, Any])
async def get_node_cache(request: Request, node_id: str):
    """
    Get cache status for a specific node.

    Returns: {
        "cached_checkpoints": [names...],
        "cached_loras": [names...],
        "cache_used_mb": float,
        "cache_capacity_mb": float,
        "last_sync": datetime
    }
    """
    model_sync = request.app.state.model_sync
    cache = model_sync.node_caches.get(node_id)

    if not cache:
        return {"error": f"Node {node_id} not registered"}

    return {
        "node_id": cache.node_id,
        "cached_checkpoints": list(cache.cached_checkpoints),
        "cached_loras": list(cache.cached_loras),
        "cache_used_mb": cache.cache_used_mb,
        "cache_capacity_mb": cache.cache_capacity_mb,
        "last_sync": cache.last_sync.isoformat() if cache.last_sync else None,
    }


@router.post("/record-usage")
async def record_model_usage(
    request: Request,
    model_name: str = Query(..., description="Model name that was used"),
):
    """
    Record that a model was used (for cache prioritization).

    Called automatically by generation endpoint.
    """
    model_sync = request.app.state.model_sync
    model_sync.record_model_usage(model_name)

    return {"recorded": True, "model": model_name}
