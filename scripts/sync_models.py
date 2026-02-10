#!/usr/bin/env python3
"""
Model sync script for ComfyUI nodes.

Syncs models from NAS to local cache based on usage patterns.
Run this on each ComfyUI node via cron or manually.

Usage:
    python sync_models.py --node gpu-premium
    python sync_models.py --node gpu-draft --force
"""

import argparse
import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import List, Set

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class ModelSyncer:
    """Sync models from NAS to local ComfyUI cache."""

    def __init__(
        self,
        node_id: str,
        nas_path: Path,
        local_path: Path,
        backend_url: str = "http://backend:8001",
    ):
        self.node_id = node_id
        self.nas_path = nas_path
        self.local_path = local_path
        self.backend_url = backend_url

    async def get_recommended_models(self) -> dict:
        """Query backend for recommended models to cache."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.backend_url}/api/models/recommend-cache",
                    params={"node_id": self.node_id}
                )
                if resp.status_code == 200:
                    return resp.json()
                else:
                    logger.warning("Backend unavailable, syncing all models")
                    return {"checkpoints": [], "loras": []}
        except Exception as e:
            logger.warning("Failed to query backend: %s, syncing all", e)
            return {"checkpoints": [], "loras": []}

    def list_nas_models(self, model_type: str) -> List[str]:
        """List all models of a type available on NAS."""
        nas_dir = self.nas_path / "models" / model_type
        if not nas_dir.exists():
            logger.warning("NAS directory not found: %s", nas_dir)
            return []

        models = []
        for ext in ["*.safetensors", "*.ckpt", "*.pt"]:
            models.extend([f.name for f in nas_dir.glob(ext)])

        return sorted(models)

    def list_local_models(self, model_type: str) -> Set[str]:
        """List models currently cached locally."""
        local_dir = self.local_path / "models" / model_type
        if not local_dir.exists():
            local_dir.mkdir(parents=True, exist_ok=True)
            return set()

        models = set()
        for ext in ["*.safetensors", "*.ckpt", "*.pt"]:
            models.update([f.name for f in local_dir.glob(ext)])

        return models

    def sync_model(self, model_type: str, model_name: str, force: bool = False):
        """Sync a single model from NAS to local cache."""
        nas_file = self.nas_path / "models" / model_type / model_name
        local_file = self.local_path / "models" / model_type / model_name

        if not nas_file.exists():
            logger.error("Model not found on NAS: %s", nas_file)
            return False

        if local_file.exists() and not force:
            logger.debug("Model already cached: %s", model_name)
            return True

        logger.info("Syncing %s/%s (%.1f MB)...",
                   model_type, model_name, nas_file.stat().st_size / 1024 / 1024)

        try:
            # Use rsync for efficient copying with progress
            cmd = [
                "rsync",
                "-avh",
                "--progress",
                str(nas_file),
                str(local_file),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("✓ Synced %s", model_name)
                return True
            else:
                logger.error("✗ Failed to sync %s: %s", model_name, result.stderr)
                return False

        except Exception as e:
            logger.error("✗ Failed to sync %s: %s", model_name, e)
            return False

    def cleanup_old_models(self, model_type: str, keep: Set[str]):
        """Remove models not in the keep set (cache eviction)."""
        local_dir = self.local_path / "models" / model_type
        current = self.list_local_models(model_type)

        to_remove = current - keep
        if not to_remove:
            logger.info("No models to evict from cache")
            return

        logger.info("Evicting %d cold models from cache", len(to_remove))
        for model_name in to_remove:
            local_file = local_dir / model_name
            try:
                local_file.unlink()
                logger.info("✓ Evicted %s", model_name)
            except Exception as e:
                logger.error("✗ Failed to evict %s: %s", model_name, e)

    async def sync_all(self, force: bool = False, evict_cold: bool = False):
        """Sync recommended models to local cache."""
        logger.info("Starting sync for node %s", self.node_id)

        # Get recommendations from backend
        recommended = await self.get_recommended_models()
        recommended_checkpoints = set(recommended.get("checkpoints", []))
        recommended_loras = set(recommended.get("loras", []))

        # If no recommendations, sync all (fallback)
        if not recommended_checkpoints and not recommended_loras:
            logger.info("No recommendations, syncing all models")
            recommended_checkpoints = set(self.list_nas_models("checkpoints"))
            recommended_loras = set(self.list_nas_models("loras"))

        logger.info("Recommended: %d checkpoints, %d LoRAs",
                   len(recommended_checkpoints), len(recommended_loras))

        # Sync checkpoints
        for ckpt in recommended_checkpoints:
            self.sync_model("checkpoints", ckpt, force)

        # Sync LoRAs
        for lora in recommended_loras:
            self.sync_model("loras", lora, force)

        # Optionally evict cold models
        if evict_cold:
            self.cleanup_old_models("checkpoints", recommended_checkpoints)
            self.cleanup_old_models("loras", recommended_loras)

        logger.info("Sync complete for node %s", self.node_id)


async def main():
    parser = argparse.ArgumentParser(description="Sync ComfyUI models from NAS")
    parser.add_argument("--node", required=True, help="Node ID (e.g., gpu-premium)")
    parser.add_argument("--nas-path", default="/mnt/comfyui",
                       help="NAS mount path (default: /mnt/comfyui)")
    parser.add_argument("--local-path", default="~/ComfyUI",
                       help="Local ComfyUI path (default: ~/ComfyUI)")
    parser.add_argument("--backend", default="http://localhost:8001",
                       help="Backend URL (default: http://localhost:8001)")
    parser.add_argument("--force", action="store_true",
                       help="Force re-sync even if file exists")
    parser.add_argument("--evict-cold", action="store_true",
                       help="Remove models not in recommended set")

    args = parser.parse_args()

    nas_path = Path(args.nas_path).expanduser()
    local_path = Path(args.local_path).expanduser()

    if not nas_path.exists():
        logger.error("NAS path not found: %s", nas_path)
        logger.error("Make sure NAS is mounted or provide correct path")
        return 1

    syncer = ModelSyncer(
        node_id=args.node,
        nas_path=nas_path,
        local_path=local_path,
        backend_url=args.backend,
    )

    await syncer.sync_all(force=args.force, evict_cold=args.evict_cold)
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
