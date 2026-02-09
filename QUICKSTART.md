# Vibes ImGen — Quick Start Guide

Get the Draft Grid flow running in under 10 minutes.

---

## Prerequisites

- [x] **ComfyUI installed** on at least one GPU machine (192.168.0.20:8188 ✓ confirmed working)
- [x] **Python 3.11+** on backend machine
- [x] **Node v20.12.2** on frontend dev machine
- [ ] **Models downloaded** (at minimum: SD 1.5 checkpoint for drafts)

---

## Step 1: Verify ComfyUI is Accessible

From any machine on your network:

```bash
curl http://192.168.0.20:8188/system_stats
```

Expected response:
```json
{
  "system": {
    "os": "nt",
    "python_version": "3.11.7",
    "embedded_python": true
  },
  "devices": [
    {
      "name": "NVIDIA GeForce RTX 5060 Ti",
      "type": "cuda",
      "vram_total": 17179869184,
      "vram_free": 16000000000
    }
  ]
}
```

If this fails:
- Check ComfyUI is running with `--listen 0.0.0.0` flag
- Check Windows Firewall allows port 8188 (inbound rule, TCP)
- Verify IP address is correct

---

## Step 2: Update GPU Config

Edit `config/gpus.yaml` — update IP addresses for your machines:

```yaml
nodes:
  - id: gpu-premium
    name: "RTX 5060 Ti"
    host: "192.168.0.20"  # ✓ This one works
    port: 8188
    # ... rest of config

  # Comment out machines not yet set up:
  # - id: gpu-quality
  #   name: "RTX 4060 Ti"
  #   host: "192.168.1.101"  # UPDATE when ready
  #   port: 8188
```

For now, you can run with just one GPU. The system will work with fewer GPUs (just slower batch operations).

---

## Step 3: Start Backend

```bash
cd backend

# Create virtual environment (first time only)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies (first time only)
pip install -r requirements.txt

# Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Expected output:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:app.main:Starting Vibes ImGen backend...
INFO:app.main:Loaded 1 GPU nodes from config
INFO:app.services.comfyui_client:Initialized ComfyUI client for gpu-premium @ 192.168.0.20:8188
INFO:app.main:Database initialized
INFO:app.main:Loaded 8 workflow templates
INFO:app.main:Initial health check: 1/1 GPUs healthy: ['gpu-premium']
INFO:app.main:Backend ready!
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

If you see "0/1 GPUs healthy" or errors:
- Check ComfyUI is running and accessible
- Check `config/gpus.yaml` has correct IP/port
- Check firewall rules

**Test the health endpoint:**

```bash
curl http://localhost:8001/health
```

Expected:
```json
{
  "status": "ok",
  "gpus_healthy": 1,
  "gpus_total": 1
}
```

**View GPU status:**

```bash
curl http://localhost:8001/api/gpus
```

Expected:
```json
[
  {
    "id": "gpu-premium",
    "name": "RTX 5060 Ti",
    "tier": "premium",
    "vram_gb": 16,
    "healthy": true,
    "current_queue_length": 0,
    "capabilities": ["sd15", "sdxl", "pony", "illustrious", "flux", "flux_fp8", "upscale", "controlnet", "ipadapter", "faceid"],
    "last_response_ms": 15
  }
]
```

**Browse API docs:**

Open in browser: `http://localhost:8001/docs`

This is the auto-generated FastAPI Swagger UI — you can test all endpoints here.

---

## Step 4: Start Frontend

Open a **new terminal** (keep backend running):

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start Vite dev server
npm run dev
```

Expected output:
```
VITE v5.4.11  ready in 823 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: http://192.168.0.42:5173/
  ➜  press h + enter to show help
```

Open `http://localhost:5173/` in your browser.

---

## Step 5: Test Draft Grid Flow

### 5.1 Select Flow

You should see:
- **GPU Status Bar** at top (green checkmark for gpu-premium)
- **Flow Selector** with 3 cards: Draft Grid, Concept Builder, Explorer

Click **"Draft Grid"** → "20 rapid drafts funnel to final image"

### 5.2 Enter Prompt

You should see:
- **Prompt Editor** (large textarea)
- **Negative Prompt Editor** (smaller textarea)
- **"Generate" button** at bottom

Try a simple prompt:
```
1girl, sitting cross-legged, detailed face, forest background, sunny day
```

Negative prompt (optional):
```
blurry, distorted, low quality, bad anatomy
```

Click **"Generate"**.

### 5.3 Watch Progress

You should see:
- Progress bar at bottom: "Generating 20 images..."
- Images appearing in grid as they complete (fastest first)
- Each image has: thumbnail, select/reject buttons, metadata tooltip (hover)

**Expected timeline** (with 1 GPU):
- First image: ~1.5s
- All 20 images: ~30s total (sequential on one GPU)

**With all 4 GPUs working**:
- First image: ~0.5s (5060 Ti)
- All 20 images: ~7.5s total (parallel across 4 GPUs)

### 5.4 Select Favorites

Click the **checkmark icon** on 5-8 images you like best.
- Selected images get a blue border
- Select count shows at bottom: "5 selected"

Click **"Continue with Selected"** at bottom.

### 5.5 Next Stage

You should see:
- Stage breadcrumb updates: "Drafts → **Refined**"
- Prompt editor shows same prompt (will be refined in future iterations)
- "Generate" button ready for next batch

Repeat: Generate → Select → Continue → Generate...

---

## Step 6: Verify Backend Logs

Check backend terminal for generation logs:

```
INFO:app.routers.generation:Starting batch generation: 20 images, sd15, draft
INFO:app.services.task_router:Routing task draft to gpu-premium (tier: premium, queue: 0)
INFO:app.services.comfyui_client:Submitted prompt abc123 to gpu-premium
INFO:app.websocket.aggregator:Progress: generation xyz at 5/10 steps
INFO:app.websocket.aggregator:Generation xyz complete: /api/images/session-id/xyz
INFO:app.services.image_store:Saved image: data/images/session-id/xyz.png (thumbnail: xyz_thumb.jpg)
```

---

## Troubleshooting

### "No GPU available" error

**Symptom**: API returns 503 error: "No GPU can handle this task"

**Fix**:
1. Check backend logs for health check failures
2. Verify ComfyUI is running: `curl http://192.168.0.20:8188/system_stats`
3. Check `config/gpus.yaml` has correct IP/port
4. Restart backend to re-run health checks

### "Connection refused" from frontend

**Symptom**: Frontend shows "Failed to fetch" or "Network error"

**Fix**:
1. Check backend is running at `http://localhost:8001`
2. Check CORS is enabled (it is by default)
3. Check browser console for error details (F12 → Console tab)

### WebSocket not connecting

**Symptom**: No progress updates, images appear all at once at the end

**Fix**:
1. Check browser console: Should see "WS connected: {session_id}"
2. Check backend logs: Should see "Frontend connected to session {session_id}"
3. Test WebSocket manually: `wscat -c ws://localhost:8001/ws/session/test-id` (install with `npm i -g wscat`)

### Images not appearing

**Symptom**: Progress completes but no images in grid

**Fix**:
1. Check browser console for 404 errors on `/api/images/...`
2. Check `data/images/` directory exists and has images
3. Check backend logs for image save errors
4. Verify image URLs in generation response: `curl http://localhost:8001/api/generate/{generation_id}`

### ComfyUI "out of memory" error

**Symptom**: Generation fails with "CUDA out of memory" in ComfyUI logs

**Fix**:
1. Reduce batch size in frontend (e.g., 10 instead of 20)
2. Check other processes using GPU VRAM (Task Manager → Performance → GPU)
3. Restart ComfyUI to clear VRAM
4. For 3050 Ti (4GB): Only use SD1.5 at 512x512

### Backend won't start — "Address already in use"

**Symptom**: `uvicorn` fails with "Address already in use" on port 8001

**Fix**:
1. Check if backend is already running: `curl http://localhost:8001/health`
2. Kill existing process: `pkill -f uvicorn` (Linux) or Task Manager → End Process (Windows)
3. Use different port: `uvicorn app.main:app --port 8002`

---

## What's Working vs Not Working

### ✅ Currently Functional

- [x] Backend startup (GPU registry, ComfyUI clients, health checks)
- [x] Frontend startup (Vite dev server, React app)
- [x] Draft Grid flow selection
- [x] Prompt editor (text input)
- [x] Single image generation (API call)
- [x] Batch generation (20 drafts distributed across GPUs)
- [x] WebSocket progress streaming (real-time updates)
- [x] Image display in grid (thumbnails)
- [x] Image selection (checkmark/X buttons)
- [x] Advancing iteration (stage counter increments)
- [x] GPU status bar (health indicators)

### 🚧 Partially Implemented

- [ ] Iteration with prompt refinement — **frontend calls API, but backend returns same prompt** (LLM pipeline not implemented)
- [ ] Feedback bar actions — **only "Generate" and "Continue" work**, "More Like This"/"Refine"/"Upscale" buttons are placeholders

### 🔴 Not Yet Built

- [ ] LLM prompt refinement (3-stage pipeline with Ollama)
- [ ] img2img generation (workflow exists, no API route yet)
- [ ] ControlNet/IP-Adapter reference controls
- [ ] Concept Builder flow (UI placeholder only)
- [ ] Explorer flow (UI placeholder only)
- [ ] Video Builder flow (not even placeholder)
- [ ] LoRA browsing / injection
- [ ] ESRGAN upscaling (workflow exists, no API route yet)
- [ ] Session management (list sessions, delete session, view history)

---

## Next Steps

Once you've verified Draft Grid works:

1. **Add More GPUs** (optional):
   - Install ComfyUI on machines B, C, D
   - Update `config/gpus.yaml` with their IPs
   - Restart backend → verify health checks pass
   - Test batch generation → verify distribution across all GPUs

2. **Download More Models** (for SDXL/Flux):
   - SD 1.5 only allows 512x512 drafts
   - SDXL allows 1024x1024 refined/polished stages
   - See `ARCHITECTURE.md` or plan file for download links

3. **Implement LLM Pipeline** (Priority 1):
   - Install Ollama on a GPU machine or VM
   - Download models: `ollama pull hermes3:8b`, `ollama pull phi4:14b`, `ollama pull minicpm-v`
   - Implement `feedback_interpreter.py`, `prompt_engineer.py`, `vision_analyzer.py`
   - Add API route: `POST /api/iterate/refine-prompt`
   - Test: User feedback → refined prompt → verify improvement

4. **Build Other Flows**:
   - Concept Builder (structured fields + field locking)
   - Explorer (LoRA browser + A/B compare)
   - Video Builder (keyframe timeline + AnimateDiff)

---

## Useful Commands

### Backend

```bash
# Start backend with auto-reload (for development)
uvicorn app.main:app --reload --port 8001

# Start backend in production mode
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 2

# Check backend logs
# (printed to terminal by default, or redirect to file)
uvicorn app.main:app --port 8001 > backend.log 2>&1

# Test API endpoints
curl http://localhost:8001/health
curl http://localhost:8001/api/gpus
curl -X POST http://localhost:8001/api/sessions -H "Content-Type: application/json" -d '{"flow_type": "draft_grid"}'
```

### Frontend

```bash
# Start dev server
npm run dev

# Build for production
npm run build
# Output: frontend/dist/

# Preview production build
npm run preview
```

### ComfyUI

```bash
# Check ComfyUI status
curl http://192.168.0.20:8188/system_stats

# Check ComfyUI queue
curl http://192.168.0.20:8188/queue

# Clear ComfyUI queue (if stuck)
curl -X POST http://192.168.0.20:8188/queue/clear

# Check installed models
curl http://192.168.0.20:8188/object_info
# Returns giant JSON — search for "CheckpointLoader" to see available checkpoints
```

### Database

```bash
# SQLite database is at: data/vibes.db

# Inspect database (install sqlite3 command-line tool)
sqlite3 data/vibes.db

# Useful queries:
sqlite> .tables
sqlite> SELECT * FROM sessions;
sqlite> SELECT id, status, prompt FROM generations WHERE session_id = 'abc123';
sqlite> SELECT COUNT(*) FROM generations WHERE status = 'complete';
sqlite> .quit
```

---

## Performance Tips

1. **Use Local Model Storage**: Copy models to each machine's local SSD (3-5s load time vs 60s over network)
2. **Batch Sizing**: More images per batch = better GPU utilization, but longer wait for first result
3. **Draft Stage**: Use ALL GPUs (fastest turnaround) — even premium GPU is fast at 512x512
4. **Quality Stage**: Let lower-tier GPUs handle standard work, reserve premium for final/upscale
5. **VRAM Management**: If hitting OOM, reduce resolution (1024→896) or steps (25→20) before downgrading model

---

## Files to Know About

### Configuration
- `config/gpus.yaml` — GPU node registry (edit this first)
- `backend/app/templates/workflows/manifest.yaml` — Workflow metadata
- `frontend/src/index.css` — Tailwind config (custom color palette)

### Backend Entry Points
- `backend/app/main.py` — FastAPI app, lifespan, WebSocket endpoint
- `backend/app/routers/generation.py` — Generation API routes
- `backend/app/routers/sessions.py` — Session API routes
- `backend/app/services/gpu_registry.py` — GPU config loader
- `backend/app/services/task_router.py` — Routing logic

### Frontend Entry Points
- `frontend/src/main.tsx` — React entry
- `frontend/src/App.tsx` — Top-level routing
- `frontend/src/components/flows/DraftGrid/DraftGridFlow.tsx` — Draft Grid implementation
- `frontend/src/stores/sessionStore.ts` — Session state
- `frontend/src/stores/generationStore.ts` — Generation results + selection state

### Data Directories
- `data/images/{session_id}/` — Generated images (full-size PNGs)
- `data/images/{session_id}/*_thumb.jpg` — Thumbnails (256x256 JPEGs)
- `data/vibes.db` — SQLite database (sessions + generations)

---

**Estimated Time to First Image**: ~5 minutes (assuming ComfyUI already installed + SD1.5 model downloaded)

**Estimated Time for Full Setup**: ~30 minutes (install ComfyUI on all 4 machines, download all models)

---

**Last Updated**: 2026-02-09
