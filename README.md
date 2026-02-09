# Vibes ImGen

**Iterative image generation orchestrator** — Progressive refinement across 4 GPUs with multi-stage LLM prompt refinement.

## Project Status

### ✅ Backend — COMPLETE
- **Core Services**: GPU registry, ComfyUI client pool, task router, workflow engine, image store, WebSocket progress aggregator
- **API Routes**: Sessions, generation (single + batch), GPUs status
- **Database**: SQLAlchemy async + aiosqlite (models + schemas)
- **Workflow Templates**: 8 templates (SD1.5, SDXL, Flux txt2img/img2img, LoRA injection, upscaling)
- **Main App**: FastAPI with lifespan events, CORS, WebSocket endpoint

### 🚧 Frontend — SCAFFOLDED
- **Build Status**: Compiles clean, runs successfully
- **Draft Grid Flow**: IMPLEMENTED (20-draft funnel with iterative refinement)
- **Placeholder Flows**: Concept Builder, Explorer (UI placeholders only)
- **State Management**: Zustand stores (session, generation, GPU), WebSocket hook
- **Shared Components**: Image grid, prompt editor, GPU status bar, feedback bar

### 🔴 NOT YET BUILT
- **LLM Pipeline**: 3-stage prompt refinement (feedback interpreter → prompt engineer → vision analyzer)
- **Iteration Router**: Feedback engine to generate iteration plans
- **Concept Builder UI**: Structured fields + concept locking
- **Explorer UI**: LoRA browser + A/B compare
- **Video Builder UI**: Keyframe timeline + AnimateDiff rendering
- **Reference Controls**: ControlNet/IP-Adapter injection for pose/style/face preservation

---

## Architecture

```
Browser (React 19 + TS + Tailwind v3 + Vite 5 + Zustand)
    │ HTTP + WebSocket
    ▼
FastAPI Orchestrator (:8001) @ backend VM
    │  GPU Registry, Task Router, Workflow Engine
    │  (future: Feedback Engine, LLM Refiner, Batch Dispatcher)
    │
    ├──► ComfyUI @ 192.168.0.20:8188 (5060 Ti 16GB — premium tier) ✓ installed
    ├──► ComfyUI @ machine-B:8188 (4060 Ti 8GB — quality tier)
    ├──► ComfyUI @ machine-C:8188 (3060 12GB — standard tier)
    └──► ComfyUI @ machine-D:8188 (3050 Ti 4GB — draft tier)

    (future) Ollama @ localhost:11434 (prompt refinement + vision)
```

### Deployment Topology
- **Frontend VM** (Proxmox): Serves built React app (~1 GB RAM, 1 vCPU)
- **Backend VM** (Proxmox): FastAPI orchestrator (~2-4 GB RAM, 1-2 vCPUs, NAS mount)
- **4x GPU Machines** (native): Each runs ComfyUI with `--listen 0.0.0.0`
- **Ollama** (future): On spare GPU machine or dedicated VM
- **NAS** (Synology): Central model repo + generated image storage

---

## Multi-GPU Strategy

| GPU | VRAM | Tier | Capabilities | Role |
|-----|------|------|-------------|------|
| 5060 Ti | 16GB | `premium` | SD1.5, SDXL, Pony, Illustrious, Flux fp8, upscale, ControlNet, IP-Adapter | Final quality, upscaling, reference controls |
| 4060 Ti | 8GB | `quality` | SD1.5, SDXL, Pony, Illustrious | Quality SDXL generation |
| 3060 | 12GB | `standard` | SD1.5, SDXL, Pony, Illustrious | Mid-quality SDXL |
| 3050 Ti | 4GB | `draft` | SD1.5 only | Bulk draft thumbnails (512x512) |

**Routing Strategy**:
- **Batch/Draft Work**: ALL idle GPUs participate — faster GPUs complete drafts quicker
- **Quality/Final Work**: Prefer higher-tier GPUs (quality → premium)
- **Overflow Handling**: If preferred tier is overloaded, routes to next-best tier
- **Health Checks**: Background polling (10s interval) marks slow/unresponsive GPUs unhealthy
- **Graceful Degradation**: System works with 1-2 GPUs available (fewer parallel drafts)

GPU config: `config/gpus.yaml` — update host/port/capabilities per machine.

---

## Four Generation Flows

### 1. Concept Builder (NOT YET BUILT)
- **Input**: Structured fields (subject, pose, background, style, mood, lighting)
- **Process**: Ollama composes fields → 4 SDXL variations → user selects → LLM refines → repeat
- **Key Feature**: Field locking — lock "subject" constant while iterating style/mood
- **UI**: Two-column — concept form (left 40%) + image grid (right 60%)

### 2. Draft Grid (Funnel) ✅ IMPLEMENTED
- **Input**: Simple text prompt
- **Process**: 20 rapid SD1.5 drafts → user selects → 8 SDXL refined → 3 polished → 1 final
- **Key Feature**: Progressive quality funnel — fewer images, better models/settings each stage
- **UI**: Full-width grid with funnel breadcrumb showing stages
- **Status**: Fully functional — prompt → generate → select → advance iteration

### 3. Concept Explorer (NOT YET BUILT)
- **Input**: LoRA selection + optional prompt
- **Process**: Browse LoRAs → generate showcase → refine with feedback → A/B compare combos
- **Key Feature**: LoRA browser with strength sliders, A/B comparison view
- **UI**: Three-column — LoRA browser (left) + gallery (center) + controls (right)

### 4. Keyframe Video Builder (NOT YET BUILT)
- **Input**: Scene concept + keyframe descriptions (text/image per keyframe)
- **Process**: Define keyframes iteratively → arrange timeline → preview motion → full AnimateDiff render
- **Key Feature**: Subject consistency via IP-Adapter + ControlNet, iterative keyframe refinement
- **UI**: Horizontal timeline (bottom) + keyframe thumbnails + preview player (center)

---

## Iteration/Feedback System (NOT YET BUILT)

All flows share a common feedback loop:
- **Select/Reject**: Pick favorites, advance the funnel
- **More Like This**: img2img with low denoise (0.3-0.5) using same seed
- **Refine**: User gives text direction → 3-stage LLM pipeline refines prompt
- **Iterate**: Direct parameter adjustments via sliders
- **Upscale**: Send to premium GPU with ESRGAN

### 3-Stage LLM Prompt Refinement Pipeline

**Why multi-stage?** Single-LLM calls drift from intent, add flowery language, don't understand SD syntax.

#### Stage 1: Feedback Interpreter
- **Input**: User's free-text feedback + selected/rejected image IDs
- **Output**: Structured JSON change instructions
- **LLM**: `hermes3:8b` (Ollama) — excellent at structured/JSON output
- **Example**: "make it moodier, keep pose, change background to rainy city"
  ```json
  {
    "keep": ["1girl", "sitting cross-legged", "detailed face"],
    "remove": ["forest background", "sunny"],
    "add": ["rainy cityscape background", "neon reflections", "moody atmosphere"],
    "modify": {"lighting": "dim, atmospheric"},
    "emphasis_up": ["mood", "atmosphere"],
    "emphasis_down": []
  }
  ```

#### Stage 2: Prompt Engineer
- **Input**: Current prompt + structured changes from Stage 1 + model family
- **Output**: New SD/Flux-optimized prompt
- **LLM**: `phi4:14b` (Ollama) — strong reasoning, precise rule-following
- **System Prompt**: SD prompt syntax rules, model-specific conventions, anti-patterns
- **Key Constraint**: NEVER invents concepts — only applies structured changes from Stage 1

#### Stage 3: Vision Analyzer (optional)
- **When Used**: User selects image and says "more like this"
- **Input**: Selected image bytes + question about what to describe
- **Output**: Visual description (composition, style, mood, colors)
- **LLM**: `minicpm-v` (Ollama) — multimodal vision model
- **Fed into Stage 2** as additional context

**Session Intent Tracking**:
- Backend maintains "Intent Document" per session — accumulates feedback, patterns from rejections, explicit preferences
- Stage 1 receives full history — can spot patterns across multiple rounds
- A/B comparison: Vision model compares selected vs rejected to find delta
- Rejection learning: Builds "avoid" list for Stage 2

**Status**: NOT YET IMPLEMENTED — services files exist as stubs, Ollama integration pending.

---

## Tech Stack

### Backend
- **Framework**: FastAPI 0.115.0 + uvicorn
- **Database**: SQLAlchemy async + aiosqlite
- **HTTP**: httpx (async ComfyUI client)
- **WebSocket**: websockets 14.1 (progress streaming)
- **Image**: Pillow 11.0 (thumbnails)
- **Config**: PyYAML 6.0

### Frontend
- **Framework**: React 19.0.0 + TypeScript 5.6
- **Build**: Vite 5.4 (NOT Vite 7 — requires Node 22+)
- **Styling**: Tailwind CSS v3.4 (NOT v4 — different config approach)
- **State**: Zustand 5.0 (minimal boilerplate, fine-grained subscriptions)
- **Node**: v20.12.2 (current on dev machine)

### Image Generation
- **Engine**: 4x ComfyUI instances (native, one per GPU machine)
- **LLM** (future): Ollama (hermes3:8b, phi4:14b, minicpm-v)
- **Models**: SD1.5, SDXL, Flux fp8, ControlNet, IP-Adapter, ESRGAN

---

## File Structure

```
I:\Vibes\ImGen\
├── backend/
│   ├── app/
│   │   ├── main.py              — FastAPI app entry, lifespan, WS endpoint
│   │   ├── models/
│   │   │   ├── database.py      — SQLAlchemy async session factory
│   │   │   ├── orm.py           — DB models (SessionORM, GenerationORM)
│   │   │   └── schemas.py       — Pydantic request/response models
│   │   ├── routers/
│   │   │   ├── sessions.py      — POST/GET /api/sessions
│   │   │   ├── generation.py    — POST /api/generate, /api/generate/batch
│   │   │   └── gpus.py          — GET /api/gpus
│   │   ├── services/
│   │   │   ├── gpu_registry.py  — GPU config loader, health checks
│   │   │   ├── comfyui_client.py — HTTP+WS client pool (one per GPU)
│   │   │   ├── task_router.py   — Route tasks to GPUs by tier/capability
│   │   │   ├── workflow_engine.py — Load templates, substitute params, inject LoRAs
│   │   │   └── image_store.py   — Filesystem storage + thumbnails
│   │   ├── websocket/
│   │   │   └── aggregator.py    — Multiplex ComfyUI WS → per-session frontend WS
│   │   └── templates/workflows/
│   │       ├── manifest.yaml    — Workflow template metadata
│   │       ├── sd15_txt2img.json
│   │       ├── sd15_img2img.json
│   │       ├── sdxl_txt2img.json
│   │       ├── sdxl_img2img.json
│   │       ├── sdxl_with_lora.json
│   │       ├── flux_txt2img.json
│   │       └── upscale_esrgan.json
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.tsx             — React entry
│   │   ├── App.tsx              — Top-level routing (flow selector + active flow)
│   │   ├── types/index.ts       — TypeScript types
│   │   ├── api/client.ts        — HTTP API client
│   │   ├── stores/
│   │   │   ├── sessionStore.ts  — Current session, stage, iteration round
│   │   │   ├── generationStore.ts — Generation results, selection state
│   │   │   └── gpuStore.ts      — GPU status polling
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts  — WebSocket connection + message handling
│   │   ├── components/
│   │   │   ├── flows/
│   │   │   │   ├── FlowSelector.tsx  — Initial flow picker
│   │   │   │   └── DraftGrid/
│   │   │   │       └── DraftGridFlow.tsx — ✅ Draft Grid implementation
│   │   │   └── shared/
│   │   │       ├── GPUStatusBar.tsx
│   │   │       ├── ImageGrid.tsx
│   │   │       ├── ImageCard.tsx
│   │   │       ├── PromptEditor.tsx
│   │   │       └── FeedbackBar.tsx
│   │   └── index.css            — Tailwind imports + custom CSS vars
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js       — Tailwind v3 config (custom color palette)
│   └── tsconfig.json
├── config/
│   └── gpus.yaml                — GPU node registry (host/port/capabilities)
├── data/
│   ├── images/                  — Generated images
│   └── uploads/                 — User-uploaded reference images
├── scripts/
│   └── setup_comfyui.py         — Automated ComfyUI setup script (per tier)
└── README.md                     — This file
```

---

## Key Patterns

### Backend
- **ComfyUIClientPool**: One HTTP+WS client per GPU node, initialized at startup
- **TaskRouter**: Tier-based routing with overflow, health-aware
- **WorkflowEngine**: JSON templates with `{{variable}}` placeholders, dynamic LoRA injection
- **ProgressAggregator**: Multiplexes ComfyUI progress → per-session frontend WebSocket
- **Background Tasks**: `asyncio.create_task` for generation jobs (300s timeout)
- **Database**: Async SQLAlchemy with aiosqlite, session factory in `app.state.db_session`

### Frontend
- **Zustand Stores**: `sessionStore` (session state), `generationStore` (results + selections), `gpuStore` (GPU status)
- **WebSocket Hook**: `useWebSocket(sessionId)` — connects, handles progress + complete messages, updates stores
- **API Client**: `src/api/client.ts` — typed fetch wrappers for all endpoints
- **Shared Components**: Image grid (lazy), image card (select/reject), prompt editor, GPU status bar

---

## Current Configuration

### GPU Nodes (`config/gpus.yaml`)
```yaml
nodes:
  - id: gpu-premium
    name: "RTX 5060 Ti"
    vram_gb: 16
    tier: premium
    host: "192.168.0.20"  # ✓ installed via Stability Matrix
    port: 8188
    capabilities: [sd15, sdxl, pony, illustrious, flux, flux_fp8, upscale, controlnet, ipadapter, faceid]
    max_resolution: 1536
    max_batch: 4

  - id: gpu-quality
    name: "RTX 4060 Ti"
    vram_gb: 8
    tier: quality
    host: "192.168.1.101"  # UPDATE: IP of 4060 Ti machine
    port: 8188
    capabilities: [sd15, sdxl, pony, illustrious]
    max_resolution: 1024
    max_batch: 4

  - id: gpu-standard
    name: "RTX 3060"
    vram_gb: 12
    tier: standard
    host: "192.168.1.102"  # UPDATE: IP of 3060 machine
    port: 8188
    capabilities: [sd15, sdxl, pony, illustrious]
    max_resolution: 1024
    max_batch: 2

  - id: gpu-draft
    name: "RTX 3050 Ti"
    vram_gb: 4
    tier: draft
    host: "192.168.1.103"  # UPDATE: IP of 3050 Ti machine
    port: 8188
    capabilities: [sd15]
    max_resolution: 512
    max_batch: 1
```

**Action Required**: Update IP addresses for machines B, C, D once ComfyUI is installed.

### Workflow Templates (`backend/app/templates/workflows/`)
8 templates currently implemented:
- **sd15_txt2img**: SD 1.5 text-to-image (fast drafts, 512x512, 10 steps)
- **sd15_img2img**: SD 1.5 image-to-image (15 steps, denoise 0.5)
- **sdxl_txt2img**: SDXL text-to-image (1024x1024, 25 steps)
- **sdxl_img2img**: SDXL image-to-image (25 steps, denoise 0.5)
- **sdxl_with_lora**: SDXL with LoRA support (max 3 LoRAs)
- **flux_txt2img**: Flux text-to-image (1024x1024, 20 steps, cfg 1.0)
- **upscale_esrgan**: ESRGAN 4x upscale (any model family)

Each template is ComfyUI API-format JSON with `{{prompt}}`, `{{checkpoint}}`, etc. placeholders.

---

## Running the Project

### Prerequisites
1. **ComfyUI installed on each GPU machine** with `--listen 0.0.0.0` flag
2. **Firewall rules** allowing port 8188 inbound on each machine
3. **Models downloaded** per tier (see plan file for download links)
4. **Python 3.11+** on backend VM
5. **Node v20.12.2** on frontend dev machine (or VM)

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Update config/gpus.yaml with actual IP addresses

# Initialize database (auto-creates on first run)
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

Backend runs at `http://localhost:8001`
- Health check: `GET /health`
- GPU status: `GET /api/gpus`
- API docs: `http://localhost:8001/docs` (FastAPI auto-generated)

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` (Vite default)

**Production Build**:
```bash
npm run build  # outputs to frontend/dist/
```

Serve `dist/` via Nginx/Caddy on frontend VM.

---

## API Endpoints

### Sessions
- `POST /api/sessions` — Create new session
  - Body: `{ "flow_type": "draft_grid", "initial_config": {...} }`
  - Returns: `{ "id": "uuid", "flow_type": "draft_grid", "created_at": "..." }`
- `GET /api/sessions/{id}` — Load existing session
- `GET /api/sessions` — List all sessions (pagination TODO)

### Generation
- `POST /api/generate` — Single image generation
  - Body: `GenerationRequest` (prompt, model_family, task_type, params, session_id)
  - Returns: `GenerationResponse` (id, status, gpu_id)
- `POST /api/generate/batch` — Batch generation (distributed across GPUs)
  - Body: `BatchGenerationRequest` (prompt, count, params)
  - Returns: `BatchGenerationResponse` (batch_id, total_count, gpu_assignments)
- `GET /api/generate/{id}` — Get generation result
- `GET /api/images/{session_id}/{image_id}` — Serve generated image
- `GET /api/images/{session_id}/{image_id}/thumb` — Serve thumbnail

### GPUs
- `GET /api/gpus` — List all GPU nodes with health status

### WebSocket
- `WS /ws/session/{session_id}` — Real-time progress streaming
  - Receives: `{ "type": "progress", "generation_id": "...", "current": 5, "total": 20 }`
  - Receives: `{ "type": "complete", "generation_id": "...", "image_url": "...", "thumbnail_url": "..." }`

### Future Endpoints (NOT YET IMPLEMENTED)
- `POST /api/iterate` — Submit feedback, get iteration plan
- `POST /api/iterate/auto` — Submit feedback + auto-generate
- `POST /api/iterate/refine-prompt` — LLM prompt refinement
- `POST /api/iterate/concept` — Concept Builder structured generation
- `GET /api/models`, `/api/loras` — Available checkpoints and LoRAs
- `POST /api/video/keyframes`, `GET /api/video/{id}/timeline`, etc. (Video Builder)

---

## ComfyUI Setup (Per Machine)

### Installation
**Recommended**: Stability Matrix (current approach on 5060 Ti @ `192.168.0.20`)
1. Install ComfyUI via Stability Matrix
2. **Enable LAN access**: Add `--listen 0.0.0.0` to launch arguments in package settings
3. Open Windows Firewall for port 8188 (inbound rule, TCP)
4. Restart ComfyUI — verify reachable from other machines

**Alternative** (manual):
```bash
git clone https://github.com/Comfy-Org/ComfyUI
cd ComfyUI
# Python setup (venv + deps)
python main.py --listen 0.0.0.0 --port 8188
```

### Custom Nodes (all machines)
- **ComfyUI Manager**: Makes installing other nodes easy
- **ComfyUI_IPAdapter_plus**: `git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git` in `custom_nodes/`
- **insightface** (for FaceID): `pip install insightface` (needs Visual C++ build tools on Windows)
- **(Future) ComfyUI-AnimateDiff-Evolved**: For video keyframe flow
- **(Future) ComfyUI-Frame-Interpolation**: RIFE/FILM interpolation
- **(Future) ComfyUI-VideoHelperSuite**: Video I/O

### Model Downloads (per tier)

**3050 Ti (draft tier, ~4 GB)**:
- SD 1.5: `v1-5-pruned-emaonly.safetensors` (~4 GB) → `models/checkpoints/`

**3060 / 4060 Ti (standard/quality tier, ~10 GB)**:
- SD 1.5: `v1-5-pruned-emaonly.safetensors` (~4 GB)
- SDXL Base: `sd_xl_base_1.0.safetensors` (~6.1 GB)

**5060 Ti (premium tier, ~40+ GB)**:
- SD 1.5: `v1-5-pruned-emaonly.safetensors` (~4 GB)
- SDXL Base: `sd_xl_base_1.0.safetensors` (~6.1 GB)
- Flux Dev FP8: `flux1-dev-fp8.safetensors` (~12 GB) → [Comfy-Org/flux1-dev](https://huggingface.co/Comfy-Org/flux1-dev)
- ControlNet models (OpenPose, Depth, Canny): ~6.5 GB total → `models/controlnet/`
- IP-Adapter models (Plus, FaceID PlusV2): ~1.6 GB total → `models/ipadapter/`
- CLIP Vision: `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` (~2.5 GB) → `models/clip_vision/`
- Upscaler: `4x-UltraSharp.pth` (~67 MB) → `models/upscale_models/`

Full download links in plan file: `C:\Users\zcoch\.claude\plans\velvet-percolating-quiche.md`

---

## Verification Checklist

### Backend
- [ ] ComfyUI running on each machine with `--listen 0.0.0.0`
- [ ] `config/gpus.yaml` updated with actual IP addresses
- [ ] Backend starts without errors: `uvicorn app.main:app --port 8001`
- [ ] Health check passes: `curl http://localhost:8001/health`
- [ ] GPU status shows all nodes: `curl http://localhost:8001/api/gpus`
- [ ] Initial health check logs show all GPUs healthy (or identifies unreachable ones)

### Frontend
- [ ] Frontend builds clean: `npm run build`
- [ ] Dev server runs: `npm run dev`
- [ ] Can select Draft Grid flow from menu
- [ ] Prompt editor appears, can type prompt
- [ ] GPU status bar shows GPU nodes

### Integration
- [ ] Create session via API: `POST /api/sessions`
- [ ] Generate single image: `POST /api/generate` (verify routes to correct GPU)
- [ ] Generate batch: `POST /api/generate/batch` (verify distribution across GPUs)
- [ ] WebSocket connects: Check browser console for WS connection
- [ ] Draft Grid flow end-to-end: prompt → generate 20 drafts → drafts appear in grid
- [ ] Select images → click "Continue with Selected" → iteration advances (prompt updates)

### Future (NOT YET TESTABLE)
- [ ] LLM refinement: Provide feedback text → verify Ollama produces refined prompt
- [ ] img2img: Select image → "more like this" → verify img2img generation
- [ ] ControlNet: Upload reference → "keep this pose" → verify pose transfer
- [ ] Video: Create keyframes → preview → full render → verify subject consistency

---

## Known Gotchas

1. **Node Version**: v20.12.2 required — Vite 5 compatible. Vite 7+ needs Node 22+.
2. **Tailwind Version**: v3.4 used (NOT v4) — v4 has different config approach.
3. **Zustand Version**: v5.0 — uses `create()` API, no middleware needed for basic stores.
4. **ComfyUI API**: Always enabled by default — web UI endpoint IS the API endpoint.
5. **Firewall**: Windows Firewall blocks port 8188 by default — must create inbound rule.
6. **poll_until_complete**: Has 300s (5 min) timeout hardcoded in backend.
7. **Workflow Templates**: Use `{{variable}}` syntax, NOT Jinja2 `{{ variable }}`.
8. **Image Paths**: Served via `/api/images/{session_id}/{image_id}`, NOT static file serving.

---

## Next Steps (Implementation Order)

1. **Verify Current Setup**:
   - Install ComfyUI on machines B, C, D
   - Update `config/gpus.yaml` with actual IPs
   - Run backend + frontend, test Draft Grid flow end-to-end

2. **LLM Pipeline** (Priority 1):
   - Implement `feedback_interpreter.py`, `prompt_engineer.py`, `vision_analyzer.py`
   - Integrate Ollama (install, download models: hermes3:8b, phi4:14b, minicpm-v)
   - Add API routes: `POST /api/iterate/refine-prompt`
   - Test: User feedback → structured changes → refined prompt

3. **Iteration System** (Priority 2):
   - Implement `FeedbackEngine` to generate `IterationPlan`
   - Add API routes: `POST /api/iterate`, `POST /api/iterate/auto`
   - Frontend: Feedback bar with "More Like This", "Refine", "Iterate" buttons
   - Test: Select image → feedback → iteration plan → auto-generate

4. **Concept Builder Flow** (Priority 3):
   - Frontend UI: Structured form (subject, pose, background, style, mood, lighting)
   - Field locking UI (lock icon per field)
   - Ollama prompt composition from fields
   - Test: Fill form → generate variations → lock fields → iterate

5. **Explorer Flow** (Priority 4):
   - LoRA discovery: Query ComfyUI instances for installed LoRAs
   - LoRA browser UI (search, filter, strength sliders)
   - A/B comparison view (side-by-side with diff overlay)
   - Test: Select LoRA → generate showcase → compare variants

6. **Reference Controls** (Priority 5):
   - ControlNet/IP-Adapter workflow injection in `WorkflowEngine`
   - Frontend: Upload reference image, select control type (pose/style/face)
   - Pinned traits system (chips in UI, persistence in Intent Document)
   - Test: Upload face → "keep this face" → generate → verify face preserved

7. **Video Builder Flow** (Priority 6):
   - Timeline UI (horizontal, keyframe thumbnails)
   - Keyframe editor (add/remove/reorder)
   - AnimateDiff workflow templates + custom nodes
   - RIFE/FILM interpolation
   - Test: Create 3 keyframes → preview → full render → verify consistency

8. **Polish + Deployment**:
   - Flux templates (currently have txt2img, add img2img)
   - ESRGAN upscaling integration (workflow exists, test E2E)
   - Lightbox for full-size image viewing
   - GPU dashboard (utilization graphs, queue depths)
   - Session management (list, delete, disk usage tracking)
   - Deploy frontend VM + backend VM on Proxmox

---

## Memory File

Project-specific memory maintained at:
`C:\Users\zcoch\.claude\projects\I--Vibes-ImGen\memory\MEMORY.md`

Comprehensive build plan (426 lines):
`C:\Users\zcoch\.claude\plans\velvet-percolating-quiche.md`

---

## License

Private project — no public license.

---

**Last Updated**: 2026-02-09
**Project Phase**: Backend complete, Frontend scaffolded, Draft Grid flow working
**Next Milestone**: LLM pipeline implementation (3-stage prompt refinement)
