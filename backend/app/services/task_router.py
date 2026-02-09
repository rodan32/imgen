"""
Task Router - routes generation tasks to appropriate GPU nodes.

Uses tier-based routing with overflow: prefer lowest sufficient tier,
fall back to higher tiers when overloaded. For batch operations,
distributes work across all capable GPUs.
"""

from __future__ import annotations

import logging
from enum import Enum

from .gpu_registry import GPUNode, GPURegistry, Tier, TIER_ORDER

logger = logging.getLogger(__name__)

# Max queue depth before a GPU is considered overloaded
OVERFLOW_THRESHOLD = 5


class TaskType(str, Enum):
    DRAFT = "draft"           # SD1.5, low steps, low res
    STANDARD = "standard"     # SDXL, normal steps
    QUALITY = "quality"       # SDXL, high steps
    UPSCALE = "upscale"       # ESRGAN upscaling
    FLUX = "flux"             # Flux model
    FLUX_QUALITY = "flux_quality"  # Flux fp16 (premium only)


# Minimum capability required per task type
CAPABILITY_REQUIREMENTS: dict[TaskType, str] = {
    TaskType.DRAFT: "sd15",
    TaskType.STANDARD: "sdxl",
    TaskType.QUALITY: "sdxl",
    TaskType.UPSCALE: "upscale",
    TaskType.FLUX: "flux_fp8",
    TaskType.FLUX_QUALITY: "flux",
}


class NoAvailableGPUError(Exception):
    """Raised when no GPU can handle the requested task."""
    pass


class TaskRouter:
    """Routes tasks to GPUs based on capability, load, and tier preference."""

    def __init__(self, registry: GPURegistry) -> None:
        self.registry = registry

    async def route(
        self,
        task_type: TaskType,
        preferred_gpu: str | None = None,
        model_family: str | None = None,
    ) -> GPUNode:
        """
        Find the best GPU for a task.

        1. If preferred_gpu is set and healthy+capable, use it.
        2. Get all capable nodes for this task type.
        3. Among capable nodes, prefer the least loaded.
        4. For draft tasks, all GPUs can participate (faster is better).
        5. Raise NoAvailableGPUError if nothing available.
        """
        # Check preferred GPU first
        if preferred_gpu:
            node = self.registry.get_node(preferred_gpu)
            if node and node.healthy and self._is_capable(node, task_type, model_family):
                logger.info("Using preferred GPU %s for %s", preferred_gpu, task_type.value)
                return node

        # Get all capable, healthy nodes
        required_cap = model_family or CAPABILITY_REQUIREMENTS.get(task_type, "sd15")
        candidates = self.registry.get_capable_nodes(required_cap)

        if not candidates:
            raise NoAvailableGPUError(
                f"No healthy GPU available for task_type={task_type.value}, "
                f"required_capability={required_cap}"
            )

        # For draft tasks: prefer idle GPUs regardless of tier (faster GPUs = faster drafts)
        # For other tasks: prefer least loaded among capable nodes
        best = self.registry.get_least_loaded(candidates)
        if best is None:
            raise NoAvailableGPUError(f"No GPU available for {task_type.value}")

        logger.info(
            "Routed %s to %s (%s, queue=%d)",
            task_type.value, best.id, best.name, best.current_queue_length,
        )
        return best

    async def route_batch(
        self,
        task_type: TaskType,
        count: int,
        model_family: str | None = None,
    ) -> list[tuple[GPUNode, int]]:
        """
        Distribute a batch of tasks across capable GPUs.

        Returns list of (gpu_node, assigned_count) tuples.
        Distribution is weighted: GPUs with shorter queues and higher
        tiers get proportionally more work.
        """
        required_cap = model_family or CAPABILITY_REQUIREMENTS.get(task_type, "sd15")
        candidates = self.registry.get_capable_nodes(required_cap)

        if not candidates:
            raise NoAvailableGPUError(
                f"No healthy GPU available for batch task_type={task_type.value}"
            )

        # Calculate weights based on available capacity and tier
        weights: list[float] = []
        for node in candidates:
            # Base weight: available queue capacity
            capacity_weight = max(1, OVERFLOW_THRESHOLD - node.current_queue_length)
            # Tier bonus: higher tier GPUs generate faster
            tier_bonus = 1.0 + (node.tier_rank * 0.25)
            weights.append(capacity_weight * tier_bonus)

        total_weight = sum(weights)
        if total_weight == 0:
            # Fallback: distribute evenly
            per_gpu = count // len(candidates)
            remainder = count % len(candidates)
            assignments = []
            for i, node in enumerate(candidates):
                n = per_gpu + (1 if i < remainder else 0)
                if n > 0:
                    assignments.append((node, n))
            return assignments

        # Weighted distribution
        assignments: list[tuple[GPUNode, int]] = []
        remaining = count
        for i, (node, weight) in enumerate(zip(candidates, weights)):
            if i == len(candidates) - 1:
                # Last GPU gets whatever remains (avoids rounding issues)
                n = remaining
            else:
                n = round(count * weight / total_weight)
                n = min(n, remaining)
            remaining -= n
            if n > 0:
                assignments.append((node, n))

        logger.info(
            "Batch distribution for %d %s tasks: %s",
            count, task_type.value,
            [(node.id, n) for node, n in assignments],
        )
        return assignments

    def _is_capable(
        self,
        node: GPUNode,
        task_type: TaskType,
        model_family: str | None = None,
    ) -> bool:
        """Check if a node can handle the given task."""
        required = model_family or CAPABILITY_REQUIREMENTS.get(task_type, "sd15")
        return required in node.capabilities
