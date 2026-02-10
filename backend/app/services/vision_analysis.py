"""Vision analysis service using Ollama for image understanding."""

from __future__ import annotations

import logging
import base64
from pathlib import Path
from typing import Optional, Dict, List
import httpx

logger = logging.getLogger(__name__)


class VisionAnalysis:
    """Analyze images using Ollama vision models (read-only, logging only)."""

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.model = "llava:7b"  # Default vision model
        self.enabled = False  # Disabled by default, enable via config

    async def check_availability(self) -> bool:
        """Check if Ollama is available and has vision model."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.ollama_url}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    has_vision = any(self.model in m.get("name", "") for m in models)
                    if has_vision:
                        logger.info("Ollama vision model available: %s", self.model)
                        return True
                    else:
                        logger.warning("Ollama available but %s not found", self.model)
                        return False
        except Exception as e:
            logger.warning("Ollama not available: %s", e)
            return False

    async def analyze_image(
        self,
        image_path: Path,
        prompt: str = "Describe this image in detail, focusing on: subject, setting, lighting, style, and mood. Be specific and concise."
    ) -> Optional[Dict[str, str]]:
        """
        Analyze an image using vision model.

        Returns: {"description": "...", "model": "llava:7b"} or None if disabled/failed
        """
        if not self.enabled:
            return None

        try:
            # Read and encode image
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Call Ollama vision API
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "images": [image_data],
                        "stream": False,
                    }
                )

                if resp.status_code == 200:
                    result = resp.json()
                    description = result.get("response", "").strip()
                    logger.info(
                        "Vision analysis: %s... (model: %s)",
                        description[:100],
                        self.model
                    )
                    return {
                        "description": description,
                        "model": self.model,
                    }
                else:
                    logger.error("Ollama API error: %s", resp.status_code)
                    return None

        except Exception as e:
            logger.error("Vision analysis failed: %s", e)
            return None

    async def analyze_selected_images(
        self,
        image_paths: List[Path],
        original_prompt: str
    ) -> Dict[str, any]:
        """
        Analyze multiple selected images to understand what the user liked.

        This is READ-ONLY logging - does not modify prompts or settings.

        Returns: {
            "common_themes": [...],
            "descriptions": [...]
        }
        """
        if not self.enabled or not image_paths:
            return {"common_themes": [], "descriptions": []}

        descriptions = []
        for img_path in image_paths[:5]:  # Limit to 5 images to avoid slowdown
            analysis = await self.analyze_image(
                img_path,
                prompt="Describe this image focusing on: subject, setting, lighting, composition, style. Be concise."
            )
            if analysis:
                descriptions.append(analysis["description"])

        # Log what we found
        if descriptions:
            logger.info(
                "User selected %d images with prompt '%s'. Vision analysis found:",
                len(image_paths),
                original_prompt[:50]
            )
            for i, desc in enumerate(descriptions, 1):
                logger.info("  Image %d: %s", i, desc[:100])

        # Future: extract common themes using LLM
        # For now, just return raw descriptions
        return {
            "common_themes": [],  # TODO: extract themes
            "descriptions": descriptions,
        }

    async def analyze_rejected_images(
        self,
        image_paths: List[Path],
        original_prompt: str,
        feedback_text: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Analyze rejected images to understand what went wrong.

        This is READ-ONLY logging - does not modify prompts or settings.

        Returns: {
            "common_issues": [...],
            "descriptions": [...]
        }
        """
        if not self.enabled or not image_paths:
            return {"common_issues": [], "descriptions": []}

        descriptions = []
        for img_path in image_paths[:3]:  # Limit to 3 rejected images
            analysis = await self.analyze_image(
                img_path,
                prompt="Describe what you see in this image. Focus on quality issues, composition, lighting, and style."
            )
            if analysis:
                descriptions.append(analysis["description"])

        # Log what we found
        if descriptions:
            logger.info(
                "User rejected images with prompt '%s' (feedback: '%s'). Vision analysis found:",
                original_prompt[:50],
                feedback_text or "none"
            )
            for i, desc in enumerate(descriptions, 1):
                logger.info("  Rejected image %d: %s", i, desc[:100])

        return {
            "common_issues": [],  # TODO: extract issues
            "descriptions": descriptions,
        }
