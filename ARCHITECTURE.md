# Vibes ImGen — Architecture Deep Dive

## System Overview

Vibes ImGen is a **distributed image generation orchestrator** that coordinates 4 GPUs across multiple machines to enable iterative, progressive image refinement workflows. The system uses a hub-and-spoke architecture where a central FastAPI backend orchestrates work across multiple ComfyUI instances.

---

## Network Topology

```
                         ┌─────────────────────────┐
                         │   Browser               │
                         │   React 19 + Zustand    │
                         └────────┬────────────────┘
                                  │ HTTP + WebSocket
                                  │
                         ┌────────▼────────────────┐
                         │   Backend VM (Proxmox)  │
                         │   FastAPI :8001         │
                         │   SQLite DB             │
                         │   NAS mount (images)    │
                         └────────┬────────────────┘
                                  │
              ┌───────────────────┼───────────────────┬───────────────┐
              │                   │                   │               │
              │ HTTP+WS           │ HTTP+WS           │ HTTP+WS       │ HTTP+WS
              │ :8188             │ :8188             │ :8188         │ :8188
              │                   │                   │               │
    ┌─────────▼────────┐  ┌──────▼───────┐  ┌────────▼──────┐  ┌────▼─────────┐
    │ Machine A        │  │ Machine B    │  │ Machine C     │  │ Machine D    │
    │ RTX 5060 Ti 16GB │  │ RTX 4060 Ti  │  │ RTX 3060      │  │ RTX 3050 Ti  │
    │ ComfyUI (premium)│  │ ComfyUI      │  │ ComfyUI       │  │ ComfyUI      │
    │ 192.168.0.20     │  │ (quality)    │  │ (standard)    │  │ (draft)      │
    │ ✓ INSTALLED      │  │ TBD          │  │ TBD           │  │ TBD          │
    └──────────────────┘  └──────────────┘  └───────────────┘  └──────────────┘

    ┌──────────────────────────────────────────────────────────────────────────┐
    │ NAS (Synology) — 10.0.0.5                                                │
    │ - Model repo (checkpoints, LoRAs, ControlNet)                            │
    │ - Generated image storage                                                 │
    │ - Mounted on Backend VM at /mnt/nas                                       │
    └──────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────────────────────────────┐
    │ Ollama (future) — localhost:11434 or separate VM                          │
    │ - hermes3:8b (feedback interpreter)                                       │
    │ - phi4:14b (prompt engineer)                                              │
    │ - minicpm-v (vision analyzer)                                             │
    └──────────────────────────────────────────────────────────────────────────┘
```

---

## Backend Architecture

### Service Layer Hierarchy

```
FastAPI App (app/main.py)
    │
    ├─► Lifespan Manager (startup/shutdown)
    │   ├─► Load GPU Registry from gpus.yaml
    │   ├─► Initialize ComfyUI Client Pool (one client per GPU)
    │   ├─► Initialize Database (SQLAlchemy async)
    │   ├─► Load Workflow Templates from templates/workflows/*.json
    │   ├─► Start Progress Aggregator (WebSocket multiplexer)
    │   └─► Start GPU Health Checks (background task, 10s interval)
    │
    ├─► API Routers
    │   ├─► /api/sessions (create, list, get session)
    │   ├─► /api/generate (single + batch generation)
    │   └─► /api/gpus (status dashboard)
    │
    ├─► WebSocket Endpoint
    │   └─► /ws/session/{session_id} (per-session progress stream)
    │
    └─► Core Services (stored in app.state)
        ├─► GPURegistry — GPU config, health checks, capability queries
        ├─► ComfyUIClientPool — HTTP+WS clients (one per GPU node)
        ├─► TaskRouter — Tier-based routing with overflow handling
        ├─► WorkflowEngine — Template loading, param substitution, LoRA injection
        ├─► ImageStore — Filesystem storage + thumbnail generation
        └─► ProgressAggregator — WS multiplexer (ComfyUI → frontend)
```

### Generation Pipeline Flow

```
1. Frontend: User clicks "Generate"
   ↓
2. API Request: POST /api/generate/batch
   {
     session_id: "uuid",
     prompt: "1girl, sitting...",
     model_family: "sd15",
     task_type: "draft",
     count: 20,
     width: 512, height: 512, steps: 10
   }
   ↓
3. TaskRouter.route(task_type="draft", model_family="sd15")
   → Query GPURegistry for capable + healthy nodes
   → Filter nodes by capability (needs "sd15")
   → Sort by current queue length (prefer idle GPUs)
   → For batch work: Return ALL capable nodes (not just one)
   ↓
4. WorkflowEngine.select_template(model_family="sd15", is_img2img=False)
   → Returns "sd15_txt2img"
   ↓
5. WorkflowEngine.build_workflow("sd15_txt2img", params={...})
   → Load template JSON: {"1": {"class_type": "CheckpointLoader", ...}, ...}
   → Substitute {{prompt}} → "1girl, sitting..."
   → Substitute {{checkpoint}} → "v1-5-pruned-emaonly.safetensors"
   → Substitute {{steps}}, {{cfg_scale}}, {{seed}}, etc.
   → Return parameterized workflow dict
   ↓
6. Create GenerationORM records (one per image, status="queued")
   → Save to SQLite DB
   ↓
7. Batch Distribution: For count=20, capable_nodes=[gpu-draft, gpu-standard, gpu-quality, gpu-premium]
   → Split 20 images across 4 GPUs: [5, 5, 5, 5]
   → (In practice, faster GPUs finish first and grab more work)
   ↓
8. For each GPU node:
   asyncio.create_task(_generate_one(gpu_node, workflow, generation_id))
       ↓
       ComfyUIClientPool.get_client(gpu_id)
       → Returns ComfyUIClient instance (reused HTTP+WS client)
       ↓
       ComfyUIClient.submit_prompt(workflow)
       → POST http://192.168.x.x:8188/prompt
       → Response: {"prompt_id": "abc123", "number": 42}
       ↓
       ProgressAggregator.listen_to_prompt(gpu_id, prompt_id, session_id, generation_id)
       → Connects to ws://192.168.x.x:8188/ws?clientId={client_id}
       → Receives: {"type": "progress", "data": {"value": 5, "max": 10}}
       → Forwards to frontend WS: {session_id}/ws → {"type": "progress", "generation_id": "...", "current": 5, "total": 10}
       ↓
       ComfyUIClient.poll_until_complete(prompt_id, timeout=300s)
       → Poll GET http://192.168.x.x:8188/history/{prompt_id} every 1s
       → When status="complete": Extract output image filename
       → GET http://192.168.x.x:8188/view?filename={output_filename}
       → Save image bytes to data/images/{session_id}/{generation_id}.png
       ↓
       ImageStore.save_generation(session_id, generation_id, image_bytes)
       → Write image to data/images/{session_id}/{generation_id}.png
       → Generate thumbnail (256x256) → data/images/{session_id}/{generation_id}_thumb.jpg
       → Return URLs: /api/images/{session_id}/{generation_id}
       ↓
       Update GenerationORM: status="complete", image_url="...", thumbnail_url="..."
       ↓
       Send WS message to frontend:
       {"type": "complete", "generation_id": "...", "image_url": "...", "thumbnail_url": "..."}
   ↓
9. Frontend receives WS messages
   → generationStore.addGeneration({id, imageUrl, thumbnailUrl, ...})
   → React re-renders ImageGrid with new images
```

---

## Frontend Architecture

### State Management (Zustand)

```
sessionStore
├─ currentSession: Session | null
│   ├─ id: string
│   ├─ flowType: "draft_grid" | "concept_builder" | "explorer"
│   ├─ createdAt: string
│   └─ currentStage: number (iteration round)
├─ sessionStage: "idle" | "configuring" | "generating" | "reviewing" | "selecting" | "iterating" | "done"
├─ iterationRound: number (0-indexed, maps to funnel stage)
├─ createSession(flowType) → POST /api/sessions
├─ loadSession(id) → GET /api/sessions/{id}
├─ setStage(stage) → Update sessionStage
├─ advanceIteration() → iterationRound++
└─ reset() → Clear session, go back to idle

generationStore
├─ generations: Map<generationId, GenerationResult>
│   ├─ id, sessionId, stage, prompt, imageUrl, thumbnailUrl, gpuId
│   ├─ selected: boolean (frontend-only)
│   └─ rejected: boolean (frontend-only)
├─ activeBatch: { batchId: string, completed: number, total: number } | null
├─ addGeneration(gen) → Add to map, trigger re-render
├─ updateProgress(batchId, completed) → Update activeBatch.completed
├─ toggleSelection(genId) → Flip selected state
├─ toggleRejection(genId) → Flip rejected state
├─ getStageGenerations(stage) → Filter generations by stage
├─ getSelectedIds() → Array of selected generation IDs
├─ clearSelections() → Reset all selected/rejected flags
├─ setBatch(batchId, total) → Initialize activeBatch
└─ reset() → Clear all generations

gpuStore
├─ nodes: GPUStatus[]
│   ├─ id, name, tier, vramGb, healthy, currentQueueLength, capabilities
│   └─ lastResponseMs
├─ fetchStatus() → GET /api/gpus
└─ startPolling(interval=5000) → setInterval(fetchStatus)
```

### Component Hierarchy

```
App.tsx (top-level)
    │
    ├─► GPUStatusBar (sticky top)
    │   ├─ Displays: gpu-premium: ✓ (0 queued), gpu-quality: ✗ (unreachable)
    │   └─ Polls gpuStore every 5s
    │
    ├─► FlowSelector (if sessionStage === "idle")
    │   ├─ Draft Grid button → createSession("draft_grid")
    │   ├─ Concept Builder button → createSession("concept_builder")
    │   └─ Explorer button → createSession("explorer")
    │
    └─► Active Flow (if session exists)
        │
        ├─► DraftGridFlow (if flowType === "draft_grid") ✅ IMPLEMENTED
        │   ├─► PromptEditor (prompt + negative prompt textareas)
        │   ├─► Stage Breadcrumb (Drafts → Refined → Polished → Final)
        │   ├─► ImageGrid (all generations for current stage)
        │   │   └─► ImageCard (image, select/reject buttons, metadata tooltip)
        │   ├─► FeedbackBar (bottom sticky)
        │   │   ├─ "Generate" button (if no images yet)
        │   │   ├─ "Continue with Selected" (if selections exist)
        │   │   └─ Progress bar (during generation)
        │   └─► useWebSocket(session.id) hook
        │       ├─ Connects to /ws/session/{session.id}
        │       ├─ Listens for {"type": "progress", ...}
        │       ├─ Listens for {"type": "complete", ...}
        │       └─ Updates generationStore on messages
        │
        ├─► ConceptBuilderFlow (if flowType === "concept_builder") 🔴 PLACEHOLDER
        │   └─ "Coming soon" message
        │
        └─► ExplorerFlow (if flowType === "explorer") 🔴 PLACEHOLDER
            └─ "Coming soon" message
```

### WebSocket Message Handling

```typescript
useWebSocket(sessionId: string | null) {
  useEffect(() => {
    if (!sessionId) return;

    const ws = new WebSocket(`ws://localhost:8001/ws/session/${sessionId}`);

    ws.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data);

      if (msg.type === "progress") {
        // Update batch progress bar
        generationStore.updateProgress(msg.batch_id, msg.completed);
      }

      if (msg.type === "complete") {
        // Add completed generation to store
        generationStore.addGeneration({
          id: msg.generation_id,
          imageUrl: msg.image_url,
          thumbnailUrl: msg.thumbnail_url,
          sessionId,
          stage: currentStage,
          // ... other fields
        });
      }
    };

    return () => ws.close();
  }, [sessionId]);
}
```

---

## GPU Routing Logic

### Tier-Based Routing with Overflow

```python
async def route(self, task_type: TaskType, preferred_gpu: str | None, model_family: str | None) -> GPUNode:
    # 1. Check preferred GPU first
    if preferred_gpu:
        node = self.registry.get_node(preferred_gpu)
        if node and node.healthy and self._is_capable(node, task_type, model_family):
            return node

    # 2. Get all capable, healthy nodes
    required_cap = model_family or CAPABILITY_REQUIREMENTS[task_type]
    candidates = self.registry.get_capable_nodes(required_cap)

    if not candidates:
        raise NoAvailableGPUError(f"No GPU can handle {task_type} with {required_cap}")

    # 3. Sort by tier preference (for quality work) + queue length (prefer idle)
    if task_type in (TaskType.QUALITY, TaskType.FLUX_QUALITY, TaskType.UPSCALE):
        # Prefer higher tiers for quality work
        candidates.sort(key=lambda n: (TIER_ORDER.index(n.tier), n.current_queue_length))
    else:
        # Prefer lower tiers for draft/standard (save premium GPU for quality)
        candidates.sort(key=lambda n: (-TIER_ORDER.index(n.tier), n.current_queue_length))

    # 4. Check for overflow — if best candidate is overloaded, try next tier
    best = candidates[0]
    if best.current_queue_length >= OVERFLOW_THRESHOLD:
        for candidate in candidates[1:]:
            if candidate.current_queue_length < OVERFLOW_THRESHOLD:
                logger.info("Best tier overloaded, routing to %s", candidate.id)
                return candidate

    # 5. Return best candidate (even if overloaded — ComfyUI will queue internally)
    return best
```

### Batch Distribution

For batch operations (e.g., 20 drafts):
1. Get ALL capable + healthy nodes
2. Divide count evenly: `count_per_gpu = total // len(nodes)`
3. Handle remainder: `remainder = total % len(nodes)` → assign +1 to first N nodes
4. Launch `asyncio.create_task(_generate_one(...))` for each image
5. Faster GPUs finish first → effective dynamic load balancing

**Example**: 20 drafts across 4 GPUs (all capable of SD1.5):
- gpu-draft: 5 images (512x512, 10 steps, 3050 Ti → ~1.5s each → 7.5s total)
- gpu-standard: 5 images (512x512, 10 steps, 3060 → ~1s each → 5s total)
- gpu-quality: 5 images (512x512, 10 steps, 4060 Ti → ~0.8s each → 4s total)
- gpu-premium: 5 images (512x512, 10 steps, 5060 Ti → ~0.5s each → 2.5s total)

Total wall-clock time: ~7.5s (limited by slowest GPU)

---

## Workflow Template System

### Template Structure

ComfyUI API format JSON with placeholder substitution:

```json
{
  "1": {
    "class_type": "CheckpointLoader",
    "inputs": {
      "ckpt_name": "{{checkpoint}}"
    }
  },
  "2": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "{{prompt}}",
      "clip": ["1", 1]
    }
  },
  "3": {
    "class_type": "CLIPTextEncode",
    "inputs": {
      "text": "{{negative_prompt}}",
      "clip": ["1", 1]
    }
  },
  "4": {
    "class_type": "KSampler",
    "inputs": {
      "seed": {{seed}},
      "steps": {{steps}},
      "cfg": {{cfg_scale}},
      "sampler_name": "{{sampler}}",
      "scheduler": "{{scheduler}}",
      "denoise": {{denoise_strength}},
      "model": ["1", 0],
      "positive": ["2", 0],
      "negative": ["3", 0],
      "latent_image": ["5", 0]
    }
  },
  "5": {
    "class_type": "EmptyLatentImage",
    "inputs": {
      "width": {{width}},
      "height": {{height}},
      "batch_size": 1
    }
  },
  "6": {
    "class_type": "VAEDecode",
    "inputs": {
      "samples": ["4", 0],
      "vae": ["1", 2]
    }
  },
  "7": {
    "class_type": "SaveImage",
    "inputs": {
      "filename_prefix": "vibes_",
      "images": ["6", 0]
    }
  }
}
```

### Substitution Process

```python
def build_workflow(self, template_name: str, params: dict) -> dict:
    template = copy.deepcopy(self.templates[template_name])
    json_str = json.dumps(template)

    # Replace {{variable}} with actual values
    for key, value in params.items():
        if isinstance(value, str):
            json_str = json_str.replace(f'"{{{{{key}}}}}"', f'"{value}"')
        else:
            json_str = json_str.replace(f'{{{{{key}}}}}', str(value))

    return json.loads(json_str)
```

### Dynamic LoRA Injection

For `sdxl_with_lora.json` template:
1. Start with base template (CheckpointLoader → CLIPTextEncode → KSampler)
2. For each LoRA in `params['loras']`:
   - Insert new node: `LoraLoader` with `lora_name`, `strength_model`, `strength_clip`
   - Rewire connections: Previous model output → LoraLoader → Next stage
3. Result: Checkpoint → LoRA1 → LoRA2 → LoRA3 → Sampler

```python
def inject_loras(self, workflow: dict, loras: list[LoRASpec]) -> dict:
    # Implementation injects LoraLoader nodes between CheckpointLoader and KSampler
    # Rewires ["1", 0] connections to chain through LoRA nodes
    # Returns modified workflow dict
    pass
```

---

## Database Schema

### SQLAlchemy ORM Models

```python
class SessionORM(Base):
    __tablename__ = "sessions"

    id: str (UUID, primary key)
    flow_type: str ("draft_grid", "concept_builder", "explorer")
    current_stage: int (iteration round)
    config: JSON (flow-specific settings, concept fields, etc.)
    created_at: datetime
    updated_at: datetime

    generations: relationship("GenerationORM", back_populates="session")


class GenerationORM(Base):
    __tablename__ = "generations"

    id: str (UUID, primary key)
    session_id: str (ForeignKey → sessions.id)
    stage: int (which funnel stage / iteration round)
    prompt: str
    negative_prompt: str
    model_family: str ("sd15", "sdxl", "flux")
    checkpoint: str (filename)
    task_type: str ("draft", "standard", "quality", "upscale")
    parameters: JSON (width, height, steps, cfg_scale, denoise_strength, sampler, scheduler)
    loras: JSON (list of LoRASpec dicts)
    gpu_id: str (which GPU rendered this)
    seed: int
    width: int
    height: int
    steps: int
    cfg_scale: float
    denoise_strength: float
    status: str ("queued", "generating", "complete", "failed")
    image_path: str (relative path in data/images/)
    thumbnail_path: str (relative path for thumbnail)
    generation_time_ms: int (render duration)
    error_message: str (if status="failed")
    created_at: datetime
    completed_at: datetime

    session: relationship("SessionORM", back_populates="generations")
```

### Async Session Factory

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

engine = create_async_engine("sqlite+aiosqlite:///./data/vibes.db", echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
```

---

## WebSocket Progress Streaming

### Backend: ProgressAggregator

```python
class ProgressAggregator:
    """Multiplexes ComfyUI WS progress → per-session frontend WS."""

    def __init__(self, client_pool: ComfyUIClientPool):
        self.client_pool = client_pool
        self.frontend_connections: dict[str, list[WebSocket]] = {}  # session_id → [websockets]
        self.tasks: list[asyncio.Task] = []

    async def start_listeners(self):
        """Start listening to all ComfyUI WS endpoints."""
        for gpu_id in self.client_pool.clients.keys():
            task = asyncio.create_task(self._listen_to_gpu(gpu_id))
            self.tasks.append(task)

    async def _listen_to_gpu(self, gpu_id: str):
        """Connect to ComfyUI WS, forward progress messages to frontend."""
        client = self.client_pool.get_client(gpu_id)
        ws_url = f"ws://{client.host}:{client.port}/ws?clientId={client.client_id}"

        async with websockets.connect(ws_url) as ws:
            async for message in ws:
                data = json.loads(message)

                if data["type"] == "progress":
                    # Extract session_id from active_jobs tracking (not shown here)
                    session_id = self._get_session_for_prompt(data["data"]["prompt_id"])
                    await self._broadcast_to_session(session_id, {
                        "type": "progress",
                        "generation_id": data["data"]["node"],
                        "current": data["data"]["value"],
                        "total": data["data"]["max"],
                    })

                if data["type"] == "executed":
                    # Image complete, send URL to frontend
                    session_id = self._get_session_for_prompt(data["data"]["prompt_id"])
                    await self._broadcast_to_session(session_id, {
                        "type": "complete",
                        "generation_id": data["data"]["node"],
                        "image_url": f"/api/images/{session_id}/{data['data']['node']}",
                        "thumbnail_url": f"/api/images/{session_id}/{data['data']['node']}/thumb",
                    })

    async def connect_frontend(self, session_id: str, websocket: WebSocket):
        """Register frontend WS connection for a session."""
        if session_id not in self.frontend_connections:
            self.frontend_connections[session_id] = []
        self.frontend_connections[session_id].append(websocket)

    async def _broadcast_to_session(self, session_id: str, message: dict):
        """Send message to all frontend connections for a session."""
        if session_id not in self.frontend_connections:
            return
        dead_connections = []
        for ws in self.frontend_connections[session_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.append(ws)
        # Clean up dead connections
        for ws in dead_connections:
            self.frontend_connections[session_id].remove(ws)
```

### Frontend: useWebSocket Hook

```typescript
export function useWebSocket(sessionId: string | null) {
  const addGeneration = useGenerationStore((s) => s.addGeneration);
  const updateProgress = useGenerationStore((s) => s.updateProgress);

  useEffect(() => {
    if (!sessionId) return;

    const ws = new WebSocket(`ws://localhost:8001/ws/session/${sessionId}`);

    ws.onopen = () => console.log(`WS connected: ${sessionId}`);

    ws.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data);

      if (msg.type === "progress") {
        updateProgress(msg.batch_id, msg.completed);
      } else if (msg.type === "complete") {
        addGeneration({
          id: msg.generation_id,
          sessionId,
          imageUrl: msg.image_url,
          thumbnailUrl: msg.thumbnail_url,
          stage: currentStage,
          selected: false,
          rejected: false,
          // ... other fields
        });
      }
    };

    ws.onerror = (error) => console.error("WS error:", error);
    ws.onclose = () => console.log("WS closed");

    // Heartbeat (keep-alive)
    const heartbeat = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 30000);

    return () => {
      clearInterval(heartbeat);
      ws.close();
    };
  }, [sessionId, addGeneration, updateProgress]);
}
```

---

## Future: 3-Stage LLM Prompt Refinement Pipeline (NOT YET IMPLEMENTED)

### Stage 1: Feedback Interpreter

```python
# backend/app/services/feedback_interpreter.py
from ollama import AsyncClient

class FeedbackInterpreter:
    """Parse user feedback into structured change instructions."""

    def __init__(self, ollama_host: str = "http://localhost:11434"):
        self.client = AsyncClient(host=ollama_host)
        self.model = "hermes3:8b"

    async def interpret(self, feedback_text: str, selected_ids: list[str], rejected_ids: list[str], intent_document: dict) -> dict:
        """
        Returns structured changes:
        {
          "keep": ["token1", "token2"],
          "remove": ["token3"],
          "add": ["token4", "token5"],
          "modify": {"field": "new_value"},
          "emphasis_up": ["concept"],
          "emphasis_down": ["concept"]
        }
        """
        system_prompt = FEEDBACK_INTERPRETER_SYSTEM_PROMPT  # Detailed prompt in source file
        user_message = f"""
        User feedback: {feedback_text}
        Selected images: {len(selected_ids)} (IDs: {selected_ids[:3]}...)
        Rejected images: {len(rejected_ids)} (IDs: {rejected_ids[:3]}...)
        Session intent history: {json.dumps(intent_document, indent=2)}

        Extract structured changes as JSON.
        """

        response = await self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            format="json",
        )

        return json.loads(response.message.content)
```

### Stage 2: Prompt Engineer

```python
# backend/app/services/prompt_engineer.py
class PromptEngineer:
    """Apply structured changes to produce SD/Flux-optimized prompts."""

    def __init__(self, ollama_host: str = "http://localhost:11434"):
        self.client = AsyncClient(host=ollama_host)
        self.model = "phi4:14b"

    async def refine(self, current_prompt: str, changes: dict, model_family: str) -> dict:
        """
        Returns:
        {
          "prompt": "refined prompt text",
          "negative_prompt": "refined negative prompt",
          "rationale": "what was changed and why"
        }
        """
        system_prompt = PROMPT_ENGINEER_SYSTEM_PROMPT[model_family]  # Different prompts per model
        user_message = f"""
        Current prompt: {current_prompt}
        Structured changes: {json.dumps(changes, indent=2)}

        Apply changes mechanically:
        - Preserve all tokens in "keep" list exactly
        - Remove all tokens in "remove" list
        - Insert tokens from "add" list in natural positions
        - Modify fields as specified
        - Adjust emphasis with () for emphasis_up, lowercase for emphasis_down

        Return JSON with "prompt", "negative_prompt", "rationale".
        """

        response = await self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            format="json",
        )

        return json.loads(response.message.content)
```

### Stage 3: Vision Analyzer

```python
# backend/app/services/vision_analyzer.py
class VisionAnalyzer:
    """Analyze images to inform prompt refinement."""

    def __init__(self, ollama_host: str = "http://localhost:11434"):
        self.client = AsyncClient(host=ollama_host)
        self.model = "minicpm-v"

    async def analyze_selection(self, image_bytes: bytes, question: str) -> str:
        """
        Question examples:
        - "Describe the composition, style, and mood of this image."
        - "What makes this image different from typical SD outputs?"
        - "Focus on colors, lighting, and atmosphere — be specific."
        """
        # Encode image as base64
        import base64
        image_b64 = base64.b64encode(image_bytes).decode()

        response = await self.client.chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": question,
                    "images": [image_b64],
                }
            ],
        )

        return response.message.content

    async def compare_selections(self, selected_images: list[bytes], rejected_images: list[bytes]) -> dict:
        """
        A/B comparison: What's different between selected vs rejected?
        Returns:
        {
          "selected_traits": ["dark moody palette", "dramatic lighting"],
          "rejected_traits": ["bright flat lighting", "oversaturated"],
          "key_differences": "Selected images have stronger contrast and more atmospheric depth"
        }
        """
        # Analyze first selected + first rejected, compare descriptions
        # (Full implementation would analyze multiple images per category)
        pass
```

### Integration in Iteration Router

```python
# backend/app/routers/iteration.py (future)
@router.post("/api/iterate/refine-prompt", response_model=IterationPlanResponse)
async def refine_prompt(req: IterationRequest, request: Request):
    """
    User submits feedback text + selected/rejected image IDs.
    Returns refined prompt + iteration plan.
    """
    feedback_interpreter = request.app.state.feedback_interpreter
    prompt_engineer = request.app.state.prompt_engineer
    vision_analyzer = request.app.state.vision_analyzer

    # Load session intent document (accumulated feedback history)
    intent_document = await get_intent_document(req.session_id)

    # Stage 1: Parse feedback into structured changes
    changes = await feedback_interpreter.interpret(
        req.feedback_text,
        req.selected_image_ids,
        req.rejected_image_ids,
        intent_document,
    )

    # Stage 3 (optional): If user selected images, analyze them
    if req.selected_image_ids:
        selected_bytes = await load_image_bytes(req.selected_image_ids[0])
        vision_description = await vision_analyzer.analyze_selection(
            selected_bytes,
            "Describe the composition, style, mood, and colors in detail.",
        )
        changes["vision_context"] = vision_description

    # Stage 2: Apply changes to produce refined prompt
    refined = await prompt_engineer.refine(
        current_prompt=req.current_prompt,
        changes=changes,
        model_family=req.model_family,
    )

    # Update intent document with new feedback
    await update_intent_document(req.session_id, {
        "feedback": req.feedback_text,
        "changes": changes,
        "refined_prompt": refined["prompt"],
    })

    # Build iteration plan
    plan = IterationPlan(
        suggested_prompt=refined["prompt"],
        suggested_negative=refined["negative_prompt"],
        task_type=determine_task_type(req.session_id),
        model_family=req.model_family,
        count=8,  # Next funnel stage
        rationale=refined["rationale"],
    )

    return plan
```

---

## Configuration Files

### `config/gpus.yaml`

```yaml
nodes:
  - id: gpu-premium
    name: "RTX 5060 Ti"
    vram_gb: 16
    tier: premium
    host: "192.168.0.20"
    port: 8188
    capabilities:
      - sd15
      - sdxl
      - pony
      - illustrious
      - flux
      - flux_fp8
      - upscale
      - controlnet
      - ipadapter
      - faceid
    max_resolution: 1536
    max_batch: 4

  - id: gpu-quality
    name: "RTX 4060 Ti"
    vram_gb: 8
    tier: quality
    host: "192.168.1.101"
    port: 8188
    capabilities: [sd15, sdxl, pony, illustrious]
    max_resolution: 1024
    max_batch: 4

  - id: gpu-standard
    name: "RTX 3060"
    vram_gb: 12
    tier: standard
    host: "192.168.1.102"
    port: 8188
    capabilities: [sd15, sdxl, pony, illustrious]
    max_resolution: 1024
    max_batch: 2

  - id: gpu-draft
    name: "RTX 3050 Ti"
    vram_gb: 4
    tier: draft
    host: "192.168.1.103"
    port: 8188
    capabilities: [sd15]
    max_resolution: 512
    max_batch: 1
```

### `backend/app/templates/workflows/manifest.yaml`

```yaml
templates:
  - name: sd15_txt2img
    description: "SD 1.5 text-to-image (fast drafts)"
    model_families: [sd15]
    supports_img2img: false
    default_params:
      steps: 10
      cfg_scale: 7.0
      sampler: euler
      scheduler: normal
      width: 512
      height: 512

  - name: sdxl_txt2img
    description: "SDXL text-to-image"
    model_families: [sdxl, pony, illustrious]
    supports_img2img: false
    default_params:
      steps: 25
      cfg_scale: 7.0
      sampler: euler
      scheduler: normal
      width: 1024
      height: 1024

  - name: sdxl_with_lora
    description: "SDXL with LoRA support"
    model_families: [sdxl, pony, illustrious]
    supports_img2img: false
    supports_lora: true
    max_loras: 3
    default_params:
      steps: 25
      cfg_scale: 7.0
      sampler: euler
      scheduler: normal

  - name: flux_txt2img
    description: "Flux text-to-image"
    model_families: [flux]
    supports_img2img: false
    default_params:
      steps: 20
      cfg_scale: 1.0
      sampler: euler
      scheduler: simple

  - name: upscale_esrgan
    description: "ESRGAN 4x upscale"
    model_families: [any]
    supports_img2img: true
    default_params:
      upscale_model: "4x-UltraSharp.pth"
```

---

## Performance Characteristics

### Expected Generation Times (per image)

| GPU | Task | Model | Resolution | Steps | Time |
|-----|------|-------|-----------|-------|------|
| 3050 Ti (4GB) | Draft | SD1.5 | 512x512 | 10 | ~1.5s |
| 3060 (12GB) | Draft | SD1.5 | 512x512 | 10 | ~1s |
| 3060 (12GB) | Standard | SDXL | 1024x1024 | 25 | ~10s |
| 4060 Ti (8GB) | Quality | SDXL | 1024x1024 | 35 | ~12s |
| 5060 Ti (16GB) | Premium | SDXL | 1024x1024 | 50 | ~15s |
| 5060 Ti (16GB) | Flux | Flux fp8 | 1024x1024 | 20 | ~8s |
| 5060 Ti (16GB) | Upscale | ESRGAN 4x | 1024→4096 | N/A | ~2s |

### Draft Grid Flow (20 → 8 → 3 → 1)

**Stage 1: Drafts** (20 images, SD1.5, 512x512, 10 steps)
- Distribution: 5 per GPU across 4 GPUs
- Wall-clock time: ~7.5s (limited by slowest GPU, the 3050 Ti)

**Stage 2: Refined** (8 images, SDXL, 1024x1024, 25 steps)
- Distribution: 2-3 per GPU (3060, 4060 Ti, 5060 Ti)
- Wall-clock time: ~30s (3 images on 3060 @ 10s each)

**Stage 3: Polished** (3 images, SDXL, 1024x1024, 35 steps)
- Distribution: 1 per GPU (4060 Ti, 5060 Ti) + 1 queued
- Wall-clock time: ~24s (2 parallel @ 12s, then 1 @ 12s)

**Stage 4: Final** (1 image, SDXL, 1024x1024, 50 steps)
- Single GPU: 5060 Ti
- Time: ~15s

**Total funnel time**: ~77s (~1.3 minutes) from prompt to final image.

---

## Security & Deployment Considerations

### Network Security
- **Firewall**: Open port 8188 only within LAN subnet (e.g., 192.168.0.0/16)
- **No Internet Exposure**: ComfyUI instances NOT exposed to public internet
- **Backend API**: Can be exposed (add API key auth for production)
- **Frontend**: Static files, can be served from any web server

### Storage
- **NAS Mount**: Backend VM mounts NAS at `/mnt/nas`
- **Local Cache**: Copy frequently-used models to each machine's local SSD (~3-5s load vs ~65s over gigabit)
- **Image Lifecycle**: Auto-delete unselected drafts when advancing funnel stages

### Resource Management
- **VRAM Contention**: ComfyUI's internal queue handles CUDA waiting automatically
- **CPU Overhead**: Backend orchestrator is lightweight (~100 MB RAM base + ~1 MB per active generation)
- **Database**: SQLite is fine for single-user, hundreds of sessions (~MB per session)

### Monitoring
- **GPU Health Checks**: Background task polls each ComfyUI every 10s
- **Failed Generations**: Stored in DB with `status="failed"` + error message
- **Slow Responses**: If ComfyUI takes >5s to respond, lowered priority in routing
- **Frontend Polling**: GPU status bar polls `/api/gpus` every 5s

---

**Last Updated**: 2026-02-09
**Status**: Backend complete, Frontend scaffolded, Draft Grid flow operational
