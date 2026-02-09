"""LoRA discovery and recommendation service."""

from __future__ import annotations

import logging
import re
from typing import List, Dict, Set

logger = logging.getLogger(__name__)


class LoRADiscovery:
    """Discover and recommend LoRAs based on prompt keywords."""

    def __init__(self):
        self.lora_cache: Dict[str, List[str]] = {}  # gpu_id -> list of lora names
        self.keyword_cache: Dict[str, Set[str]] = {}  # lora_name -> set of keywords

    async def fetch_available_loras(self, client, gpu_id: str) -> List[str]:
        """Fetch list of available LoRAs from ComfyUI."""
        try:
            # ComfyUI object_info endpoint contains all available models
            info = await client.get_object_info()
            lora_loader_info = info.get("LoraLoader", {})
            loras = lora_loader_info.get("input", {}).get("required", {}).get("lora_name", [[]])[0]

            self.lora_cache[gpu_id] = loras
            logger.info("Fetched %d LoRAs from %s", len(loras), gpu_id)
            return loras
        except Exception as e:
            logger.warning("Failed to fetch LoRAs from %s: %s", gpu_id, e)
            return []

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
