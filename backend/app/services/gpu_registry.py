"""
GPU Registry - manages ComfyUI GPU nodes, health checks, and capability tracking.

Loads configuration from config/gpus.yaml and maintains runtime state
(health, queue depth) for each registered GPU node.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import httpx
import yaml

logger = logging.getLogger(__name__)


class Tier(str, Enum):
    DRAFT = "draft"
    STANDARD = "standard"
    QUALITY = "quality"
    PREMIUM = "premium"


TIER_ORDER: dict[Tier, int] = {
    Tier.DRAFT: 0,
    Tier.STANDARD: 1,
    Tier.QUALITY: 2,
    Tier.PREMIUM: 3,
}


@dataclass
class GPUNode:
    id: str
    name: str
    vram_gb: int
    tier: Tier
    host: str
    port: int
    capabilities: set[str]
    max_resolution: int
    max_batch: int
    # Runtime state
    current_queue_length: int = 0
    healthy: bool = False
    last_health_check: float = 0.0
    last_response_ms: float = 0.0

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}:{self.port}/ws"

    @property
    def tier_rank(self) -> int:
        return TIER_ORDER[self.tier]


class GPURegistry:
    """
    Singleton registry of GPU nodes. Loads from YAML config and runs
    periodic health checks against each ComfyUI instance.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, GPUNode] = {}
        self._health_task: asyncio.Task | None = None

    def load_from_yaml(self, path: str | Path) -> None:
        """Parse gpus.yaml into GPUNode objects."""
        path = Path(path)
        if not path.exists():
            logger.warning("GPU config not found at %s, starting with no nodes", path)
            return

        with open(path) as f:
            config = yaml.safe_load(f)

        for entry in config.get("nodes", []):
            node = GPUNode(
                id=entry["id"],
                name=entry["name"],
                vram_gb=entry["vram_gb"],
                tier=Tier(entry["tier"]),
                host=entry["host"],
                port=entry["port"],
                capabilities=set(entry.get("capabilities", [])),
                max_resolution=entry.get("max_resolution", 1024),
                max_batch=entry.get("max_batch", 1),
            )
            self.nodes[node.id] = node
            logger.info("Registered GPU node: %s (%s, %s tier)", node.id, node.name, node.tier.value)

    async def check_health(self, node: GPUNode) -> bool:
        """Check if a single ComfyUI instance is responsive."""
        try:
            start = time.monotonic()
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{node.base_url}/system_stats")
                elapsed_ms = (time.monotonic() - start) * 1000

                if resp.status_code == 200:
                    node.healthy = True
                    node.last_response_ms = elapsed_ms
                    node.last_health_check = time.time()

                    # Also check queue depth
                    try:
                        queue_resp = await client.get(f"{node.base_url}/queue")
                        if queue_resp.status_code == 200:
                            queue_data = queue_resp.json()
                            running = len(queue_data.get("queue_running", []))
                            pending = len(queue_data.get("queue_pending", []))
                            node.current_queue_length = running + pending
                    except Exception:
                        pass  # Queue check is best-effort

                    logger.debug(
                        "Health OK: %s (%s, %.0fms, queue=%d)",
                        node.id, node.name, elapsed_ms, node.current_queue_length,
                    )
                    return True
                else:
                    node.healthy = False
                    logger.warning("Health FAIL: %s returned status %d", node.id, resp.status_code)
                    return False

        except (httpx.ConnectError, httpx.TimeoutException, httpx.ConnectTimeout) as e:
            node.healthy = False
            node.last_health_check = time.time()
            logger.warning("Health FAIL: %s - %s", node.id, type(e).__name__)
            return False

    async def check_all_health(self) -> dict[str, bool]:
        """Check health of all nodes concurrently."""
        results = await asyncio.gather(
            *(self.check_health(node) for node in self.nodes.values()),
            return_exceptions=True,
        )
        return {
            node_id: (result is True)
            for node_id, result in zip(self.nodes.keys(), results)
        }

    async def start_health_check_loop(self, interval: float = 10.0) -> None:
        """Background loop that checks all nodes periodically."""
        logger.info("Starting GPU health check loop (interval=%.1fs)", interval)
        while True:
            try:
                await self.check_all_health()
            except Exception:
                logger.exception("Error in health check loop")
            await asyncio.sleep(interval)

    def start_background_health_checks(self, interval: float = 10.0) -> asyncio.Task:
        """Start health checks as a background task. Returns the task for cancellation."""
        self._health_task = asyncio.create_task(self.start_health_check_loop(interval))
        return self._health_task

    def stop_health_checks(self) -> None:
        """Cancel the background health check task."""
        if self._health_task:
            self._health_task.cancel()
            self._health_task = None

    # --- Query methods ---

    def get_all_nodes(self) -> list[GPUNode]:
        return list(self.nodes.values())

    def get_healthy_nodes(self) -> list[GPUNode]:
        return [n for n in self.nodes.values() if n.healthy]

    def get_capable_nodes(self, capability: str) -> list[GPUNode]:
        return [n for n in self.nodes.values() if n.healthy and capability in n.capabilities]

    def get_nodes_at_or_above_tier(self, min_tier: Tier) -> list[GPUNode]:
        min_rank = TIER_ORDER[min_tier]
        return [n for n in self.nodes.values() if n.healthy and n.tier_rank >= min_rank]

    def get_least_loaded(self, candidates: list[GPUNode]) -> GPUNode | None:
        if not candidates:
            return None
        return min(candidates, key=lambda n: n.current_queue_length)

    def get_node(self, gpu_id: str) -> GPUNode | None:
        return self.nodes.get(gpu_id)

    def increment_load(self, gpu_id: str) -> None:
        if gpu_id in self.nodes:
            self.nodes[gpu_id].current_queue_length += 1

    def decrement_load(self, gpu_id: str) -> None:
        if gpu_id in self.nodes:
            self.nodes[gpu_id].current_queue_length = max(0, self.nodes[gpu_id].current_queue_length - 1)
