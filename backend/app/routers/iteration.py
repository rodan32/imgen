"""Iteration routes - feedback and prompt refinement (minimal stub)."""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import get_session
from ..models.orm import GenerationORM, SessionORM

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/iterate", tags=["iteration"])


class FeedbackRequest(BaseModel):
    session_id: str
    selected_image_ids: Optional[List[str]] = None
    rejected_image_ids: Optional[List[str]] = None
    action: str
    feedback_text: Optional[str] = None
    parameter_adjustments: Optional[Dict[str, Any]] = None


class FeedbackResponse(BaseModel):
    suggested_prompt: str
    suggested_negative: str
    suggested_parameters: Dict[str, Any]
    task_type: str
    model_family: str
    use_img2img: bool
    source_image_id: Optional[str]
    denoise_strength: float
    count: int
    rationale: str


class RefinePromptRequest(BaseModel):
    session_id: str
    current_prompt: str
    feedback_text: str
    reference_image_ids: Optional[List[str]] = None


class RefinePromptResponse(BaseModel):
    refined_prompt: str
    rationale: str


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    req: FeedbackRequest,
    db: AsyncSession = Depends(get_session),
):
    """
    Submit user feedback on generated images.

    Minimal stub: returns the same prompt and basic parameters.
    TODO: Integrate LLM prompt refinement pipeline.
    """
    # Verify session exists and increment stage
    result = await db.execute(select(SessionORM).where(SessionORM.id == req.session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Increment current_stage for next iteration
    session.current_stage += 1
    await db.commit()

    logger.info(
        "Feedback submitted for session %s, action=%s, selected=%d, stage now %d",
        req.session_id, req.action,
        len(req.selected_image_ids or []),
        session.current_stage,
    )

    # Get the original prompt from the most recent generation in the previous stage
    # This is a temporary solution until we implement LLM prompt refinement
    result = await db.execute(
        select(GenerationORM)
        .where(
            GenerationORM.session_id == req.session_id,
            GenerationORM.stage == session.current_stage - 1
        )
        .order_by(GenerationORM.created_at.desc())
        .limit(1)
    )
    last_gen = result.scalar_one_or_none()
    original_prompt = last_gen.prompt if last_gen else ""
    original_negative = last_gen.negative_prompt if last_gen else ""

    # Stub response - echo back the original prompt
    # TODO: implement LLM prompt refinement based on selected images
    return FeedbackResponse(
        suggested_prompt=original_prompt,
        suggested_negative=original_negative,
        suggested_parameters={},
        task_type="standard",
        model_family="sdxl",
        use_img2img=False,
        source_image_id=None,
        denoise_strength=0.75,
        count=8,
        rationale="User selected images, advancing to next stage with same prompt",
    )


@router.post("/refine-prompt", response_model=RefinePromptResponse)
async def refine_prompt(
    req: RefinePromptRequest,
    db: AsyncSession = Depends(get_session),
):
    """
    Refine a prompt based on user feedback text.

    Minimal stub: returns the same prompt.
    TODO: Integrate LLM prompt refinement.
    """
    # Verify session exists
    result = await db.execute(select(SessionORM).where(SessionORM.id == req.session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info(
        "Refine prompt for session %s: %s",
        req.session_id, req.feedback_text,
    )

    # Stub response
    return RefinePromptResponse(
        refined_prompt=req.current_prompt,
        rationale="Prompt refinement not yet implemented",
    )
