"""LoRA discovery and recommendation service."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import List, Dict, Set, Optional

logger = logging.getLogger(__name__)


class LoRADiscovery:
    """Discover and recommend LoRAs based on prompt keywords."""

    def __init__(self):
        self.lora_cache: Dict[str, List[str]] = {}  # gpu_id -> list of lora names
        self.keyword_cache: Dict[str, Set[str]] = {}  # lora_name -> set of keywords
        self.last_update: Dict[str, float] = {}  # gpu_id -> timestamp
        self.polling_task: Optional[asyncio.Task] = None
        self.client_pool = None  # Will be set during initialization

    async def start_polling(self, client_pool, interval: float = 300.0):
        """Start background polling of LoRAs from all GPU nodes."""
        self.client_pool = client_pool
        self.polling_task = asyncio.create_task(self._poll_loop(interval))
        logger.info("Started LoRA polling (interval=%.1fs)", interval)

    async def stop_polling(self):
        """Stop background polling."""
        if self.polling_task:
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped LoRA polling")

    async def _poll_loop(self, interval: float):
        """Background loop to poll LoRAs periodically."""
        # Do an immediate poll on startup
        await self._poll_all_gpus()

        while True:
            try:
                await asyncio.sleep(interval)
                await self._poll_all_gpus()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in LoRA polling loop: %s", e)

    async def _poll_all_gpus(self):
        """Poll LoRAs from all GPU nodes."""
        if not self.client_pool:
            return

        import time
        tasks = []
        for gpu_id, client in self.client_pool.clients.items():
            tasks.append(self._fetch_and_cache(client, gpu_id))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _fetch_and_cache(self, client, gpu_id: str):
        """Fetch LoRAs from a single GPU and cache them."""
        import time
        try:
            info = await client.get_object_info()
            lora_loader_info = info.get("LoraLoader", {})
            loras = lora_loader_info.get("input", {}).get("required", {}).get("lora_name", [[]])[0]

            self.lora_cache[gpu_id] = loras
            self.last_update[gpu_id] = time.time()
            logger.info("Cached %d LoRAs from %s", len(loras), gpu_id)
        except Exception as e:
            logger.warning("Failed to fetch LoRAs from %s: %s", gpu_id, e)

    def get_cached_loras(self, gpu_id: Optional[str] = None) -> List[str]:
        """
        Get cached LoRAs for a GPU (or union of all GPUs if gpu_id=None).

        Returns empty list if cache is not yet populated.
        """
        if gpu_id:
            return self.lora_cache.get(gpu_id, [])
        else:
            # Return union of all LoRAs across all GPUs
            all_loras = set()
            for loras in self.lora_cache.values():
                all_loras.update(loras)
            return sorted(all_loras)

    def extract_keywords(self, prompt: str) -> Set[str]:
        """Extract meaningful keywords from prompt."""
        # Remove common SD syntax
        cleaned = re.sub(r'\([^)]*\)', '', prompt)  # Remove weight syntax
        cleaned = re.sub(r'<[^>]*>', '', cleaned)   # Remove embeddings

        # Split and lowercase
        words = cleaned.lower().split()

        # Filter out common words and keep significant terms
        stop_words = {
            'a', 'an', 'the', 'is', 'are', 'was', 'were', 'of', 'in', 'on', 'at',
            'to', 'for', 'with', 'by', 'from', 'as', 'and', 'or', 'but',
            'very', 'highly', 'extremely', 'detailed', 'quality', 'best'
        }

        keywords = {w.strip('.,!?;:') for w in words if len(w) > 3 and w not in stop_words}
        return keywords

    def match_loras_to_prompt(
        self,
        prompt: str,
        available_loras: List[str],
        max_results: int = 5
    ) -> List[Dict[str, any]]:
        """
        Match LoRAs to prompt keywords.

        Returns list of {"name": str, "relevance": float, "matched_keywords": List[str]}
        """
        keywords = self.extract_keywords(prompt)
        if not keywords:
            return []

        matches = []
        for lora_name in available_loras:
            lora_lower = lora_name.lower()
            matched = []

            for keyword in keywords:
                # Check if keyword appears in LoRA name
                if keyword in lora_lower:
                    matched.append(keyword)
                # Check partial matches (e.g., "anime" matches "anime_style")
                elif any(keyword in part for part in lora_lower.split('_')):
                    matched.append(keyword)

            if matched:
                # Calculate relevance score
                relevance = len(matched) / len(keywords)
                matches.append({
                    "name": lora_name,
                    "relevance": relevance,
                    "matched_keywords": matched
                })

        # Sort by relevance and return top matches
        matches.sort(key=lambda x: x["relevance"], reverse=True)
        return matches[:max_results]

    def suggest_lora_specs(
        self,
        prompt: str,
        available_loras: List[str],
        count: int = 3
    ) -> List[Dict[str, any]]:
        """
        Suggest LoRA specifications for generation.

        Returns list of {"name": str, "strengthModel": float, "strengthClip": float}
        """
        matches = self.match_loras_to_prompt(prompt, available_loras, max_results=count)

        specs = []
        for match in matches:
            # Base strength on relevance
            strength = 0.5 + (match["relevance"] * 0.3)  # 0.5 to 0.8 range
            specs.append({
                "name": match["name"],
                "strengthModel": strength,
                "strengthClip": strength,
            })

        return specs
