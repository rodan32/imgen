"""LoRA management routes."""

from __future__ import annotations

import logging
from typing import List, Dict

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/loras", tags=["loras"])


@router.get("", response_model=Dict[str, List[str]])
async def get_loras(request: Request):
    """
    Get available LoRAs from cache.

    Returns: {gpu_id: [lora_names...]} or {"all": [union of all loras]}
    """
    lora_discovery = request.app.state.lora_discovery

    # Return per-GPU cache
    result = {}
    for gpu_id in lora_discovery.lora_cache.keys():
        result[gpu_id] = lora_discovery.get_cached_loras(gpu_id)

    # Also include union of all
    result["all"] = lora_discovery.get_cached_loras(None)

    return result


@router.get("/search")
async def search_loras(
    prompt: str,
    max_results: int = 5,
    request: Request = None
):
    """
    Search for LoRAs relevant to a prompt.

    Returns list of {name, relevance, matched_keywords}
    """
    lora_discovery = request.app.state.lora_discovery

    available_loras = lora_discovery.get_cached_loras(None)
    if not available_loras:
        return []

    matches = lora_discovery.match_loras_to_prompt(prompt, available_loras, max_results)
    return matches


@router.post("/refresh")
async def refresh_loras(request: Request):
    """
    Force an immediate refresh of LoRA cache.

    Returns: Number of LoRAs cached
    """
    lora_discovery = request.app.state.lora_discovery

    await lora_discovery._poll_all_gpus()

    total = len(lora_discovery.get_cached_loras(None))
    return {"status": "refreshed", "total_loras": total}
