"""Session management routes."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import get_session
from ..models.orm import GenerationORM, SessionORM
from ..models.schemas import (
    CreateSessionRequest,
    GenerationResultResponse,
    SessionResponse,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse)
async def create_session(
    req: CreateSessionRequest,
    db: AsyncSession = Depends(get_session),
):
    """Create a new generation session."""
    session = SessionORM(
        id=str(uuid.uuid4()),
        flow_type=req.flow_type.value,
        created_at=datetime.now(timezone.utc),
        current_stage=0,
        config=req.initial_config,
        intent_document={"preferences": [], "rejections": [], "pinned_traits": []},
    )
    db.add(session)
    await db.commit()

    return SessionResponse(
        id=session.id,
        flow_type=req.flow_type,
        created_at=session.created_at,
        current_stage=session.current_stage,
        config=session.config,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session_info(
    session_id: str,
    db: AsyncSession = Depends(get_session),
):
    """Get session details."""
    result = await db.execute(select(SessionORM).where(SessionORM.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        id=session.id,
        flow_type=session.flow_type,
        created_at=session.created_at,
        current_stage=session.current_stage,
        config=session.config,
    )


@router.get("/{session_id}/generations", response_model=list[GenerationResultResponse])
async def get_session_generations(
    session_id: str,
    stage: int | None = None,
    db: AsyncSession = Depends(get_session),
):
    """Get all generations for a session, optionally filtered by stage."""
    query = select(GenerationORM).where(GenerationORM.session_id == session_id)
    if stage is not None:
        query = query.where(GenerationORM.stage == stage)
    query = query.order_by(GenerationORM.created_at)

    result = await db.execute(query)
    generations = result.scalars().all()

    return [
        GenerationResultResponse(
            id=g.id,
            session_id=g.session_id,
            stage=g.stage,
            prompt=g.prompt or "",
            negative_prompt=g.negative_prompt or "",
            image_url=f"/api/generate/{g.id}/image",
            thumbnail_url=f"/api/generate/{g.id}/thumbnail",
            gpu_id=g.gpu_id,
            generation_time_ms=g.generation_time_ms,
            parameters=g.parameters,
            seed=g.seed,
            created_at=g.created_at,
        )
        for g in generations
        if g.status == "complete"
    ]


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Delete a session and its images."""
    result = await db.execute(select(SessionORM).where(SessionORM.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete images from filesystem
    image_store = request.app.state.image_store
    await image_store.delete_session(session_id)

    # Delete DB records
    await db.execute(
        GenerationORM.__table__.delete().where(GenerationORM.session_id == session_id)
    )
    await db.delete(session)
    await db.commit()

    return {"status": "deleted", "session_id": session_id}
