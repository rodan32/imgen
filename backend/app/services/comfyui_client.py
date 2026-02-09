"""
ComfyUI Client Pool - HTTP + WebSocket clients for communicating with ComfyUI instances.

Each GPU node gets its own ComfyUIClient with persistent HTTP connection.
The pool manages all clients and provides access by GPU ID.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import AsyncGenerator

import httpx

from .gpu_registry import GPUNode, GPURegistry

logger = logging.getLogger(__name__)


class ComfyUIError(Exception):
    """Error from ComfyUI API."""
    pass


class ComfyUIClient:
    """
    HTTP client for one ComfyUI instance.
    Handles prompt submission, result retrieval, and image upload/download.
    """

    def __init__(self, node: GPUNode) -> None:
        self.node = node
        self.client_id = str(uuid.uuid4())
        self.http = httpx.AsyncClient(
            base_url=node.base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    @property
    def gpu_id(self) -> str:
        return self.node.id

    async def queue_prompt(self, workflow: dict) -> str:
        """
        Submit a workflow to ComfyUI for execution.
        Returns the prompt_id for tracking.
        """
        payload = {
            "prompt": workflow,
            "client_id": self.client_id,
        }
        resp = await self.http.post("/prompt", json=payload)

        if resp.status_code != 200:
            error_text = resp.text
            raise ComfyUIError(f"Failed to queue prompt on {self.gpu_id}: {resp.status_code} - {error_text}")

        data = resp.json()
        if "error" in data:
            raise ComfyUIError(f"ComfyUI validation error on {self.gpu_id}: {data['error']}")

        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise ComfyUIError(f"No prompt_id returned from {self.gpu_id}")

        logger.info("Queued prompt %s on %s", prompt_id, self.gpu_id)
        return prompt_id

    async def get_queue(self) -> dict:
        """Get current queue status (running + pending)."""
        resp = await self.http.get("/queue")
        resp.raise_for_status()
        return resp.json()

    async def get_history(self, prompt_id: str) -> dict | None:
        """
        Get execution history for a prompt.
        Returns None if not yet complete.
        """
        resp = await self.http.get(f"/history/{prompt_id}")
        resp.raise_for_status()
        data = resp.json()
        return data.get(prompt_id)

    async def get_image(
        self,
        filename: str,
        subfolder: str = "",
        folder_type: str = "output",
    ) -> bytes:
        """Download a generated image from ComfyUI."""
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type,
        }
        resp = await self.http.get("/view", params=params)
        resp.raise_for_status()
        return resp.content

    async def upload_image(
        self,
        image_bytes: bytes,
        filename: str,
        subfolder: str = "",
        image_type: str = "input",
        overwrite: bool = True,
    ) -> dict:
        """
        Upload an image to ComfyUI (for img2img workflows).
        Returns {"name": filename, "subfolder": subfolder, "type": image_type}.
        """
        files = {"image": (filename, image_bytes, "image/png")}
        data = {
            "subfolder": subfolder,
            "type": image_type,
            "overwrite": str(overwrite).lower(),
        }
        resp = await self.http.post("/upload/image", files=files, data=data)
        resp.raise_for_status()
        return resp.json()

    async def poll_until_complete(
        self,
        prompt_id: str,
        timeout: float = 300.0,
        poll_interval: float = 1.0,
    ) -> dict:
        """
        Poll history endpoint until the prompt completes.
        Returns the history entry with outputs.
        Raises TimeoutError if not complete within timeout.
        """
        start = time.monotonic()
        while (time.monotonic() - start) < timeout:
            history = await self.get_history(prompt_id)
            if history and history.get("outputs"):
                return history
            await asyncio.sleep(poll_interval)

        raise TimeoutError(
            f"Prompt {prompt_id} on {self.gpu_id} did not complete within {timeout}s"
        )

    async def get_output_images(self, history: dict) -> list[tuple[str, bytes]]:
        """
        Extract and download all output images from a history entry.
        Returns list of (filename, image_bytes) tuples.
        """
        images = []
        outputs = history.get("outputs", {})
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for img_info in node_output["images"]:
                    filename = img_info["filename"]
                    subfolder = img_info.get("subfolder", "")
                    img_type = img_info.get("type", "output")
                    img_bytes = await self.get_image(filename, subfolder, img_type)
                    images.append((filename, img_bytes))
        return images

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.http.aclose()


class ComfyUIClientPool:
    """
    Manages one ComfyUIClient per GPU node.
    Initialized from the GPURegistry on FastAPI startup.
    """

    def __init__(self) -> None:
        self.clients: dict[str, ComfyUIClient] = {}

    async def initialize(self, registry: GPURegistry) -> None:
        """Create a client for each registered GPU node."""
        for node in registry.get_all_nodes():
            client = ComfyUIClient(node)
            self.clients[node.id] = client
            logger.info("Created ComfyUI client for %s at %s", node.id, node.base_url)

    def get_client(self, gpu_id: str) -> ComfyUIClient:
        """Get client by GPU ID. Raises KeyError if not found."""
        if gpu_id not in self.clients:
            raise KeyError(f"No ComfyUI client for GPU '{gpu_id}'")
        return self.clients[gpu_id]

    def get_all_clients(self) -> list[ComfyUIClient]:
        return list(self.clients.values())

    async def close_all(self) -> None:
        """Close all HTTP clients. Called on shutdown."""
        for client in self.clients.values():
            await client.close()
        self.clients.clear()
        logger.info("Closed all ComfyUI clients")
