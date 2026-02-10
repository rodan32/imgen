"""Checkpoint learning and stats routes."""

from __future__ import annotations

import logging
from typing import Dict, Any

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/checkpoints", tags=["checkpoints"])


@router.get("/stats", response_model=Dict[str, Dict[str, Any]])
async def get_checkpoint_stats(request: Request):
    """
    Get checkpoint performance statistics.

    Returns: {checkpoint_name: {selected: int, total: int, selection_rate: float}}
    """
    checkpoint_learning = request.app.state.checkpoint_learning
    return checkpoint_learning.get_stats_summary()


@router.get("/pools", response_model=Dict[str, Any])
async def get_checkpoint_pools(request: Request):
    """
    Get configured checkpoint pools.

    Returns: {pool_name: [checkpoint_names...]}
    """
    checkpoint_learning = request.app.state.checkpoint_learning
    return checkpoint_learning.checkpoint_pools
