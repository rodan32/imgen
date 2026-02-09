# LoRA Discovery & Checkpoint Learning Implementation Plan

## Overview
Add intelligent checkpoint and LoRA experimentation to improve image quality and variety during the Draft Grid flow.

## Features

### 1. LoRA Discovery (Auto-LoRA)
**Goal**: Automatically discover and apply relevant LoRAs based on prompt keywords.

**How it works**:
- Parse prompt for meaningful keywords (remove stop words, extract nouns/styles)
- Fetch available LoRAs from ComfyUI `/object_info` endpoint
- Match LoRA names against keywords (e.g., "anime" → "anime_style_v2.safetensors")
- Apply top 3 most relevant LoRAs with relevance-based strength (0.5-0.8)
- Optional: Vary LoRA combinations across batch (some images get LoRA A, some get LoRA B)

**Frontend Control**:
- Toggle: "Auto-LoRA" (checkbox next to aspect ratio selector)
- When enabled, backend automatically discovers and applies LoRAs

### 2. Checkpoint Experimentation (Explore Mode)
**Goal**: Test multiple checkpoints and learn which produce better results.

**How it works**:
- Define checkpoint pools per tier:
  - SD1.5 Draft: [beenyouLite, realisticVision, dreamshaper]
  - SDXL Standard: [epicrealismXL, realvisxl, juggernautXL]
- In Explore Mode: distribute batch across 2-3 checkpoints
  - Example: 20 drafts → 7 with beenyouLite, 7 with realisticVision, 6 with dreamshaper
- Track selection rates per checkpoint
- Future batches favor better-performing checkpoints
- In Quick Mode: use single best-performing checkpoint

**Frontend Control**:
- Toggle: "Explore Mode" vs "Quick Mode"
- Display checkpoint stats in GPU panel (selection rates)

## Implementation Steps

### Phase 1: Backend Services ✅ DONE
- [x] Create `LoRADiscovery` service (`lora_discovery.py`)
- [x] Create `CheckpointLearning` service (`checkpoint_learning.py`)
- [x] Add `get_object_info()` method to ComfyUIClient
- [x] Initialize services in `main.py`
- [x] Add `explore_mode` and `auto_lora` flags to `BatchGenerationRequest`

### Phase 2: Generation Logic Integration
- [ ] Update `/api/generate/batch` endpoint logic:
  - [ ] If `auto_lora=True`: discover and inject LoRAs
  - [ ] If `explore_mode=True`: distribute batch across checkpoints
  - [ ] Track checkpoint assignments in generation records
- [ ] Update `_run_generation` to record checkpoint performance
- [ ] Add endpoint `/api/checkpoints/stats` to view learning data

### Phase 3: Frontend Controls
- [ ] Add "Auto-LoRA" toggle to DraftGridFlow
- [ ] Add "Explore Mode" / "Quick Mode" toggle to DraftGridFlow
- [ ] Update API client to send new flags
- [ ] Display checkpoint stats in GPUs panel

### Phase 4: Feedback Integration
- [ ] When user selects images, record which checkpoints they came from
- [ ] Update `CheckpointLearning` stats on selection
- [ ] Prefer better-performing checkpoints in future generations

## Example: Draft Stage with Both Features

**User**:
- Prompt: "beautiful anime girl with flowing hair in magical forest"
- Explore Mode: ON
- Auto-LoRA: ON
- Count: 20

**Backend**:
1. LoRA Discovery finds: ["anime_style_v2", "fantasy_landscape", "detailed_hair"]
2. Checkpoint Learning decides: [beenyouLite: 7, realisticVision: 7, dreamshaper: 6]
3. Generates:
   - 7 images with beenyouLite + anime_style_v2 (0.7 strength)
   - 7 images with realisticVision + fantasy_landscape (0.6 strength)
   - 6 images with dreamshaper + detailed_hair (0.5 strength)
4. User selects favorites → records which checkpoint/LoRA combinations worked

**Learning**:
- If realisticVision images get selected more, future drafts use more realisticVision
- If anime_style_v2 LoRA images get selected, that LoRA is prioritized in future anime prompts

## API Changes

### Request
```json
{
  "session_id": "...",
  "prompt": "...",
  "explore_mode": true,
  "auto_lora": true,
  ...
}
```

### Response (unchanged)
```json
{
  "batch_id": "...",
  "total_count": 20,
  "gpu_distribution": {...}
}
```

### New Endpoint: GET /api/checkpoints/stats
```json
{
  "beenyouLite_l15.safetensors": {
    "selected": 45,
    "total": 120,
    "selection_rate": 0.375
  },
  ...
}
```

## Configuration

### Checkpoint Pools
Defined in `CheckpointLearning.__init__()`:
```python
self.checkpoint_pools = {
    "sd15_draft": ["beenyouLite_l15.safetensors", "realisticVision...", "dreamshaper..."],
    "sdxl_standard": ["epicrealismXL_pureFix.safetensors", ...],
}
```

Users can customize by editing pools or adding more checkpoints.

### LoRA Discovery Tuning
- Keyword extraction can be improved with NLP libraries
- Relevance scoring can be enhanced with embeddings
- Max LoRAs per image: currently 3, configurable

## Future Enhancements
- **LoRA Libraries**: Index LoRA metadata (tags, trigger words) for better matching
- **Multi-LoRA Strategies**: Test LoRA combinations (A+B vs A alone vs B alone)
- **Prompt Analysis**: Use LLM to extract concepts from prompt for smarter matching
- **Visual Feedback**: Show which checkpoint/LoRA was used on each image card
- **Export Preferences**: Save learned checkpoint preferences per user/style
