"""SQLAlchemy ORM models for sessions, generations, and feedback."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text

from .database import Base


class SessionORM(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    flow_type = Column(String, nullable=False)  # concept_builder | draft_grid | explorer
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    current_stage = Column(Integer, default=0)
    config = Column(JSON, nullable=True)
    intent_document = Column(JSON, nullable=True)  # accumulated user intent


class GenerationORM(Base):
    __tablename__ = "generations"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    stage = Column(Integer, nullable=False)
    batch_id = Column(String, nullable=True, index=True)
    batch_index = Column(Integer, nullable=True)
    prompt = Column(Text)
    negative_prompt = Column(Text)
    model_family = Column(String)
    checkpoint = Column(String)
    task_type = Column(String)
    parameters = Column(JSON)  # full snapshot of all params
    loras = Column(JSON)
    gpu_id = Column(String)
    prompt_comfy_id = Column(String)  # ComfyUI's prompt_id
    image_path = Column(String)
    thumbnail_path = Column(String)
    seed = Column(Integer)
    width = Column(Integer)
    height = Column(Integer)
    steps = Column(Integer)
    cfg_scale = Column(Float)
    denoise_strength = Column(Float)
    generation_time_ms = Column(Integer)
    status = Column(String, default="queued")  # queued | generating | complete | error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class FeedbackORM(Base):
    __tablename__ = "feedback"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    stage = Column(Integer)
    action = Column(String)
    selected_generation_ids = Column(JSON)
    rejected_generation_ids = Column(JSON)
    feedback_text = Column(Text, nullable=True)
    parameter_adjustments = Column(JSON, nullable=True)
    resulting_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
