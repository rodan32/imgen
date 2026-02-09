"""Pydantic models for API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# --- Enums ---

class FlowType(str, Enum):
    CONCEPT_BUILDER = "concept_builder"
    DRAFT_GRID = "draft_grid"
    EXPLORER = "explorer"


class TaskType(str, Enum):
    DRAFT = "draft"
    STANDARD = "standard"
    QUALITY = "quality"
    UPSCALE = "upscale"
    FLUX = "flux"
    FLUX_QUALITY = "flux_quality"


class FeedbackAction(str, Enum):
    SELECT = "select"
    REJECT = "reject"
    MORE_LIKE_THIS = "more_like_this"
    REFINE = "refine"
    ITERATE = "iterate"
    UPSCALE = "upscale"


class ModelFamily(str, Enum):
    SD15 = "sd15"
    SDXL = "sdxl"
    PONY = "pony"
    ILLUSTRIOUS = "illustrious"
    FLUX = "flux"


# --- Shared Models ---

class LoRASpec(BaseModel):
    name: str
    strength_model: float = 0.8
    strength_clip: float = 0.8


class ConceptFields(BaseModel):
    subject: str = ""
    pose: str = ""
    background: str = ""
    style: str = ""
    mood: str = ""
    lighting: str = ""
    additional: str = ""
    locked_fields: list[str] = Field(default_factory=list)


# --- Request Models ---

class CreateSessionRequest(BaseModel):
    flow_type: FlowType
    initial_config: dict | None = None


class GenerationRequest(BaseModel):
    session_id: str
    prompt: str
    negative_prompt: str = ""
    model_family: ModelFamily = ModelFamily.SDXL
    task_type: TaskType = TaskType.STANDARD
    width: int = 1024
    height: int = 1024
    steps: int = 20
    cfg_scale: float = 7.0
    denoise_strength: float = 1.0
    sampler: str = "euler"
    scheduler: str = "normal"
    seed: int = -1
    source_image_id: str | None = None
    workflow_template: str | None = None
    loras: list[LoRASpec] = Field(default_factory=list)
    checkpoint: str | None = None
    preferred_gpu: str | None = None


class BatchGenerationRequest(BaseModel):
    session_id: str
    prompt: str
    negative_prompt: str = ""
    model_family: ModelFamily = ModelFamily.SD15
    task_type: TaskType = TaskType.DRAFT
    width: int = 512
    height: int = 512
    steps: int = 10
    cfg_scale: float = 7.0
    sampler: str = "euler"
    scheduler: str = "normal"
    count: int = 20
    seed_start: int = -1
    loras: list[LoRASpec] = Field(default_factory=list)
    checkpoint: str | None = None
    explore_mode: bool = False  # Enable checkpoint/LoRA experimentation
    auto_lora: bool = False  # Automatically discover and apply relevant LoRAs


class FeedbackRequest(BaseModel):
    session_id: str
    selected_image_ids: list[str] = Field(default_factory=list)
    rejected_image_ids: list[str] = Field(default_factory=list)
    action: FeedbackAction
    feedback_text: str | None = None
    parameter_adjustments: dict | None = None


class PromptRefineRequest(BaseModel):
    session_id: str
    current_prompt: str
    feedback_text: str
    reference_image_ids: list[str] = Field(default_factory=list)


class ConceptBuilderRequest(BaseModel):
    session_id: str
    concepts: ConceptFields
    model_family: ModelFamily = ModelFamily.SDXL
    count: int = 4
    task_type: TaskType = TaskType.STANDARD


# --- Response Models ---

class SessionResponse(BaseModel):
    id: str
    flow_type: FlowType
    created_at: datetime
    current_stage: int
    config: dict | None = None


class GenerationResponse(BaseModel):
    id: str
    session_id: str
    status: str
    gpu_id: str | None = None
    prompt_id: str | None = None


class BatchGenerationResponse(BaseModel):
    batch_id: str
    session_id: str
    total_count: int
    gpu_assignments: dict[str, int]  # gpu_id -> count


class GenerationResultResponse(BaseModel):
    id: str
    session_id: str
    stage: int
    prompt: str
    negative_prompt: str
    image_url: str
    thumbnail_url: str
    gpu_id: str | None
    generation_time_ms: int | None
    parameters: dict | None
    seed: int | None
    created_at: datetime


class IterationPlanResponse(BaseModel):
    suggested_prompt: str
    suggested_negative: str
    suggested_parameters: dict
    task_type: TaskType
    model_family: ModelFamily
    use_img2img: bool
    source_image_id: str | None = None
    denoise_strength: float
    count: int = 4
    rationale: str


class GPUStatusResponse(BaseModel):
    id: str
    name: str
    tier: str
    vram_gb: int
    healthy: bool
    current_queue_length: int
    capabilities: list[str]
    last_response_ms: float = 0.0


class ModelInfo(BaseModel):
    filename: str
    family: str | None = None
    available_on_gpus: list[str] = Field(default_factory=list)


class LoRAInfo(BaseModel):
    filename: str
    available_on_gpus: list[str] = Field(default_factory=list)
