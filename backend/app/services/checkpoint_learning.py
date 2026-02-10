"""Checkpoint experimentation and learning service."""

from __future__ import annotations

import logging
from typing import List, Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class CheckpointLearning:
    """Track checkpoint performance and suggest optimal checkpoints."""

    def __init__(self):
        # Track selection rates: checkpoint -> {selected: int, total: int}
        self.checkpoint_stats: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"selected": 0, "total": 0}
        )

        # Checkpoint pools for different tiers
        self.checkpoint_pools = {
            "sd15_draft": [
                "beenyouLite_l15.safetensors",
                "realisticVisionV60B1_v51VAE.safetensors",
                "dreamshaper_8.safetensors",
            ],
            "sdxl_standard": [
                "epicrealismXL_pureFix.safetensors",
                "realvisxlV40.safetensors",
                "juggernautXL_v9Rundiffusionphoto2.safetensors",
            ],
        }

    def get_checkpoints_for_tier(
        self,
        model_family: str,
        tier: str,
        explore_mode: bool = True
    ) -> List[str]:
        """
        Get checkpoints to use for a generation tier.

        Args:
            model_family: "sd15" or "sdxl"
            tier: "draft", "standard", "quality"
            explore_mode: If True, return multiple checkpoints for experimentation

        Returns:
            List of checkpoint filenames
        """
        pool_key = f"{model_family}_{tier}"
        pool = self.checkpoint_pools.get(pool_key, [])

        if not pool:
            # Fallback to defaults
            return ["beenyouLite_l15.safetensors"] if model_family == "sd15" else ["epicrealismXL_pureFix.safetensors"]

        if explore_mode and tier == "draft":
            # Return 2-3 checkpoints for experimentation in draft stage
            return pool[:3]
        else:
            # Return best performing checkpoint
            return [self._get_best_checkpoint(pool)]

    def _get_best_checkpoint(self, pool: List[str]) -> str:
        """Get the best performing checkpoint from a pool."""
        best = None
        best_rate = 0.0

        for checkpoint in pool:
            stats = self.checkpoint_stats[checkpoint]
            if stats["total"] == 0:
                continue

            rate = stats["selected"] / stats["total"]
            if rate > best_rate:
                best_rate = rate
                best = checkpoint

        # If no stats yet, return first in pool
        return best or pool[0]

    def record_generation(self, checkpoint: str, selected: bool = False):
        """Record a generation result for learning."""
        stats = self.checkpoint_stats[checkpoint]
        stats["total"] += 1
        if selected:
            stats["selected"] += 1

        logger.debug(
            "Checkpoint %s: %d/%d selected (%.1f%%)",
            checkpoint,
            stats["selected"],
            stats["total"],
            (stats["selected"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        )

    def record_rejection(self, checkpoint: str, count: int = 1):
        """
        Record rejections for a checkpoint.

        When all images in a batch are rejected, this signals the checkpoint
        may not be suitable for that prompt/style.
        """
        stats = self.checkpoint_stats[checkpoint]
        stats["total"] += count
        # Rejections don't increment selected, lowering the selection rate

        logger.info(
            "Checkpoint %s rejected %d times, selection rate: %.1f%%",
            checkpoint,
            count,
            (stats["selected"] / stats["total"]) * 100 if stats["total"] > 0 else 0
        )

    def get_stats_summary(self) -> Dict[str, Dict[str, any]]:
        """Get summary of checkpoint performance."""
        summary = {}
        for checkpoint, stats in self.checkpoint_stats.items():
            if stats["total"] > 0:
                summary[checkpoint] = {
                    "selected": stats["selected"],
                    "total": stats["total"],
                    "selection_rate": stats["selected"] / stats["total"],
                }
        return summary

    def distribute_batch_across_checkpoints(
        self,
        total_count: int,
        checkpoints: List[str]
    ) -> Dict[str, int]:
        """
        Distribute a batch across multiple checkpoints.

        Returns: {checkpoint: count} mapping
        """
        if len(checkpoints) == 1:
            return {checkpoints[0]: total_count}

        # Distribute evenly, with remainder going to best checkpoint
        base_count = total_count // len(checkpoints)
        remainder = total_count % len(checkpoints)

        distribution = {}
        for i, checkpoint in enumerate(checkpoints):
            count = base_count
            if i == 0:  # Give remainder to first (best) checkpoint
                count += remainder
            distribution[checkpoint] = count

        return distribution
