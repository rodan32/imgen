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


class RejectAllRequest(BaseModel):
    session_id: str
    stage: int
    feedback_text: Optional[str] = None
    rejected_image_ids: List[str]


class RejectAllResponse(BaseModel):
    recorded: bool
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
    from ..main import app
    from pathlib import Path

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

    # Record preferences for selected images
    if req.selected_image_ids:
        preference_learning = app.state.preference_learning
        vision_analysis = app.state.vision_analysis

        # Get selected generations
        result = await db.execute(
            select(GenerationORM)
            .where(GenerationORM.id.in_(req.selected_image_ids))
        )
        selected_gens = result.scalars().all()

        # Record each selection for learning
        for gen in selected_gens:
            # Extract LoRAs from parameters if available
            loras = []
            # TODO: Parse gen.parameters for LoRA info when we start tracking it

            # Record preference
            await preference_learning.record_preference(
                db=db,
                prompt=gen.prompt,
                checkpoint=gen.checkpoint_name or "unknown",
                loras=loras,
                selected=True,
                rejected=False,
                model_family=gen.model_family or "sdxl",
                task_type="standard",  # TODO: get from gen
                stage=session.current_stage - 1,
                session_id=req.session_id,
                generation_id=gen.id,
                negative_prompt=gen.negative_prompt,
            )

        logger.info(
            "Recorded %d selections for preference learning",
            len(selected_gens)
        )

        # EXPERIMENTAL: Vision analysis of selected images (logging only)
        if vision_analysis.enabled:
            image_paths = []
            for gen in selected_gens:
                # Assume images are stored in data/images/
                img_path = Path(gen.image_url.replace("/images/", "data/images/"))
                if img_path.exists():
                    image_paths.append(img_path)

            if image_paths:
                original_prompt = selected_gens[0].prompt if selected_gens else ""
                # Analyze in background to not block response
                import asyncio
                asyncio.create_task(
                    vision_analysis.analyze_selected_images(image_paths, original_prompt)
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


@router.post("/reject-all", response_model=RejectAllResponse)
async def reject_all(
    req: RejectAllRequest,
    db: AsyncSession = Depends(get_session),
):
    """
    Record rejection of all images in a stage.

    This feeds back into checkpoint/LoRA learning to avoid bad combinations.
    Likely causes: too strong LoRA, wrong checkpoint for the prompt.
    """
    from ..main import app

    # Verify session exists
    result = await db.execute(select(SessionORM).where(SessionORM.id == req.session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info(
        "Reject all for session %s stage %d, feedback: %s, images: %d",
        req.session_id, req.stage, req.feedback_text, len(req.rejected_image_ids),
    )

    # Get the rejected generations to extract checkpoint/LoRA info
    if req.rejected_image_ids:
        result = await db.execute(
            select(GenerationORM)
            .where(GenerationORM.id.in_(req.rejected_image_ids))
        )
        rejected_gens = result.scalars().all()

        # Extract checkpoints and LoRAs used
        checkpoints_used = {}
        loras_used = {}
        for gen in rejected_gens:
            checkpoint = gen.checkpoint_name
            if checkpoint:
                checkpoints_used[checkpoint] = checkpoints_used.get(checkpoint, 0) + 1

            # TODO: Extract LoRA names from gen.parameters when we start tracking them
            # For now, this is a placeholder for future LoRA tracking

        logger.info(
            "Rejected checkpoints: %s",
            {k: v for k, v in checkpoints_used.items()},
        )

        # Feed this back into CheckpointLearning to penalize these checkpoints
        checkpoint_learning = app.state.checkpoint_learning
        preference_learning = app.state.preference_learning

        for checkpoint, count in checkpoints_used.items():
            checkpoint_learning.record_rejection(checkpoint, count)

        # Record each rejection for preference learning
        for gen in rejected_gens:
            # Extract LoRAs from parameters if available
            loras = []
            # TODO: Parse gen.parameters for LoRA info

            await preference_learning.record_preference(
                db=db,
                prompt=gen.prompt,
                checkpoint=gen.checkpoint_name or "unknown",
                loras=loras,
                selected=False,
                rejected=True,
                model_family=gen.model_family or "sdxl",
                task_type="standard",
                stage=req.stage,
                session_id=req.session_id,
                generation_id=gen.id,
                feedback_text=req.feedback_text,
                negative_prompt=gen.negative_prompt,
            )

        logger.info(
            "Recorded %d rejections for preference learning",
            len(rejected_gens)
        )

        # EXPERIMENTAL: Vision analysis of rejected images (logging only)
        vision_analysis = app.state.vision_analysis
        if vision_analysis.enabled:
            from pathlib import Path
            import asyncio

            image_paths = []
            for gen in rejected_gens:
                img_path = Path(gen.image_url.replace("/images/", "data/images/"))
                if img_path.exists():
                    image_paths.append(img_path)

            if image_paths:
                original_prompt = rejected_gens[0].prompt if rejected_gens else ""
                # Analyze in background
                asyncio.create_task(
                    vision_analysis.analyze_rejected_images(
                        image_paths,
                        original_prompt,
                        req.feedback_text
                    )
                )

        # Future enhancements:
        # - If feedback mentions "too strong", reduce LoRA strength recommendations
        # - If feedback mentions "wrong style", adjust checkpoint-prompt matching
        # - Track LoRA combinations that get rejected together

    return RejectAllResponse(
        recorded=True,
        rationale=f"Rejection recorded. Penalized {len(checkpoints_used)} checkpoint(s) in learning system.",
    )
