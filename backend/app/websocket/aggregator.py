"""
WebSocket Progress Aggregator - multiplexes ComfyUI progress events
to frontend WebSocket connections per session.

Listens to each ComfyUI instance's WebSocket, maps prompt_ids to sessions,
and forwards formatted events to connected frontend clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket
import websockets
from websockets.exceptions import ConnectionClosedError

from ..services.comfyui_client import ComfyUIClientPool

logger = logging.getLogger(__name__)


class ProgressAggregator:
    def __init__(self, pool: ComfyUIClientPool) -> None:
        self.pool = pool
        # prompt_id -> (session_id, generation_id, gpu_id)
        self.prompt_map: dict[str, tuple[str, str, str]] = {}
        # session_id -> list of connected frontend WebSockets
        self.session_connections: dict[str, list[WebSocket]] = {}
        self._listener_tasks: list[asyncio.Task] = []

    def register_prompt(
        self,
        prompt_id: str,
        session_id: str,
        generation_id: str,
        gpu_id: str,
    ) -> None:
        """Map a ComfyUI prompt_id to a session and generation for routing."""
        self.prompt_map[prompt_id] = (session_id, generation_id, gpu_id)

    def unregister_prompt(self, prompt_id: str) -> None:
        """Remove a prompt mapping (after completion)."""
        self.prompt_map.pop(prompt_id, None)

    async def start_listeners(self) -> None:
        """Start background WebSocket listeners for each ComfyUI instance."""
        for client in self.pool.get_all_clients():
            task = asyncio.create_task(
                self._listen_gpu(client.gpu_id, client.node.ws_url, client.client_id),
                name=f"ws-listener-{client.gpu_id}",
            )
            self._listener_tasks.append(task)
            logger.info("Started WS listener for %s", client.gpu_id)

    async def stop_listeners(self) -> None:
        """Cancel all listener tasks."""
        for task in self._listener_tasks:
            task.cancel()
        self._listener_tasks.clear()

    async def _listen_gpu(self, gpu_id: str, ws_url: str, client_id: str) -> None:
        """
        Infinite loop: connect to ComfyUI WS, forward events to frontend.
        Reconnects on disconnect.
        """
        url = f"{ws_url}?clientId={client_id}"
        backoff = 1.0

        while True:
            try:
                async with websockets.connect(url) as ws:
                    logger.info("Connected to ComfyUI WS at %s", url)
                    backoff = 1.0  # reset on successful connect

                    async for raw_msg in ws:
                        try:
                            # Handle both string and bytes messages
                            if isinstance(raw_msg, bytes):
                                msg_str = raw_msg.decode('utf-8')
                            else:
                                msg_str = raw_msg
                            msg = json.loads(msg_str)
                            await self._handle_comfyui_message(gpu_id, msg)
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            pass  # binary preview frames or malformed data, ignore

            except ConnectionClosedError:
                logger.warning("ComfyUI WS disconnected for %s, reconnecting in %.0fs", gpu_id, backoff)
            except (OSError, ConnectionRefusedError):
                logger.debug("Cannot connect to ComfyUI WS for %s, retrying in %.0fs", gpu_id, backoff)
            except asyncio.CancelledError:
                logger.info("WS listener cancelled for %s", gpu_id)
                return
            except Exception:
                logger.exception("Unexpected error in WS listener for %s", gpu_id)

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    async def _handle_comfyui_message(self, gpu_id: str, msg: dict) -> None:
        """Process a message from ComfyUI and forward to the right frontend session."""
        msg_type = msg.get("type")
        data = msg.get("data", {})

        # Try to find which session this belongs to
        # ComfyUI sends prompt_id in some message types
        prompt_id = data.get("prompt_id")

        # For 'executing' messages, prompt_id might be at top level
        if not prompt_id and msg_type == "executing":
            prompt_id = data.get("prompt_id")

        # For 'progress' messages, we need to look it up differently
        # ComfyUI progress messages don't always include prompt_id
        # We track the "currently executing" prompt per GPU
        if not prompt_id:
            # Find any active prompt for this GPU
            for pid, (sid, gid, gpuid) in self.prompt_map.items():
                if gpuid == gpu_id:
                    prompt_id = pid
                    break

        if not prompt_id or prompt_id not in self.prompt_map:
            return

        session_id, generation_id, _ = self.prompt_map[prompt_id]

        # Format for frontend
        frontend_msg: dict[str, Any] | None = None

        if msg_type == "progress":
            value = data.get("value", 0)
            max_val = data.get("max", 1)
            frontend_msg = {
                "type": "generation_progress",
                "generationId": generation_id,
                "gpuId": gpu_id,
                "step": value,
                "totalSteps": max_val,
                "percent": (value / max_val * 100) if max_val > 0 else 0,
            }

        elif msg_type == "executed":
            # Node completed - check if it has image outputs
            output = data.get("output", {})
            if "images" in output:
                frontend_msg = {
                    "type": "generation_node_complete",
                    "generationId": generation_id,
                    "gpuId": gpu_id,
                    "nodeId": data.get("node"),
                    "hasImages": True,
                }

        elif msg_type == "execution_complete":
            frontend_msg = {
                "type": "generation_complete_signal",
                "generationId": generation_id,
                "gpuId": gpu_id,
                "promptId": prompt_id,
            }
            # Don't unregister yet - let the generation handler do it
            # after fetching the images

        elif msg_type == "execution_error":
            frontend_msg = {
                "type": "error",
                "generationId": generation_id,
                "message": data.get("exception_message", "Unknown ComfyUI error"),
            }

        if frontend_msg:
            await self._send_to_session(session_id, frontend_msg)

    async def _send_to_session(self, session_id: str, message: dict) -> None:
        """Send a message to all frontend WebSockets connected to a session."""
        connections = self.session_connections.get(session_id, [])
        if not connections:
            logger.warning("No WebSocket connections for session %s", session_id)
            return

        payload = json.dumps(message)
        dead: list[WebSocket] = []

        logger.debug("Sending %s message to %d connections for session %s",
                    message.get("type"), len(connections), session_id)

        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception as e:
                logger.error("Failed to send WebSocket message: %s", e)
                dead.append(ws)

        # Clean up dead connections
        for ws in dead:
            connections.remove(ws)

    async def connect_frontend(self, session_id: str, ws: WebSocket) -> None:
        """Register a frontend WebSocket for a session."""
        if session_id not in self.session_connections:
            self.session_connections[session_id] = []
        self.session_connections[session_id].append(ws)
        logger.info("Frontend WS connected for session %s", session_id)

    async def disconnect_frontend(self, session_id: str, ws: WebSocket) -> None:
        """Remove a frontend WebSocket."""
        conns = self.session_connections.get(session_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self.session_connections.pop(session_id, None)
        logger.info("Frontend WS disconnected for session %s", session_id)
