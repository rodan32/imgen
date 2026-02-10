"""
Preference learning database models.

Tracks user selections/rejections with full context for learning.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class UserPreferenceORM(Base):
    """
    Individual preference records - every selection/rejection.

    Stores full context: prompt, checkpoint, LoRAs, outcome.
    Used to build aggregated statistics and learn user preferences.
    """
    __tablename__ = "user_preferences"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # User context (for multi-user future)
    user_id: Mapped[str] = mapped_column(String(36), default="default", nullable=False)

    # Input context
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array
    negative_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Generation settings
    checkpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    loras: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array of {name, strength}
    model_family: Mapped[str] = mapped_column(String(50), nullable=False)  # "sd15" or "sdxl"
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "draft", "standard", "quality"

    # User feedback
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # "selected", "rejected", "reject_all"
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stage: Mapped[int] = mapped_column(Integer, nullable=False)

    # Metadata
    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    generation_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # Optional: Vision analysis (if enabled)
    vision_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vision_themes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array

    # Indexes for fast queries
    __table_args__ = (
        Index("idx_user_timestamp", "user_id", "timestamp"),
        Index("idx_checkpoint", "checkpoint"),
        Index("idx_keywords", "keywords"),  # PostgreSQL would want GIN index for JSONB
        Index("idx_action", "action"),
        Index("idx_session", "session_id"),
    )


class PreferenceStatsORM(Base):
    """
    Aggregated statistics for fast lookups.

    Pre-computed selection rates for different combination types:
    - keyword + checkpoint
    - keyword + LoRA
    - checkpoint + LoRA
    """
    __tablename__ = "preference_stats"

    # Composite key
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # User context
    user_id: Mapped[str] = mapped_column(String(36), default="default", nullable=False)

    # Stat type and key
    stat_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "keyword_checkpoint", "keyword_lora", "checkpoint_lora"
    key: Mapped[str] = mapped_column(String(512), nullable=False)  # e.g., "beach:epicrealismXL"

    # Statistics
    selected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    selection_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # Based on sample size

    # Metadata
    last_updated: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Indexes
    __table_args__ = (
        Index("idx_user_stat_key", "user_id", "stat_type", "key", unique=True),
        Index("idx_stat_type", "stat_type"),
    )


class ImageCleanupORM(Base):
    """
    Track images for cleanup - rejected images can be deleted after vision analysis.
    """
    __tablename__ = "image_cleanup"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    generation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    image_path: Mapped[str] = mapped_column(String(512), nullable=False)

    # Status
    rejected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vision_analyzed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ready_for_cleanup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Index
    __table_args__ = (
        Index("idx_cleanup_status", "ready_for_cleanup", "rejected_at"),
    )
