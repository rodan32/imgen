"""
Vibes ImGen - FastAPI Backend

Orchestrates image generation across multiple ComfyUI GPU nodes.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .models.database import async_session, init_db
from .routers import generation, gpus, iteration, sessions
from .services.comfyui_client import ComfyUIClientPool
from .services.gpu_registry import GPURegistry
from .services.image_store import ImageStore
from .services.task_router import TaskRouter
from .services.workflow_engine import WorkflowEngine
from .websocket.aggregator import ProgressAggregator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Resolve paths relative to the backend directory
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

# When running in Docker, use absolute paths for mounted volumes
# When running locally, use relative paths
if Path("/app/config/gpus.yaml").exists():
    # Running in Docker
    CONFIG_PATH = Path("/app/config/gpus.yaml")
    DATA_DIR = Path("/app/data")
else:
    # Running locally
    CONFIG_PATH = PROJECT_DIR / "config" / "gpus.yaml"
    DATA_DIR = PROJECT_DIR / "data"

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates" / "workflows"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Vibes ImGen backend...")

    # 1. Load GPU config
    gpu_registry = GPURegistry()
    gpu_registry.load_from_yaml(CONFIG_PATH)
    logger.info("Loaded %d GPU nodes from config", len(gpu_registry.nodes))

    # 2. Initialize ComfyUI client pool
    client_pool = ComfyUIClientPool()
    await client_pool.initialize(gpu_registry)

    # 3. Initialize database
    await init_db()
    logger.info("Database initialized")

    # 4. Load workflow templates
    workflow_engine = WorkflowEngine(TEMPLATES_DIR)
    workflow_engine.load_templates()
    logger.info("Loaded %d workflow templates", len(workflow_engine.templates))

    # 5. Initialize services
    task_router = TaskRouter(gpu_registry)
    image_store = ImageStore(DATA_DIR)

    # 6. Start progress aggregator
    progress_aggregator = ProgressAggregator(client_pool)
    await progress_aggregator.start_listeners()

    # 7. Start GPU health checks
    health_task = gpu_registry.start_background_health_checks(interval=10.0)

    # 8. Store everything in app.state
    app.state.gpu_registry = gpu_registry
    app.state.client_pool = client_pool
    app.state.workflow_engine = workflow_engine
    app.state.task_router = task_router
    app.state.image_store = image_store
    app.state.progress_aggregator = progress_aggregator
    app.state.db_session = async_session  # session factory for background tasks

    # Run initial health check
    await gpu_registry.check_all_health()
    healthy = [n.id for n in gpu_registry.get_healthy_nodes()]
    logger.info("Initial health check: %d/%d GPUs healthy: %s",
                len(healthy), len(gpu_registry.nodes), healthy)

    logger.info("Backend ready!")
    yield

    # Shutdown
    logger.info("Shutting down...")
    gpu_registry.stop_health_checks()
    await progress_aggregator.stop_listeners()
    await client_pool.close_all()


app = FastAPI(title="Vibes ImGen", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(sessions.router)
app.include_router(generation.router)
app.include_router(iteration.router)
app.include_router(gpus.router)


# WebSocket endpoint for frontend session connections
@app.websocket("/ws/session/{session_id}")
async def session_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    aggregator: ProgressAggregator = app.state.progress_aggregator
    await aggregator.connect_frontend(session_id, websocket)
    try:
        while True:
            # Keep alive - frontend may send ping/heartbeat
            await websocket.receive_text()
    except WebSocketDisconnect:
        await aggregator.disconnect_frontend(session_id, websocket)


@app.get("/health")
async def health():
    """Simple health check endpoint."""
    registry: GPURegistry = app.state.gpu_registry
    healthy = len(registry.get_healthy_nodes())
    total = len(registry.nodes)
    return {
        "status": "ok",
        "gpus_healthy": healthy,
        "gpus_total": total,
    }
