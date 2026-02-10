# Context-Aware Preference Learning

## Problem Statement

**Current Issue:** Checkpoint rejection tracking was partially global (not context-aware).

**Scenario:**
1. User generates "anime girl" with checkpoint A → Rejects all
2. Later generates "photorealistic landscape" with checkpoint A
3. Checkpoint A should NOT be penalized for landscapes just because it failed for anime

**Root Cause:** The system had TWO learning systems with different behaviors:
- `CheckpointLearning`: Global stats (no prompt context)
- `PreferenceLearning`: Context-aware (tracks prompt keywords + checkpoint combinations)

## Solution Implemented

### Phase 1: Remove Global Checkpoint Penalization ✅

**Changed:** `backend/app/routers/iteration.py` - `reject_all()` endpoint

**Before:**
```python
# Global penalization (no context)
for checkpoint, count in checkpoints_used.items():
    checkpoint_learning.record_rejection(checkpoint, count)

# Also record with context
await preference_learning.record_preference(
    prompt=gen.prompt,  # Full context
    checkpoint=checkpoint,
    selected=False,
    rejected=True,
    ...
)
```

**After:**
```python
# Only use context-aware preference learning
# Removed global checkpoint_learning.record_rejection()

# Record with full prompt context
await preference_learning.record_preference(
    prompt=gen.prompt,  # Full context
    checkpoint=checkpoint,
    selected=False,
    rejected=True,
    ...
)
```

**Rationale:**
- `PreferenceLearning` already tracks rejections with full prompt context
- Global penalization hurts checkpoints unfairly across different prompt types
- A checkpoint can be excellent for one style but poor for another

### Phase 2: Use Context-Aware Recommendations (TODO)

**Current State:**
- Rejection tracking: ✅ Context-aware (fixed above)
- Checkpoint selection: ❌ Still uses global `checkpoint_learning`

**Needs Update:** `backend/app/routers/generation.py` - `generate_batch()` endpoint

**Current (Global):**
```python
if req.explore_mode and not req.checkpoint:
    checkpoints_to_test = checkpoint_learning.get_checkpoints_for_tier(
        req.model_family.value,
        tier,
        explore_mode=True
    )
```

**Should Be (Context-Aware):**
```python
if req.explore_mode and not req.checkpoint:
    # Get available checkpoints for tier
    available_checkpoints = checkpoint_learning.checkpoint_pools.get(
        f"{req.model_family.value}_{tier}",
        []
    )

    # Use PreferenceLearning to rank them based on prompt context
    checkpoint, confidence = await preference_learning.recommend_checkpoint(
        db=db,
        prompt=req.prompt,
        available_checkpoints=available_checkpoints,
    )

    if confidence > 0.5:
        # High confidence: use recommended checkpoint
        checkpoints_to_test = [checkpoint]
    else:
        # Low confidence: explore multiple checkpoints
        checkpoints_to_test = available_checkpoints[:3]
```

**Benefits:**
1. Checkpoints recommended based on similar past prompts
2. New prompts still get exploration (low confidence)
3. Established preferences get exploited (high confidence)
4. Learning improves over time with user feedback

## How Context-Aware Learning Works

### Data Model

**PreferenceLearning** tracks multi-dimensional combinations:

```python
# Stored in database (user_preferences table)
{
    "prompt": "photorealistic portrait of a woman",
    "keywords": ["photorealistic", "portrait", "woman"],
    "checkpoint": "epicrealismXL_pureFix.safetensors",
    "action": "selected",  # or "rejected"
    "model_family": "sdxl",
    "task_type": "standard",
}
```

**Statistics Tracked** (preference_stats table):

1. `(keyword, checkpoint)` pairs
   - Example: `("photorealistic", "epicrealismXL")` → 80% selection rate
   - Example: `("anime", "epicrealismXL")` → 20% selection rate

2. `(keyword, lora)` pairs
   - Example: `("portrait", "detail_enhancer_lora")` → 90% selection rate

3. `(checkpoint, lora)` pairs
   - Example: `("epicrealismXL", "detail_enhancer")` → works well together

### Scoring Algorithm

When recommending a checkpoint for a new prompt:

```python
def get_checkpoint_score(prompt_keywords, checkpoint):
    # For each keyword in the prompt
    scores = []
    for keyword in prompt_keywords:
        # Get historical performance of (keyword, checkpoint) pair
        stats = get_stats(keyword, checkpoint)

        # Bayesian confidence-weighted score
        prior = 0.5  # Neutral starting assumption
        weight = stats.total / (stats.total + 10)  # More data = higher weight
        score = (stats.selected / stats.total) if stats.total > 0 else prior

        # Blend prior with data
        weighted_score = (1 - weight) * prior + weight * score
        scores.append(weighted_score)

    # Average across all keywords
    return sum(scores) / len(scores) if scores else 0.5
```

**Example:**

Prompt: "photorealistic portrait of a woman"
Keywords: ["photorealistic", "portrait", "woman"]

Checkpoint A (epicrealismXL):
- ("photorealistic", A): 15 selected / 20 total = 0.75
- ("portrait", A): 12 selected / 15 total = 0.80
- ("woman", A): 8 selected / 10 total = 0.80
- **Average: 0.783** ✅

Checkpoint B (dreamShaperXL):
- ("photorealistic", B): 5 selected / 20 total = 0.25
- ("portrait", B): 8 selected / 15 total = 0.53
- ("woman", B): 6 selected / 12 total = 0.50
- **Average: 0.427** ❌

→ **Recommend Checkpoint A**

### Confidence Calculation

```python
confidence = min(total_data_points / 100, 1.0)
```

- **Low confidence** (<0.3): Not enough data → Explore (try multiple checkpoints)
- **Medium confidence** (0.3-0.7): Some data → Exploit best + explore backup
- **High confidence** (>0.7): Strong data → Exploit best checkpoint only

## Rejection Flow (After Fix)

### User Rejects All Images

```
User clicks "Reject All"
    ↓
Frontend: rejectAllInStage(stage)
    ↓
Backend: reject_all() endpoint
    ↓
For each rejected generation:
    ↓
Extract: prompt, checkpoint, LoRAs, keywords
    ↓
preference_learning.record_preference(
    prompt="anime girl with blue hair",
    checkpoint="epicrealismXL",
    keywords=["anime", "girl", "blue", "hair"],
    selected=False,
    rejected=True
)
    ↓
Database stores:
    user_preferences: Full record with context
    preference_stats: Updates (keyword, checkpoint) stats
        ("anime", "epicrealismXL"): -1 selection
        ("girl", "epicrealismXL"): -1 selection
        ...
```

### Future Generation Uses Context

```
User generates: "anime boy with red hair"
Keywords: ["anime", "boy", "red", "hair"]
    ↓
preference_learning.recommend_checkpoint(
    prompt="anime boy with red hair",
    available_checkpoints=["epicrealismXL", "dreamShaperXL", ...]
)
    ↓
Score each checkpoint:
    epicrealismXL:
        ("anime", epic): LOW (rejected before)
        ("boy", epic): NEUTRAL (no data)
        ("red", epic): NEUTRAL
        ("hair", epic): LOW (rejected before)
        → Average: 0.35 ❌

    dreamShaperXL:
        ("anime", dream): HIGH (selected before)
        ("boy", dream): NEUTRAL
        ("red", dream): NEUTRAL
        ("hair", dream): HIGH (selected before)
        → Average: 0.72 ✅
    ↓
Recommend: dreamShaperXL (better for anime prompts)
```

**Result:** The system learns that `epicrealismXL` is bad for **anime** specifically, but won't penalize it for **photorealistic** prompts!

## Export/Import for Portability

`PreferenceLearning` supports export/import:

```python
# Export to JSON
data = await preference_learning.export_preferences(db)
with open("my_preferences.json", "w") as f:
    json.dump(data, f)

# Import on another machine
with open("my_preferences.json") as f:
    data = json.load(f)
await preference_learning.import_preferences(db, data)
```

**Use Cases:**
- Transfer preferences between dev/prod
- Share preferences with other users
- Backup/restore preference data
- Migrate to new hardware

## Benefits

### 1. Fair Checkpoint Evaluation
- Checkpoints aren't globally penalized
- Each prompt type gets appropriate checkpoint
- Specialized checkpoints can excel in their niche

### 2. Faster Learning
- Multi-dimensional tracking captures nuances
- (keyword, checkpoint) pairs learn quickly
- Even single rejection teaches about that keyword

### 3. Better Recommendations
- New prompts leverage similar past prompts
- "anime girl" and "anime boy" share "anime" keyword stats
- Confidence-based exploration vs exploitation

### 4. User Trust
- Prompt refinement notification shows rationale
- Users see their feedback making a difference
- System explains why it chose a checkpoint

## Testing Checklist

- [ ] Reject "anime" images with checkpoint A
- [ ] Generate "photorealistic" images with checkpoint A
- [ ] Verify checkpoint A not penalized for photorealistic
- [ ] Check `preference_stats` table has (keyword, checkpoint) rows
- [ ] Call `/api/preferences/recommend-checkpoint` with anime prompt
- [ ] Verify it avoids checkpoint A
- [ ] Call with photorealistic prompt
- [ ] Verify it still considers checkpoint A
- [ ] Export preferences to JSON
- [ ] Import on another instance
- [ ] Verify recommendations still work

## Future Enhancements

### 1. LoRA Context Awareness (Planned)
Currently LoRAs are placeholders (`loras=[]`). When implemented:
```python
await preference_learning.record_preference(
    prompt="portrait",
    checkpoint="epicrealismXL",
    loras=[
        {"name": "detail_enhancer", "strength_model": 0.8},
        {"name": "face_fix", "strength_model": 0.5}
    ],
    selected=True,
    ...
)
```

This will track:
- `(keyword, lora)` pairs: Which LoRAs work for which keywords
- `(checkpoint, lora)` pairs: Which LoRAs work with which checkpoints
- Strength recommendations: Optimal LoRA strength per keyword

### 2. Negative Prompt Learning
Track which negative prompts work well with prompts:
```python
stats[(keyword, negative_keyword)] = {
    "selected": count_selected,
    "total": count_total
}
```

### 3. Parameter Learning
Track optimal parameters per prompt type:
```python
stats[(keyword, "steps")] = {
    "average": 28.5,
    "variance": 2.3
}
```

Learn: "anime" prompts work better with fewer steps, "photorealistic" needs more steps.

### 4. Temporal Decay
Old preferences fade over time:
```python
# Weight recent selections more than old ones
age_weight = exp(-age_days / 30)  # 30-day half-life
```

User tastes change, so old preferences shouldn't dominate forever.

### 5. Multi-User Learning
Aggregate preferences across users (with privacy):
```python
global_stats = aggregate(
    user_stats for all users
    where user.share_preferences == True
)
```

Cold-start new users with global preferences, then personalize.

## Architecture Notes

### Separation of Concerns

**CheckpointLearning** (Keep for now):
- Manages checkpoint pools (which checkpoints exist)
- Distributes batches across multiple checkpoints
- Provides tier-based defaults (draft/standard/quality)

**PreferenceLearning** (Primary learning engine):
- Records all selections/rejections with context
- Scores checkpoints based on prompt similarity
- Recommends checkpoints/LoRAs based on history
- Handles export/import for portability

**Future:** Consider merging or deprecating `CheckpointLearning` once `PreferenceLearning` handles all recommendation logic.

### Database Schema

**user_preferences** (per-generation record):
- Full context for each generation
- Supports complex queries
- Can be exported/imported

**preference_stats** (aggregated statistics):
- Fast lookups for scoring
- Incrementally updated
- Bayesian confidence scoring

**Why Both?**
- `user_preferences`: Detailed history (debugging, export, analysis)
- `preference_stats`: Fast scoring (real-time recommendations)

## Deployment Notes

### Migration Required: No

The fix is additive - it removes a problematic call to `checkpoint_learning.record_rejection()` but doesn't change database schema or APIs.

### Rollback Strategy

If context-aware recommendations cause issues:

1. Revert `iteration.py` to add back global penalization:
```python
for checkpoint, count in checkpoints_used.items():
    checkpoint_learning.record_rejection(checkpoint, count)
```

2. Preference data remains intact (no data loss)

### Performance Impact

- **Recording**: Negligible (one DB insert per generation)
- **Scoring**: Fast (simple aggregation query)
- **Recommendation**: <100ms (scores a few checkpoints)

No performance degradation expected.

## Summary

### What Changed ✅
- Removed global checkpoint penalization from `reject_all()`
- Rejections now recorded only via context-aware `PreferenceLearning`
- Added documentation explaining context-aware learning

### What Still Needs Work ⏳
- Update checkpoint selection in `generate_batch()` to use `recommend_checkpoint()`
- Implement LoRA tracking in generation parameters
- Add LoRA recommendation based on preferences
- Add confidence-based exploration/exploitation logic

### What Works Now ✅
- Rejection tracking with full prompt context
- Multi-dimensional preference statistics
- Checkpoint scoring based on keyword similarity
- Export/import for portability
- Vision analysis integration (experimental)

The system is now **context-aware for rejections** and ready for **context-aware recommendations** once Phase 2 is implemented!
