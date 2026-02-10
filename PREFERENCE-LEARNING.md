# Preference Learning System

## Overview

Multi-dimensional preference learning that tracks your selections/rejections with full context to personalize checkpoint and LoRA recommendations.

## What Gets Tracked

Every time you select or reject an image, the system records:

```python
{
  "prompt": "beautiful woman on beach at sunset",
  "keywords": ["beautiful", "woman", "beach", "sunset"],
  "checkpoint": "epicrealismXL_pureFix.safetensors",
  "loras": [{"name": "anime_v2", "strength": 0.7}],
  "action": "selected",  # or "rejected"
  "stage": 0,
  "timestamp": "2026-02-09T17:00:00Z"
}
```

## Multi-Dimensional Learning

The system tracks preferences across multiple dimensions:

### 1. Keyword × Checkpoint Affinity
```
"beach" + "epicrealismXL" → 75% selection rate (15/20 selected)
"forest" + "epicrealismXL" → 11% selection rate (2/18 selected)
```
**Learning:** epicrealismXL is great for beaches but bad for forests.

### 2. Keyword × LoRA Affinity
```
"anime" + "anime_style_v2" → 80% selection rate (12/15)
"realistic" + "anime_style_v2" → 20% selection rate (3/15)
```
**Learning:** anime_style_v2 works well for anime prompts but not realistic ones.

### 3. Checkpoint × LoRA Compatibility
```
"epicrealismXL" + "anime_v2" → 32% selection rate (8/25)
```
**Learning:** This checkpoint + LoRA combination clashes.

### 4. Overall Quality
```
"epicrealismXL" → 65% overall selection rate
```
**Learning:** This checkpoint performs well in general.

## How It Works

### Recording Preferences

Happens automatically when you:
- Click "Advance" (records selections)
- Click "Reject All" (records rejections)

```python
# Backend automatically calls:
await preference_learning.record_preference(
    prompt="beach sunset",
    checkpoint="epicrealismXL",
    loras=[],
    selected=True,
    # ... other context
)
```

### Using Learning for Recommendations

When you generate with same keywords:

```python
# Get best checkpoint for "beach sunset"
checkpoint, confidence = await preference_learning.recommend_checkpoint(
    prompt="beach sunset",
    available_checkpoints=["epicrealismXL", "realvisxlV40", ...]
)
# Returns: ("epicrealismXL", 0.75) because you selected 75% of beach images from this checkpoint
```

### Confidence Scoring

The system blends personal history with global stats:

```python
confidence = min(sample_size / 20.0, 1.0)

# 0 samples → confidence = 0.0 (use global stats)
# 5 samples → confidence = 0.25 (blend 25% personal, 75% global)
# 20+ samples → confidence = 1.0 (fully trust personal data)
```

## Database Schema

### `user_preferences` Table
Detailed records of every selection/rejection:
- Prompt, keywords, checkpoint, LoRAs
- Action (selected/rejected), feedback text
- Stage, session, timestamp
- Optional: vision analysis description

**Size:** ~500 bytes per record, 5MB for 10K generations

### `preference_stats` Table
Aggregated statistics for fast lookups:
- Stat type (keyword_checkpoint, keyword_lora, checkpoint_lora)
- Key ("beach:epicrealismXL")
- Selected count, total count, selection rate
- Confidence score

**Size:** ~200 bytes per stat, grows slowly (only unique combinations)

### `image_cleanup` Table
Track rejected images for cleanup:
- Once vision analysis is done on rejected image → safe to delete
- Keeps your disk usage under control

## API Endpoints

### Get Statistics
```bash
curl http://localhost:8001/api/preferences/stats
```

Returns:
```json
{
  "total_preferences": 1523,
  "action_counts": {
    "selected": 892,
    "rejected": 631
  },
  "top_checkpoints": [
    {
      "checkpoint": "epicrealismXL_pureFix.safetensors",
      "selection_rate": 0.75,
      "total": 120,
      "selected": 90
    }
  ]
}
```

### Export All Preferences
```bash
curl http://localhost:8001/api/preferences/export > my_preferences.json
```

Portable JSON format for backup/sharing:
```json
{
  "version": "1.0",
  "total_preferences": 1523,
  "preferences": [...],
  "stats": [...]
}
```

### Get Checkpoint Recommendation
```bash
curl "http://localhost:8001/api/preferences/recommend/checkpoint?prompt=beach+sunset"
```

Returns:
```json
{
  "checkpoint": "epicrealismXL_pureFix.safetensors",
  "confidence": 0.75
}
```

### Get LoRA Recommendations
```bash
curl "http://localhost:8001/api/preferences/recommend/loras?prompt=beach+sunset&checkpoint=epicrealismXL&count=3"
```

Returns:
```json
[
  {"lora": "detailed_v2", "score": 0.8},
  {"lora": "sunset_style", "score": 0.72},
  {"lora": "realistic_light", "score": 0.65}
]
```

## Data Privacy

✅ **All data stays local** - No cloud sync, no external services
✅ **SQLite database** - Single file in `data/preferences.db`
✅ **Portable** - Export as JSON, import on new machine
✅ **Your choice on images** - Rejected images can be auto-deleted after vision analysis

## Storage Estimates

```
10,000 generations:
- Preferences: ~5 MB
- Stats: ~200 KB
- Total: ~5.2 MB

100,000 generations:
- Preferences: ~50 MB
- Stats: ~500 KB
- Total: ~50 MB
```

Linear growth, very manageable.

## Future Enhancements

### Phase 2: Explore Mode Integration
- Use preference learning to score checkpoints in Explore Mode
- Distribute batch across top 3 scoring checkpoints instead of random

### Phase 3: Smart LoRA Selection
- Auto-enable LoRAs you consistently select
- Avoid LoRA + checkpoint combinations you reject

### Phase 4: Style Preference Detection
- Detect if you prefer realistic vs anime style
- Detect if you prefer bright vs dark lighting
- Use style preferences to recommend checkpoints

### Phase 5: Semantic Keyword Matching
- Use LLM to extract semantic concepts from prompts
- "sunset on beach" and "ocean at dusk" treated as similar
- Better generalization from limited data

## Current Status

✅ **Database schema created** - Ready to store preferences
✅ **Recording working** - Selections/rejections tracked automatically
✅ **API endpoints** - Stats, export, recommendations available
✅ **Vision integration** - Optional vision analysis of selected/rejected images

⏳ **Not yet integrated:**
- Explore Mode doesn't use preferences yet
- Auto-LoRA doesn't use preferences yet
- No UI to display learning stats yet

## Next Steps

1. Integrate preference scoring into Explore Mode checkpoint distribution
2. Add confidence indicators to UI ("High confidence" vs "Exploring")
3. Show why a checkpoint was chosen: "Based on your 15 'beach' selections"
4. Auto-cleanup rejected images after vision analysis
5. Add UI panel to view top checkpoints, selection rates, export data
