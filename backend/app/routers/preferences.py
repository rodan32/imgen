"""Preference learning routes."""

from __future__ import annotations

import logging
from typing import Dict, Any

from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("/stats", response_model=Dict[str, Any])
async def get_preference_stats(
    request: Request,
    db: AsyncSession = Depends(get_session),
    user_id: str = "default",
):
    """
    Get preference learning statistics.

    Returns summary of user preferences, top checkpoints, etc.
    """
    preference_learning = request.app.state.preference_learning

    stats = await preference_learning.get_stats_summary(db, user_id)
    return stats


@router.get("/export")
async def export_preferences(
    request: Request,
    db: AsyncSession = Depends(get_session),
    user_id: str = "default",
):
    """
    Export all preference data as JSON.

    For backup and portability across systems.
    """
    preference_learning = request.app.state.preference_learning

    export_data = await preference_learning.export_preferences(db, user_id)
    return export_data


@router.get("/recommend/checkpoint")
async def recommend_checkpoint(
    request: Request,
    db: AsyncSession = Depends(get_session),
    prompt: str = "",
    user_id: str = "default",
):
    """
    Get checkpoint recommendation for a prompt.

    Query params:
    - prompt: The prompt to generate for
    - user_id: User ID (default: "default")

    Returns: {checkpoint: str, confidence: float}
    """
    preference_learning = request.app.state.preference_learning
    checkpoint_learning = request.app.state.checkpoint_learning

    # Get available checkpoints (SDXL by default)
    available = list(checkpoint_learning.checkpoint_pools.get("sdxl_standard", []))

    if not available:
        return {"checkpoint": None, "confidence": 0.0}

    checkpoint, confidence = await preference_learning.recommend_checkpoint(
        db, prompt, available, user_id
    )

    return {"checkpoint": checkpoint, "confidence": confidence}


@router.get("/recommend/loras")
async def recommend_loras(
    request: Request,
    db: AsyncSession = Depends(get_session),
    prompt: str = "",
    checkpoint: str = "",
    count: int = 3,
    user_id: str = "default",
):
    """
    Get LoRA recommendations for a prompt + checkpoint.

    Query params:
    - prompt: The prompt to generate for
    - checkpoint: The checkpoint being used
    - count: Number of LoRAs to recommend (default: 3)
    - user_id: User ID (default: "default")

    Returns: [{lora: str, score: float}, ...]
    """
    preference_learning = request.app.state.preference_learning
    lora_discovery = request.app.state.lora_discovery

    # Get available LoRAs
    available = lora_discovery.get_cached_loras(None)

    if not available:
        return []

    recommendations = await preference_learning.recommend_loras(
        db, prompt, available, checkpoint, count, user_id
    )

    return [
        {"lora": lora, "score": score}
        for lora, score in recommendations
    ]
