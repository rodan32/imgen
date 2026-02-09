export type FlowType = "concept_builder" | "draft_grid" | "explorer";
export type TaskType = "draft" | "standard" | "quality" | "upscale" | "flux" | "flux_quality";
export type ModelFamily = "sd15" | "sdxl" | "pony" | "illustrious" | "flux";
export type FeedbackAction = "select" | "reject" | "more_like_this" | "refine" | "iterate" | "upscale";

export type SessionStage =
  | "idle"
  | "configuring"
  | "generating"
  | "reviewing"
  | "selecting"
  | "iterating"
  | "done";

export interface LoRASpec {
  name: string;
  strengthModel: number;
  strengthClip: number;
}

export interface Session {
  id: string;
  flowType: FlowType;
  createdAt: string;
  currentStage: number;
  config: Record<string, unknown> | null;
}

export interface GenerationResult {
  id: string;
  sessionId: string;
  stage: number;
  prompt: string;
  negativePrompt: string;
  imageUrl: string;
  thumbnailUrl: string;
  gpuId: string | null;
  generationTimeMs: number | null;
  parameters: Record<string, unknown> | null;
  seed: number | null;
  createdAt: string;
  // Frontend-only state
  selected: boolean;
  rejected: boolean;
}

export interface IterationPlan {
  suggestedPrompt: string;
  suggestedNegative: string;
  suggestedParameters: Record<string, unknown>;
  taskType: TaskType;
  modelFamily: ModelFamily;
  useImg2Img: boolean;
  sourceImageId: string | null;
  denoiseStrength: number;
  count: number;
  rationale: string;
}

export interface GPUStatus {
  id: string;
  name: string;
  tier: string;
  vramGb: number;
  healthy: boolean;
  currentQueueLength: number;
  capabilities: string[];
  lastResponseMs: number;
}

export interface BatchProgress {
  batchId: string;
  completed: number;
  total: number;
}

// WebSocket message types
export type WSMessage =
  | GenerationProgressMessage
  | GenerationCompleteMessage
  | BatchProgressMessage
  | BatchCompleteMessage
  | WSErrorMessage;

export interface GenerationProgressMessage {
  type: "generation_progress";
  generationId: string;
  gpuId: string;
  step: number;
  totalSteps: number;
  percent: number;
}

export interface GenerationCompleteMessage {
  type: "generation_complete";
  generationId: string;
  imageUrl: string;
  thumbnailUrl: string;
  seed: number;
  generationTimeMs: number;
  gpuId: string;
}

export interface BatchProgressMessage {
  type: "batch_progress";
  batchId: string;
  completed: number;
  total: number;
  latestResult: {
    generationId: string;
    imageUrl: string;
    thumbnailUrl: string;
    index: number;
  };
}

export interface BatchCompleteMessage {
  type: "batch_complete";
  batchId: string;
  total: number;
  totalTimeMs: number;
}

export interface WSErrorMessage {
  type: "error";
  generationId: string;
  message: string;
}
