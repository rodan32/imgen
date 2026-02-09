"""
Workflow Engine - loads ComfyUI workflow templates and builds parameterized workflows.

Templates are ComfyUI API-format JSON files with {{variable}} placeholders.
The engine substitutes parameters, injects LoRAs, and handles img2img setup.
"""

from __future__ import annotations

import copy
import json
import logging
import random
import re
from pathlib import Path

import yaml

from .gpu_registry import GPUNode

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Loads workflow templates and builds parameterized ComfyUI workflows."""

    def __init__(self, templates_dir: str | Path) -> None:
        self.templates_dir = Path(templates_dir)
        self.templates: dict[str, dict] = {}        # name -> parsed JSON workflow
        self.manifest: dict[str, dict] = {}          # name -> manifest entry
        self.default_checkpoints: dict[str, str] = {
            "sd15": "v1-5-pruned-emaonly.safetensors",
            "sdxl": "sd_xl_base_1.0.safetensors",
            "pony": "sd_xl_base_1.0.safetensors",
            "illustrious": "sd_xl_base_1.0.safetensors",
            "flux": "flux1-dev-fp8.safetensors",
        }

    def load_templates(self) -> None:
        """Load manifest and all template JSON files."""
        manifest_path = self.templates_dir / "manifest.yaml"
        if not manifest_path.exists():
            logger.warning("No manifest.yaml found at %s", manifest_path)
            return

        with open(manifest_path) as f:
            manifest_data = yaml.safe_load(f)

        for entry in manifest_data.get("templates", []):
            name = entry["name"]
            json_path = self.templates_dir / f"{name}.json"

            if not json_path.exists():
                logger.warning("Template %s referenced in manifest but %s not found", name, json_path)
                continue

            with open(json_path) as f:
                template = json.load(f)

            self.templates[name] = template
            self.manifest[name] = entry
            logger.info("Loaded workflow template: %s", name)

    def select_template(
        self,
        model_family: str,
        is_img2img: bool = False,
        has_loras: bool = False,
    ) -> str:
        """
        Auto-select the best template based on requirements.
        Returns template name.
        """
        # Map model families to template prefixes
        if model_family in ("flux",):
            prefix = "flux"
        elif model_family in ("sd15",):
            prefix = "sd15"
        else:
            prefix = "sdxl"  # sdxl, pony, illustrious all use sdxl templates

        # Build candidate name
        if has_loras and f"{prefix}_with_lora" in self.templates:
            return f"{prefix}_with_lora"
        elif is_img2img and f"{prefix}_img2img" in self.templates:
            return f"{prefix}_img2img"
        elif f"{prefix}_txt2img" in self.templates:
            return f"{prefix}_txt2img"

        # Fallback: try any template for this family
        for name, entry in self.manifest.items():
            families = entry.get("model_families", [])
            if model_family in families or "any" in families:
                return name

        raise ValueError(f"No template found for model_family={model_family}")

    def build_workflow(
        self,
        template_name: str,
        params: dict,
        gpu_node: GPUNode | None = None,
    ) -> dict:
        """
        Build a complete ComfyUI workflow from a template and parameters.

        Args:
            template_name: Name of the template to use
            params: Dictionary with keys like:
                - prompt, negative_prompt, checkpoint, width, height,
                  steps, cfg_scale, sampler, scheduler, denoise_strength,
                  seed, filename_prefix, source_image_filename
                - loras: list of {"name": str, "strength_model": float, "strength_clip": float}
            gpu_node: Optional GPU node for applying constraints

        Returns:
            Complete workflow dict ready for ComfyUI /prompt endpoint.
        """
        if template_name not in self.templates:
            raise ValueError(f"Unknown template: {template_name}")

        workflow = copy.deepcopy(self.templates[template_name])
        manifest = self.manifest.get(template_name, {})

        # Resolve checkpoint
        model_family = params.get("model_family", "sdxl")
        checkpoint = params.get("checkpoint") or self.default_checkpoints.get(model_family, "sd_xl_base_1.0.safetensors")

        # Resolve seed
        seed = params.get("seed", -1)
        if seed == -1:
            seed = random.randint(0, 2**32 - 1)

        # Build substitution values
        values = {
            "prompt": params.get("prompt", ""),
            "negative_prompt": params.get("negative_prompt", ""),
            "checkpoint": checkpoint,
            "width": params.get("width", 1024),
            "height": params.get("height", 1024),
            "steps": params.get("steps", 20),
            "cfg_scale": params.get("cfg_scale", 7.0),
            "sampler": params.get("sampler", "euler"),
            "scheduler": params.get("scheduler", "normal"),
            "denoise_strength": params.get("denoise_strength", 1.0),
            "seed": seed,
            "filename_prefix": params.get("filename_prefix", "imgen"),
        }

        # Apply GPU constraints
        if gpu_node:
            if gpu_node.tier.value == "draft":
                values["steps"] = min(values["steps"], 12)
                values["width"] = min(values["width"], 512)
                values["height"] = min(values["height"], 512)

        # img2img source image
        if params.get("source_image_filename"):
            values["source_image_filename"] = params["source_image_filename"]

        # Perform substitution
        workflow = self._substitute(workflow, values)

        # Inject LoRAs if requested
        loras = params.get("loras", [])
        if loras:
            workflow = self._inject_loras(workflow, loras)

        return workflow

    def _substitute(self, obj: dict | list | str | int | float, values: dict):
        """
        Recursively substitute {{variable}} placeholders in the workflow.
        Handles both quoted string values and unquoted numeric values.
        """
        if isinstance(obj, dict):
            return {k: self._substitute(v, values) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute(item, values) for item in obj]
        elif isinstance(obj, str):
            # Check for full-string placeholder: "{{variable}}"
            match = re.fullmatch(r"\{\{(\w+)\}\}", obj)
            if match:
                key = match.group(1)
                if key in values:
                    return values[key]

            # Check for embedded placeholders: "some text {{variable}} more text"
            def replacer(m):
                key = m.group(1)
                return str(values.get(key, m.group(0)))

            return re.sub(r"\{\{(\w+)\}\}", replacer, obj)
        else:
            return obj

    def _inject_loras(self, workflow: dict, loras: list[dict]) -> dict:
        """
        Dynamically insert LoraLoader nodes into the workflow.

        Finds the checkpoint loader and KSampler nodes, then inserts
        LoRA loaders in the chain between them.
        """
        # Find existing node IDs and determine next available
        existing_ids = [int(k) for k in workflow.keys() if k.isdigit()]
        next_id = max(existing_ids, default=0) + 100  # start high to avoid collisions

        # Find the checkpoint loader node
        ckpt_node_id = None
        for node_id, node in workflow.items():
            if node.get("class_type") in ("CheckpointLoaderSimple", "CheckpointLoader"):
                ckpt_node_id = node_id
                break

        if not ckpt_node_id:
            logger.warning("No checkpoint loader found in workflow, cannot inject LoRAs")
            return workflow

        # Find all nodes that reference the checkpoint's model output (output index 0)
        # and clip output (output index 1)
        model_consumers = []
        clip_consumers = []
        for node_id, node in workflow.items():
            inputs = node.get("inputs", {})
            for input_key, input_val in inputs.items():
                if isinstance(input_val, list) and len(input_val) == 2:
                    if input_val[0] == ckpt_node_id:
                        if input_val[1] == 0:
                            model_consumers.append((node_id, input_key))
                        elif input_val[1] == 1:
                            clip_consumers.append((node_id, input_key))

        # Insert LoRA loader chain
        prev_model_source = [ckpt_node_id, 0]
        prev_clip_source = [ckpt_node_id, 1]

        for lora in loras:
            lora_node_id = str(next_id)
            next_id += 1

            workflow[lora_node_id] = {
                "class_type": "LoraLoader",
                "inputs": {
                    "lora_name": lora["name"],
                    "strength_model": lora.get("strength_model", 0.8),
                    "strength_clip": lora.get("strength_clip", 0.8),
                    "model": prev_model_source,
                    "clip": prev_clip_source,
                },
            }

            prev_model_source = [lora_node_id, 0]
            prev_clip_source = [lora_node_id, 1]

        # Rewire consumers to point to last LoRA loader instead of checkpoint
        for node_id, input_key in model_consumers:
            workflow[node_id]["inputs"][input_key] = prev_model_source
        for node_id, input_key in clip_consumers:
            workflow[node_id]["inputs"][input_key] = prev_clip_source

        logger.info("Injected %d LoRA(s) into workflow", len(loras))
        return workflow

    def get_template_list(self) -> list[dict]:
        """Return list of available templates with metadata."""
        return [
            {
                "name": name,
                "description": entry.get("description", ""),
                "model_families": entry.get("model_families", []),
                "supports_img2img": entry.get("supports_img2img", False),
                "supports_lora": entry.get("supports_lora", False),
                "default_params": entry.get("default_params", {}),
            }
            for name, entry in self.manifest.items()
        ]
