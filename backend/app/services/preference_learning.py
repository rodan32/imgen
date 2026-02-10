"""
User preference learning service.

Tracks selections/rejections with context and provides personalized recommendations.
"""

from __future__ import annotations

import json
import logging
import math
from collections import defaultdict
from typing import List, Dict, Tuple, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.preference_orm import UserPreferenceORM, PreferenceStatsORM

logger = logging.getLogger(__name__)


class PreferenceLearning:
    """
    Learn user preferences for checkpoint/LoRA/keyword combinations.

    Tracks:
    - (keyword, checkpoint) affinity
    - (keyword, LoRA) affinity
    - (checkpoint, LoRA) compatibility
    - Overall checkpoint/LoRA quality
    """

    def __init__(self):
        # In-memory cache for fast lookups (synced from DB)
        self.stats_cache: Dict[Tuple[str, str], Dict] = {}
        self.last_cache_update: float = 0

    def extract_keywords(self, prompt: str) -> List[str]:
        """
        Extract meaningful keywords from prompt.

        Simple implementation: split on common delimiters, filter short words.
        Future: Use LLM for semantic extraction.
        """
        # Remove common prompt syntax
        cleaned = prompt.lower()
        for remove in [",", ".", "!", "?", ";", ":", "(", ")", "[", "]"]:
            cleaned = cleaned.replace(remove, " ")

        # Split and filter
        words = cleaned.split()
        keywords = [
            w for w in words
            if len(w) >= 3 and w not in {
                "the", "and", "with", "for", "very", "best", "high", "quality",
                "detailed", "masterpiece", "professional", "realistic"
            }
        ]

        return keywords[:10]  # Limit to 10 most relevant

    async def record_preference(
        self,
        db: AsyncSession,
        prompt: str,
        checkpoint: str,
        loras: List[Dict[str, float]],
        selected: bool,
        rejected: bool,
        model_family: str,
        task_type: str,
        stage: int,
        session_id: str,
        generation_id: str,
        feedback_text: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        vision_description: Optional[str] = None,
        user_id: str = "default",
    ):
        """
        Record a user preference with full context.

        Args:
            selected: User selected this image
            rejected: User rejected this image
            Other args: Context for learning
        """
        keywords = self.extract_keywords(prompt)
        action = "selected" if selected else ("rejected" if rejected else "neutral")

        # Store preference record
        pref = UserPreferenceORM(
            user_id=user_id,
            prompt=prompt,
            keywords=json.dumps(keywords),
            negative_prompt=negative_prompt,
            checkpoint=checkpoint,
            loras=json.dumps(loras),
            model_family=model_family,
            task_type=task_type,
            action=action,
            feedback_text=feedback_text,
            stage=stage,
            session_id=session_id,
            generation_id=generation_id,
            vision_description=vision_description,
        )
        db.add(pref)

        # Update aggregated stats
        await self._update_stats(
            db, user_id, keywords, checkpoint, loras, selected
        )

        await db.commit()

        logger.info(
            "Recorded preference: %s, checkpoint=%s, keywords=%s",
            action, checkpoint, keywords[:3]
        )

    async def _update_stats(
        self,
        db: AsyncSession,
        user_id: str,
        keywords: List[str],
        checkpoint: str,
        loras: List[Dict[str, float]],
        selected: bool,
    ):
        """Update aggregated statistics for fast lookups."""

        # Update keyword + checkpoint stats
        for keyword in keywords:
            await self._increment_stat(
                db, user_id, "keyword_checkpoint", f"{keyword}:{checkpoint}", selected
            )

        # Update keyword + LoRA stats
        for lora in loras:
            lora_name = lora.get("name", "")
            for keyword in keywords:
                await self._increment_stat(
                    db, user_id, "keyword_lora", f"{keyword}:{lora_name}", selected
                )

        # Update checkpoint + LoRA stats
        for lora in loras:
            lora_name = lora.get("name", "")
            await self._increment_stat(
                db, user_id, "checkpoint_lora", f"{checkpoint}:{lora_name}", selected
            )

        # Update overall checkpoint stats
        await self._increment_stat(
            db, user_id, "checkpoint_overall", checkpoint, selected
        )

    async def _increment_stat(
        self,
        db: AsyncSession,
        user_id: str,
        stat_type: str,
        key: str,
        selected: bool,
    ):
        """Increment or create a stat entry."""
        # Try to find existing stat
        result = await db.execute(
            select(PreferenceStatsORM).where(
                PreferenceStatsORM.user_id == user_id,
                PreferenceStatsORM.stat_type == stat_type,
                PreferenceStatsORM.key == key,
            )
        )
        stat = result.scalar_one_or_none()

        if stat:
            # Update existing
            stat.total_count += 1
            if selected:
                stat.selected_count += 1
            stat.selection_rate = stat.selected_count / stat.total_count
            stat.confidence_score = self._calculate_confidence(stat.total_count)
        else:
            # Create new
            stat = PreferenceStatsORM(
                user_id=user_id,
                stat_type=stat_type,
                key=key,
                selected_count=1 if selected else 0,
                total_count=1,
                selection_rate=1.0 if selected else 0.0,
                confidence_score=self._calculate_confidence(1),
            )
            db.add(stat)

    def _calculate_confidence(self, sample_size: int) -> float:
        """
        Calculate confidence score based on sample size.

        Returns 0.0-1.0, reaches 0.9 at 20 samples, asymptotic to 1.0.
        """
        return min(sample_size / 20.0, 1.0)

    async def get_checkpoint_score(
        self,
        db: AsyncSession,
        checkpoint: str,
        keywords: List[str],
        user_id: str = "default",
        global_fallback: float = 0.5,
    ) -> float:
        """
        Get score for checkpoint given prompt keywords.

        Blends personal history with global stats based on confidence.
        """
        scores = []

        for keyword in keywords:
            key = f"{keyword}:{checkpoint}"
            result = await db.execute(
                select(PreferenceStatsORM).where(
                    PreferenceStatsORM.user_id == user_id,
                    PreferenceStatsORM.stat_type == "keyword_checkpoint",
                    PreferenceStatsORM.key == key,
                )
            )
            stat = result.scalar_one_or_none()

            if stat and stat.total_count >= 3:
                # Have personal data
                scores.append(stat.selection_rate)
            else:
                # No personal data, use global fallback
                scores.append(global_fallback)

        # Average scores across keywords
        return sum(scores) / len(scores) if scores else global_fallback

    async def recommend_checkpoint(
        self,
        db: AsyncSession,
        prompt: str,
        available_checkpoints: List[str],
        user_id: str = "default",
    ) -> Tuple[str, float]:
        """
        Recommend best checkpoint for prompt based on user history.

        Returns: (checkpoint_name, confidence_score)
        """
        keywords = self.extract_keywords(prompt)

        if not keywords:
            # No keywords, use overall stats
            return available_checkpoints[0], 0.0

        checkpoint_scores = {}
        for checkpoint in available_checkpoints:
            score = await self.get_checkpoint_score(
                db, checkpoint, keywords, user_id
            )
            checkpoint_scores[checkpoint] = score

        # Return best scoring checkpoint
        best_checkpoint = max(checkpoint_scores.items(), key=lambda x: x[1])
        return best_checkpoint

    async def recommend_loras(
        self,
        db: AsyncSession,
        prompt: str,
        available_loras: List[str],
        checkpoint: str,
        count: int = 3,
        user_id: str = "default",
    ) -> List[Tuple[str, float]]:
        """
        Recommend LoRAs for prompt + checkpoint based on user history.

        Returns: [(lora_name, score), ...]
        """
        keywords = self.extract_keywords(prompt)

        if not keywords:
            return []

        lora_scores = {}
        for lora in available_loras:
            scores = []

            # Score based on keyword affinity
            for keyword in keywords:
                key = f"{keyword}:{lora}"
                result = await db.execute(
                    select(PreferenceStatsORM).where(
                        PreferenceStatsORM.user_id == user_id,
                        PreferenceStatsORM.stat_type == "keyword_lora",
                        PreferenceStatsORM.key == key,
                    )
                )
                stat = result.scalar_one_or_none()

                if stat and stat.total_count >= 3:
                    scores.append(stat.selection_rate)

            # Check checkpoint compatibility
            compat_key = f"{checkpoint}:{lora}"
            result = await db.execute(
                select(PreferenceStatsORM).where(
                    PreferenceStatsORM.user_id == user_id,
                    PreferenceStatsORM.stat_type == "checkpoint_lora",
                    PreferenceStatsORM.key == compat_key,
                )
            )
            compat_stat = result.scalar_one_or_none()

            if compat_stat and compat_stat.total_count >= 3:
                # Have compatibility data
                if compat_stat.selection_rate < 0.3:
                    # Bad compatibility, skip this LoRA
                    continue
                scores.append(compat_stat.selection_rate)

            if scores:
                lora_scores[lora] = sum(scores) / len(scores)

        # Return top N LoRAs
        sorted_loras = sorted(lora_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_loras[:count]

    async def get_stats_summary(
        self,
        db: AsyncSession,
        user_id: str = "default",
    ) -> Dict[str, any]:
        """
        Get summary of preference learning data.

        Returns stats for UI display.
        """
        # Count total preferences
        result = await db.execute(
            select(func.count(UserPreferenceORM.id)).where(
                UserPreferenceORM.user_id == user_id
            )
        )
        total_prefs = result.scalar()

        # Count by action
        result = await db.execute(
            select(
                UserPreferenceORM.action,
                func.count(UserPreferenceORM.id)
            )
            .where(UserPreferenceORM.user_id == user_id)
            .group_by(UserPreferenceORM.action)
        )
        action_counts = dict(result.all())

        # Get top checkpoints
        result = await db.execute(
            select(PreferenceStatsORM)
            .where(
                PreferenceStatsORM.user_id == user_id,
                PreferenceStatsORM.stat_type == "checkpoint_overall",
                PreferenceStatsORM.total_count >= 5,
            )
            .order_by(PreferenceStatsORM.selection_rate.desc())
            .limit(10)
        )
        top_checkpoints = [
            {
                "checkpoint": stat.key,
                "selection_rate": stat.selection_rate,
                "total": stat.total_count,
                "selected": stat.selected_count,
            }
            for stat in result.scalars().all()
        ]

        return {
            "total_preferences": total_prefs,
            "action_counts": action_counts,
            "top_checkpoints": top_checkpoints,
        }

    async def export_preferences(
        self,
        db: AsyncSession,
        user_id: str = "default",
    ) -> Dict[str, any]:
        """
        Export all preference data as JSON.

        For backup and portability across systems.
        """
        # Get all preferences
        result = await db.execute(
            select(UserPreferenceORM)
            .where(UserPreferenceORM.user_id == user_id)
            .order_by(UserPreferenceORM.timestamp.desc())
        )
        prefs = result.scalars().all()

        # Get all stats
        result = await db.execute(
            select(PreferenceStatsORM)
            .where(PreferenceStatsORM.user_id == user_id)
        )
        stats = result.scalars().all()

        return {
            "version": "1.0",
            "user_id": user_id,
            "total_preferences": len(prefs),
            "preferences": [
                {
                    "prompt": p.prompt,
                    "keywords": json.loads(p.keywords),
                    "checkpoint": p.checkpoint,
                    "loras": json.loads(p.loras),
                    "action": p.action,
                    "timestamp": p.timestamp.isoformat(),
                }
                for p in prefs
            ],
            "stats": [
                {
                    "type": s.stat_type,
                    "key": s.key,
                    "selected": s.selected_count,
                    "total": s.total_count,
                    "rate": s.selection_rate,
                }
                for s in stats
            ],
        }
