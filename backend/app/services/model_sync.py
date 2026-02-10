"""
Model synchronization and caching management.

Tracks what models are available on NAS vs locally cached on each node.
Implements smart caching based on usage patterns.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Set, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Information about a model file."""
    name: str
    path: str
    size_mb: float
    model_type: str  # "checkpoint", "lora", "controlnet", "upscale"
    family: str  # "sd15", "sdxl", "unknown"
    last_used: Optional[datetime] = None
    use_count: int = 0


@dataclass
class NodeModelCache:
    """Track what's cached on a specific GPU node."""
    node_id: str
    cached_checkpoints: Set[str] = field(default_factory=set)
    cached_loras: Set[str] = field(default_factory=set)
    cache_capacity_mb: float = 0  # Available disk space for caching
    cache_used_mb: float = 0
    last_sync: Optional[datetime] = None


class ModelSyncManager:
    """
    Manages model synchronization between NAS and GPU nodes.

    Strategy:
    - NAS is the source of truth (master copies)
    - Each node caches models locally for performance
    - Hot models (frequently used) stay cached
    - Cold models (rarely used) can be evicted
    - 3050Ti gets only SD1.5 models (VRAM constraint)
    """

    def __init__(self):
        # Master list from NAS (all model types)
        self.nas_checkpoints: Dict[str, ModelInfo] = {}
        self.nas_loras: Dict[str, ModelInfo] = {}
        self.nas_controlnets: Dict[str, ModelInfo] = {}
        self.nas_embeddings: Dict[str, ModelInfo] = {}  # Textual Inversions
        self.nas_ipadapters: Dict[str, ModelInfo] = {}
        self.nas_upscalers: Dict[str, ModelInfo] = {}
        self.nas_vae: Dict[str, ModelInfo] = {}

        # Per-node caches
        self.node_caches: Dict[str, NodeModelCache] = {}

        # Usage tracking for smart caching
        self.model_usage: Dict[str, List[datetime]] = defaultdict(list)

        # Node capabilities (from config)
        self.node_constraints = {
            "gpu-draft": {
                "max_cache_mb": 10000,  # 10GB cache
                "allowed_families": ["sd15"],  # 3050Ti: SD1.5 only
            },
            "gpu-standard": {
                "max_cache_mb": 30000,  # 30GB cache
                "allowed_families": ["sd15", "sdxl"],
            },
            "gpu-quality": {
                "max_cache_mb": 30000,
                "allowed_families": ["sd15", "sdxl"],
            },
            "gpu-premium": {
                "max_cache_mb": 50000,  # 50GB cache
                "allowed_families": ["sd15", "sdxl"],
            },
        }

    def register_node(self, node_id: str, cache_capacity_mb: float = None):
        """Register a GPU node for cache tracking."""
        if cache_capacity_mb is None:
            cache_capacity_mb = self.node_constraints.get(node_id, {}).get("max_cache_mb", 30000)

        self.node_caches[node_id] = NodeModelCache(
            node_id=node_id,
            cache_capacity_mb=cache_capacity_mb,
        )
        logger.info("Registered node %s with %.1fGB cache capacity",
                   node_id, cache_capacity_mb / 1024)

    async def discover_nas_models(self, client_pool) -> Dict[str, int]:
        """
        Discover all models available on NAS by querying a reference node.

        Assumes all nodes can see NAS models (either via mount or symlink).
        Returns: {checkpoint_count, lora_count, controlnet_count, ...}
        """
        # Query one healthy node to get full model list
        # (All nodes should see the same NAS-backed models)
        client = client_pool.get_any_healthy_client()
        if not client:
            logger.warning("No healthy GPU nodes to query for NAS models")
            return {}

        try:
            object_info = await client.get_object_info()

            # Extract checkpoints
            ckpt_node = object_info.get("CheckpointLoaderSimple", {})
            ckpt_list = ckpt_node.get("input", {}).get("ckpt_name", [[]])[0]

            # Extract LoRAs
            lora_node = object_info.get("LoraLoader", {})
            lora_list = lora_node.get("input", {}).get("lora_name", [[]])[0]

            # Extract ControlNets
            controlnet_node = object_info.get("ControlNetLoader", {})
            controlnet_list = controlnet_node.get("input", {}).get("control_net_name", [[]])[0] if controlnet_node else []

            # Extract Textual Inversions (Embeddings)
            # These don't have a loader node, they're just in embeddings folder
            # Will be discovered via file system if needed

            # Extract IP-Adapters
            ipadapter_node = object_info.get("IPAdapterModelLoader", {})
            ipadapter_list = ipadapter_node.get("input", {}).get("ipadapter_file", [[]])[0] if ipadapter_node else []

            # Extract Upscale Models
            upscale_node = object_info.get("UpscaleModelLoader", {})
            upscale_list = upscale_node.get("input", {}).get("model_name", [[]])[0] if upscale_node else []

            # Extract VAE
            vae_node = object_info.get("VAELoader", {})
            vae_list = vae_node.get("input", {}).get("vae_name", [[]])[0] if vae_node else []

            # Classify by family (SD1.5 vs SDXL)
            for ckpt_name in ckpt_list:
                family = self._classify_model_family(ckpt_name)
                self.nas_checkpoints[ckpt_name] = ModelInfo(
                    name=ckpt_name,
                    path=f"checkpoints/{ckpt_name}",
                    size_mb=0,  # TODO: Query actual size
                    model_type="checkpoint",
                    family=family,
                )

            for lora_name in lora_list:
                family = self._classify_model_family(lora_name)
                self.nas_loras[lora_name] = ModelInfo(
                    name=lora_name,
                    path=f"loras/{lora_name}",
                    size_mb=0,
                    model_type="lora",
                    family=family,
                )

            for cn_name in controlnet_list:
                family = self._classify_model_family(cn_name)
                self.nas_controlnets[cn_name] = ModelInfo(
                    name=cn_name,
                    path=f"controlnet/{cn_name}",
                    size_mb=0,
                    model_type="controlnet",
                    family=family,
                )

            for ipa_name in ipadapter_list:
                family = self._classify_model_family(ipa_name)
                self.nas_ipadapters[ipa_name] = ModelInfo(
                    name=ipa_name,
                    path=f"ipadapter/{ipa_name}",
                    size_mb=0,
                    model_type="ipadapter",
                    family=family,
                )

            for up_name in upscale_list:
                self.nas_upscalers[up_name] = ModelInfo(
                    name=up_name,
                    path=f"upscale_models/{up_name}",
                    size_mb=0,
                    model_type="upscaler",
                    family="universal",  # Most upscalers work with any model
                )

            for vae_name in vae_list:
                family = self._classify_model_family(vae_name)
                self.nas_vae[vae_name] = ModelInfo(
                    name=vae_name,
                    path=f"vae/{vae_name}",
                    size_mb=0,
                    model_type="vae",
                    family=family,
                )

            logger.info(
                "Discovered models on NAS: %d checkpoints, %d LoRAs, %d ControlNets, "
                "%d IP-Adapters, %d Upscalers, %d VAE",
                len(self.nas_checkpoints),
                len(self.nas_loras),
                len(self.nas_controlnets),
                len(self.nas_ipadapters),
                len(self.nas_upscalers),
                len(self.nas_vae),
            )

            return {
                "checkpoints": len(self.nas_checkpoints),
                "loras": len(self.nas_loras),
                "controlnets": len(self.nas_controlnets),
                "ipadapters": len(self.nas_ipadapters),
                "upscalers": len(self.nas_upscalers),
                "vae": len(self.nas_vae),
            }

        except Exception as e:
            logger.error("Failed to discover NAS models: %s", e)
            return {}

    def _classify_model_family(self, model_name: str) -> str:
        """Classify model as SD1.5 or SDXL based on naming conventions."""
        name_lower = model_name.lower()

        # SDXL indicators
        if any(x in name_lower for x in ["xl", "sdxl", "pony", "juggernaut"]):
            return "sdxl"

        # SD1.5 indicators
        if any(x in name_lower for x in ["v1-5", "sd15", "1.5", "dreamshaper"]):
            return "sd15"

        # Default: assume SDXL if it's large
        return "sdxl"

    def can_node_use_model(self, node_id: str, model_name: str, model_type: str = "checkpoint") -> bool:
        """Check if a node can use this model based on constraints."""
        constraints = self.node_constraints.get(node_id, {})
        allowed_families = constraints.get("allowed_families", ["sd15", "sdxl"])

        # Get model info
        if model_type == "checkpoint":
            model_info = self.nas_checkpoints.get(model_name)
        else:
            model_info = self.nas_loras.get(model_name)

        if not model_info:
            return False

        # Check if node can handle this model family
        return model_info.family in allowed_families

    def record_model_usage(self, model_name: str, timestamp: datetime = None):
        """Record that a model was used (for cache prioritization)."""
        if timestamp is None:
            timestamp = datetime.now()

        self.model_usage[model_name].append(timestamp)

        # Update model info
        if model_name in self.nas_checkpoints:
            self.nas_checkpoints[model_name].last_used = timestamp
            self.nas_checkpoints[model_name].use_count += 1
        elif model_name in self.nas_loras:
            self.nas_loras[model_name].last_used = timestamp
            self.nas_loras[model_name].use_count += 1

    def get_hot_models(self, days: int = 7, min_uses: int = 3) -> Dict[str, List[str]]:
        """
        Get frequently used models (candidates for local caching).

        Returns: {
            "checkpoints": [names...],
            "loras": [names...]
        }
        """
        cutoff = datetime.now() - timedelta(days=days)
        hot_checkpoints = []
        hot_loras = []

        for name, timestamps in self.model_usage.items():
            recent_uses = [t for t in timestamps if t > cutoff]
            if len(recent_uses) >= min_uses:
                if name in self.nas_checkpoints:
                    hot_checkpoints.append(name)
                elif name in self.nas_loras:
                    hot_loras.append(name)

        return {
            "checkpoints": hot_checkpoints,
            "loras": hot_loras,
        }

    def recommend_cache_for_node(self, node_id: str, max_items: int = 10) -> Dict[str, List[str]]:
        """
        Recommend which models should be cached locally on a node.

        Based on:
        - Node constraints (SD1.5 only for 3050Ti)
        - Usage frequency
        - Cache capacity
        """
        constraints = self.node_constraints.get(node_id, {})
        allowed_families = constraints.get("allowed_families", ["sd15", "sdxl"])

        # Get hot models
        hot = self.get_hot_models()

        # Filter by what this node can use
        recommended_checkpoints = [
            name for name in hot["checkpoints"]
            if self.nas_checkpoints[name].family in allowed_families
        ][:max_items]

        recommended_loras = [
            name for name in hot["loras"]
            if self.nas_loras[name].family in allowed_families
        ][:max_items]

        return {
            "checkpoints": recommended_checkpoints,
            "loras": recommended_loras,
        }

    def get_sync_status(self) -> Dict[str, any]:
        """Get current sync status for all nodes."""
        return {
            "nas_models": {
                "checkpoints": len(self.nas_checkpoints),
                "loras": len(self.nas_loras),
            },
            "nodes": {
                node_id: {
                    "cached_checkpoints": len(cache.cached_checkpoints),
                    "cached_loras": len(cache.cached_loras),
                    "cache_used_mb": cache.cache_used_mb,
                    "cache_capacity_mb": cache.cache_capacity_mb,
                    "last_sync": cache.last_sync.isoformat() if cache.last_sync else None,
                }
                for node_id, cache in self.node_caches.items()
            },
            "hot_models": self.get_hot_models(),
        }
