# Vision Analysis Experiment

## What is this?

An **experimental read-only feature** that uses Ollama's vision models to analyze selected and rejected images. This helps understand:
- What you liked about selected images
- What went wrong with rejected images
- Whether vision analysis can help improve future generations

**Important:** This is currently **logging only** - it doesn't change prompts, settings, or generation behavior. It just logs what it sees.

## Prerequisites

### 1. Install Ollama

Download and install Ollama from https://ollama.com/

### 2. Pull the vision model

```bash
ollama pull llava:7b
```

This downloads a 7B parameter vision model (~4GB). Alternatives:
- `llava:13b` - Better quality, larger size (~7GB)
- `bakllava:7b` - Specialized for detailed descriptions

### 3. Verify Ollama is running

```bash
ollama list
```

Should show `llava:7b` in the list.

## Enable Vision Analysis

### Method 1: Environment Variable

Set environment variable before starting backend:

```bash
export ENABLE_VISION=true
docker compose up -d
```

### Method 2: Code modification

Edit `backend/app/main.py`, uncomment this line:

```python
if ollama_available:
    logger.info("Ollama vision available - enable with ENABLE_VISION=true")
    vision_analysis.enabled = True  # <-- Uncomment this line
```

## What Gets Logged

### When you select images:

```
User selected 3 images with prompt 'beach sunset beautiful woman'. Vision analysis found:
  Image 1: A woman with long dark hair stands on a sandy beach at sunset...
  Image 2: Portrait of a woman on the beach during golden hour with warm lighting...
  Image 3: Beach scene at dusk with a silhouetted figure and orange sky...
```

### When you reject all images:

```
User rejected images with prompt 'forest mystical fantasy' (feedback: 'too dark'). Vision analysis found:
  Rejected image 1: A dark forest scene with heavy shadows and muted colors...
  Rejected image 2: Dense woodland with low visibility and dark green tones...
  Rejected image 3: Nighttime forest with minimal lighting and silhouetted trees...
```

## Checking Logs

### Docker logs:

```bash
docker compose logs backend | grep "Vision analysis"
```

### Native logs:

Check console output when running `uvicorn` directly.

## Performance Impact

- **Minimal when disabled** (default)
- **Small when enabled**: ~2-5 seconds per image analysis
  - Analysis runs in background (async)
  - Doesn't block generation or feedback responses
  - Only analyzes up to 5 selected / 3 rejected images

## Future Plans

Once we validate vision analysis is working and helpful:

1. **Extract themes** - Identify common elements in selected images
2. **Detect quality issues** - Understand why images were rejected
3. **Smart prompt refinement** - Use vision + LLM to suggest better prompts
4. **Preference learning** - Correlate vision analysis with checkpoint/LoRA performance

## Troubleshooting

### "Ollama not available"

- Check Ollama is running: `ollama serve` (if not running as service)
- Check URL is correct (default: `http://localhost:11434`)
- Try: `curl http://localhost:11434/api/tags`

### "Vision model not found"

- Pull the model: `ollama pull llava:7b`
- Verify: `ollama list`

### "Vision analysis failed"

- Check image paths are accessible
- Check Ollama has enough RAM (~8GB recommended for 7B model)
- Check logs for specific error messages

## Disable Vision Analysis

Set `vision_analysis.enabled = False` in `main.py` or restart without `ENABLE_VISION=true`.

Vision analysis will gracefully disable and have zero performance impact.
