/**
 * API client - all HTTP calls to the backend.
 * Uses the Vite proxy in dev, direct URL in production.
 */

const BASE = "";  // empty = same origin, proxied by Vite

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`API ${resp.status}: ${text}`);
  }
  return resp.json();
}

// --- Sessions ---

export async function createSession(flowType: string, config?: Record<string, unknown>) {
  return request<{ id: string; flow_type: string; created_at: string; current_stage: number }>(
    "/api/sessions",
    { method: "POST", body: JSON.stringify({ flow_type: flowType, initial_config: config }) }
  );
}

export async function getSession(id: string) {
  return request<{ id: string; flow_type: string; current_stage: number }>(`/api/sessions/${id}`);
}

export async function getSessionGenerations(sessionId: string, stage?: number) {
  const query = stage !== undefined ? `?stage=${stage}` : "";
  return request<Array<{
    id: string; session_id: string; stage: number; prompt: string;
    negative_prompt: string; image_url: string; thumbnail_url: string;
    gpu_id: string; generation_time_ms: number; seed: number; created_at: string;
  }>>(`/api/sessions/${sessionId}/generations${query}`);
}

export async function deleteSession(id: string) {
  return request<{ status: string }>(`/api/sessions/${id}`, { method: "DELETE" });
}

// --- Generation ---

export interface GenerateParams {
  session_id: string;
  prompt: string;
  negative_prompt?: string;
  model_family?: string;
  task_type?: string;
  width?: number;
  height?: number;
  steps?: number;
  cfg_scale?: number;
  denoise_strength?: number;
  sampler?: string;
  scheduler?: string;
  seed?: number;
  source_image_id?: string;
  workflow_template?: string;
  loras?: Array<{ name: string; strength_model: number; strength_clip: number }>;
  checkpoint?: string;
  preferred_gpu?: string;
}

export async function generateImage(params: GenerateParams) {
  return request<{ id: string; session_id: string; status: string; gpu_id: string }>(
    "/api/generate",
    { method: "POST", body: JSON.stringify(params) }
  );
}

export interface BatchGenerateParams {
  session_id: string;
  prompt: string;
  negative_prompt?: string;
  explore_mode?: boolean;
  auto_lora?: boolean;
  model_family?: string;
  task_type?: string;
  width?: number;
  height?: number;
  steps?: number;
  cfg_scale?: number;
  sampler?: string;
  scheduler?: string;
  count?: number;
  seed_start?: number;
  loras?: Array<{ name: string; strength_model: number; strength_clip: number }>;
  checkpoint?: string;
}

export async function generateBatch(params: BatchGenerateParams) {
  return request<{
    batch_id: string; session_id: string; total_count: number;
    gpu_assignments: Record<string, number>;
  }>("/api/generate/batch", { method: "POST", body: JSON.stringify(params) });
}

export async function getGeneration(id: string) {
  return request<{
    id: string; session_id: string; stage: number; prompt: string;
    image_url: string; thumbnail_url: string; seed: number;
  }>(`/api/generate/${id}`);
}

// --- Iteration ---

export interface FeedbackParams {
  session_id: string;
  selected_image_ids?: string[];
  rejected_image_ids?: string[];
  action: string;
  feedback_text?: string;
  parameter_adjustments?: Record<string, unknown>;
}

export async function submitFeedback(params: FeedbackParams) {
  return request<{
    suggested_prompt: string; suggested_negative: string;
    suggested_parameters: Record<string, unknown>;
    task_type: string; model_family: string; use_img2img: boolean;
    source_image_id: string | null; denoise_strength: number;
    count: number; rationale: string;
  }>("/api/iterate", { method: "POST", body: JSON.stringify(params) });
}

export async function autoIterate(params: FeedbackParams) {
  return request<{ id: string; status: string }>("/api/iterate/auto", {
    method: "POST", body: JSON.stringify(params),
  });
}

export async function refinePrompt(params: {
  session_id: string; current_prompt: string; feedback_text: string;
  reference_image_ids?: string[];
}) {
  return request<{ refined_prompt: string; rationale: string }>(
    "/api/iterate/refine-prompt",
    { method: "POST", body: JSON.stringify(params) }
  );
}

export async function rejectAll(params: {
  session_id: string; stage: number; feedback_text?: string;
  rejected_image_ids: string[];
}) {
  return request<{ recorded: boolean; rationale: string }>(
    "/api/iterate/reject-all",
    { method: "POST", body: JSON.stringify(params) }
  );
}

// --- GPUs ---

export async function getGPUs() {
  return request<Array<{
    id: string; name: string; tier: string; vram_gb: number;
    healthy: boolean; current_queue_length: number;
    capabilities: string[]; last_response_ms: number;
  }>>("/api/gpus");
}

// --- Health ---

export async function getHealth() {
  return request<{ status: string; gpus_healthy: number; gpus_total: number }>("/health");
}
