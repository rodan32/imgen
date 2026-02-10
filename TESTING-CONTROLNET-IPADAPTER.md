# Testing ControlNet & IP-Adapter Setup

## Quick Verification After Download

### 1. Verify Files Are in Place

```bash
# Check IP-Adapter models
ls ComfyUI/models/ipadapter/
# Should see:
# - ip-adapter-faceid-plus_sd15.bin
# - ip-adapter-faceid-plusv2_sdxl.bin

# Check CLIP Vision (REQUIRED!)
ls ComfyUI/models/clip_vision/
# Should see:
# - CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors

# Check ControlNet models
ls ComfyUI/models/controlnet/
# Should see:
# - control_v11p_sd15_openpose.pth
# - control_v11f1p_sd15_depth.pth
# - control_v11p_sd15_canny.pth
# - diffusers_xl_canny_full.safetensors
# - diffusers_xl_depth_full.safetensors
```

### 2. Test in ComfyUI (Simple Face Preservation)

**Minimal IP-Adapter Test Workflow:**

1. Open ComfyUI web interface
2. Add these nodes:
   - `CheckpointLoaderSimple` → Load your SD1.5 checkpoint
   - `CLIPVisionLoader` → Load `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors`
   - `IPAdapterModelLoader` → Load `ip-adapter-faceid-plus_sd15.bin`
   - `LoadImage` → Load a face reference image
   - `CLIPVisionEncode` → Connect CLIP vision + image
   - `IPAdapterApply` → Connect all inputs
   - `CLIPTextEncode` (positive) → Your prompt
   - `CLIPTextEncode` (negative) → Negative prompt
   - `KSampler` → Use IP-Adapter modified model
   - `VAEDecode` → Decode latent
   - `SaveImage` → Output

3. Queue prompt
4. **Success:** Generated image has same face as reference
5. **Failure:** Check ComfyUI console for errors about missing models

### 3. Test in ComfyUI (Simple Pose Control)

**Minimal ControlNet Test Workflow:**

1. Add these nodes:
   - `CheckpointLoaderSimple` → Load SD1.5 checkpoint
   - `ControlNetLoader` → Load `control_v11p_sd15_openpose.pth`
   - `LoadImage` → Load a pose reference image
   - `OpenposePreprocessor` → Process reference image
   - `ControlNetApply` → Apply to conditioning
   - `CLIPTextEncode` (positive/negative)
   - `KSampler` → Use ControlNet conditioning
   - `VAEDecode` → Decode
   - `SaveImage` → Output

2. Queue prompt
3. **Success:** Generated image matches pose from reference
4. **Failure:** Check if preprocessor models downloaded (ComfyUI Manager should auto-prompt)

### 4. Test Combined (Face + Pose)

**This is what Concept Builder will use!**

Chain both:
1. IP-Adapter modifies the model (face consistency)
2. ControlNet modifies the conditioning (pose guidance)
3. KSampler uses both

Expected result: Same face from reference + same pose from reference + your prompt style

---

## Common Issues & Fixes

### Issue: "CLIP vision model not found"
**Fix:**
- Ensure `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` is in `models/clip_vision/`
- Restart ComfyUI after adding the file
- File must be exactly this name (case-sensitive)

### Issue: "Cannot load IP-Adapter model"
**Fix:**
- Check file size matches expected (~143MB for faceid-plus_sd15)
- Verify download completed (not corrupted)
- Ensure it's a `.bin` file, not `.safetensors`

### Issue: "ControlNet preprocessor missing"
**Fix:**
- Install ComfyUI Manager if not installed
- Go to Manager → Install Missing Custom Nodes
- Look for "comfyui_controlnet_aux"
- Restart ComfyUI

### Issue: "OpenPose preprocessor fails"
**Fix:**
- The preprocessor downloads additional models on first use
- Check `custom_nodes/comfyui_controlnet_aux/ckpts/` for downloaded files
- May take 1-2 minutes on first run
- Check ComfyUI console for download progress

### Issue: "Out of memory with IP-Adapter + ControlNet"
**Fix:**
- Reduce image resolution (try 512x512 for SD1.5, 832x832 for SDXL)
- Lower batch size to 1
- Use `--lowvram` or `--medvram` flags when starting ComfyUI
- 3050Ti (4GB): Use SD1.5 only, avoid combining IP-Adapter + ControlNet
- 8GB+ VRAM: Should handle both together

---

## Performance Expectations

### Generation Time Increase:
- **IP-Adapter alone:** +10-20% generation time (CLIP vision encoding)
- **ControlNet alone:** +20-30% generation time (preprocessing + conditioning)
- **Both combined:** +30-50% generation time
- **Worth it:** Much better control over output!

### VRAM Usage:
- **SD1.5 base:** ~2-3GB
- **+ IP-Adapter:** +500MB
- **+ ControlNet:** +500-800MB
- **+ Both:** ~4-5GB total
- **SDXL base:** ~6-7GB
- **+ IP-Adapter:** +700MB
- **+ ControlNet:** +800MB
- **+ Both:** ~8-9GB total

### GPU Tier Recommendations:
- **3050Ti (4GB):** SD1.5 only, use IP-Adapter OR ControlNet (not both)
- **3060 (12GB):** SD1.5 + both, or SDXL + one of them
- **4060Ti (8GB):** SD1.5 + both comfortably, SDXL + both with care
- **5060Ti (16GB):** SDXL + both + batch generation, no problem

---

## Integration Checklist for Backend

Once models are verified working in ComfyUI:

### Backend Tasks (for Concept Builder integration):

1. **Create workflow templates:**
   - [ ] `workflow_sd15_base.json` (no references)
   - [ ] `workflow_sd15_ipadapter.json` (face preservation)
   - [ ] `workflow_sd15_controlnet_pose.json` (pose control)
   - [ ] `workflow_sd15_combined.json` (face + pose)
   - [ ] Same for SDXL variants

2. **Extend WorkflowEngine:**
   - [ ] Detect reference images in generation request
   - [ ] Select correct template based on reference types
   - [ ] Inject reference image paths into workflow
   - [ ] Set strength parameters from request

3. **Add reference upload endpoints:**
   - [ ] `POST /api/references/upload` - Upload and store reference
   - [ ] `GET /api/references/{ref_id}` - Retrieve reference
   - [ ] `DELETE /api/references/{ref_id}` - Delete reference
   - [ ] `PATCH /api/references/{ref_id}/strength` - Update strength

4. **Update model sync:**
   - [ ] Add IP-Adapter models to discovery
   - [ ] Add ControlNet models to discovery
   - [ ] Add CLIP vision to discovery
   - [ ] Update node constraints (3050Ti: no SDXL IP-Adapter)

5. **Test generation flow:**
   - [ ] Generate with face reference (IP-Adapter)
   - [ ] Generate with pose reference (ControlNet)
   - [ ] Generate with both combined
   - [ ] Verify locked fields work correctly
   - [ ] Test strength adjustments (0.0 - 1.0)

---

## Example Workflow JSON Snippets

### IP-Adapter Node Chain:
```json
{
  "10": {
    "class_type": "IPAdapterModelLoader",
    "inputs": {
      "ipadapter_file": "ip-adapter-faceid-plus_sd15.bin"
    }
  },
  "11": {
    "class_type": "CLIPVisionLoader",
    "inputs": {
      "clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"
    }
  },
  "12": {
    "class_type": "LoadImage",
    "inputs": {
      "image": "{{reference_face_path}}"
    }
  },
  "13": {
    "class_type": "CLIPVisionEncode",
    "inputs": {
      "clip_vision": ["11", 0],
      "image": ["12", 0]
    }
  },
  "14": {
    "class_type": "IPAdapterApply",
    "inputs": {
      "ipadapter": ["10", 0],
      "image_embed": ["13", 0],
      "model": ["1", 0],
      "weight": {{reference_face_strength}}
    }
  }
}
```

### ControlNet Node Chain:
```json
{
  "20": {
    "class_type": "ControlNetLoader",
    "inputs": {
      "control_net_name": "control_v11p_sd15_openpose.pth"
    }
  },
  "21": {
    "class_type": "LoadImage",
    "inputs": {
      "image": "{{reference_pose_path}}"
    }
  },
  "22": {
    "class_type": "OpenposePreprocessor",
    "inputs": {
      "image": ["21", 0],
      "detect_hand": "enable",
      "detect_body": "enable",
      "detect_face": "enable"
    }
  },
  "23": {
    "class_type": "ControlNetApply",
    "inputs": {
      "conditioning": ["2", 0],
      "control_net": ["20", 0],
      "image": ["22", 0],
      "strength": {{reference_pose_strength}}
    }
  }
}
```

### Combined (Model flow):
```
Checkpoint → IP-Adapter → KSampler
             ↑                ↑
        Face Reference   ControlNet Conditioning
                              ↑
                         Pose Reference
```

---

## Next Steps After Download Complete

1. ✅ Copy models to each ComfyUI node
2. ✅ Test basic IP-Adapter workflow in ComfyUI web UI
3. ✅ Test basic ControlNet workflow in ComfyUI web UI
4. ✅ Test combined workflow (face + pose)
5. ✅ Sync models to NAS at `192.168.0.103:/volume1/comfyui/models/`
6. ✅ Run model discovery on backend to detect new models
7. ✅ Create workflow templates for backend
8. ✅ Implement reference upload endpoints
9. ✅ Test end-to-end from Concept Builder UI

Let me know when downloads complete and we can test in ComfyUI!
