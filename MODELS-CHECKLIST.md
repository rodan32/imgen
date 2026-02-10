# ComfyUI Models Checklist for Concept Builder

## 🎭 IP-Adapter Models (Face/Character Preservation)

### SD 1.5 (Essential for 3050Ti, 3060, 4060Ti, 5060Ti)
- **ip-adapter-faceid-plus_sd15.bin** ⭐ RECOMMENDED
  - Best for face consistency with ID preservation
  - Works with SD1.5 checkpoints
  - Location: `ComfyUI/models/ipadapter/`
  - Download: https://huggingface.co/h94/IP-Adapter-FaceID/tree/main

- **ip-adapter-faceid-plusv2_sd15.bin** (Alternative/Upgrade)
  - Improved version of faceid-plus
  - Better at handling different angles
  - Same location
  - Download: https://huggingface.co/h94/IP-Adapter-FaceID/tree/main

- **ip-adapter_sd15.bin** (Fallback - General Purpose)
  - Works for general image style transfer, not just faces
  - Less specialized but more versatile
  - Download: https://huggingface.co/h94/IP-Adapter/tree/main

### SDXL (Essential for 3060, 4060Ti, 5060Ti - skip for 3050Ti)
- **ip-adapter-faceid-plusv2_sdxl.bin** ⭐ RECOMMENDED
  - Best for SDXL face preservation
  - Higher quality than SD1.5 version
  - Location: `ComfyUI/models/ipadapter/`
  - Download: https://huggingface.co/h94/IP-Adapter-FaceID/tree/main

- **ip-adapter_sdxl.bin** (Fallback - General Purpose)
  - General SDXL IP-Adapter
  - Download: https://huggingface.co/h94/IP-Adapter/tree/main

---

## 🧍 ControlNet Models

### SD 1.5 ControlNets (Essential for ALL nodes)

**Pose Control:**
- **control_v11p_sd15_openpose.pth** ⭐ ESSENTIAL
  - Body pose detection and guidance
  - Location: `ComfyUI/models/controlnet/`
  - Download: https://huggingface.co/lllyasviel/ControlNet-v1-1/tree/main

**Depth Control:**
- **control_v11f1p_sd15_depth.pth** ⭐ RECOMMENDED
  - Depth/distance preservation
  - Location: `ComfyUI/models/controlnet/`
  - Download: https://huggingface.co/lllyasviel/ControlNet-v1-1/tree/main

**Edge/Line Control:**
- **control_v11p_sd15_canny.pth** ⭐ RECOMMENDED
  - Sharp edge detection
  - Location: `ComfyUI/models/controlnet/`
  - Download: https://huggingface.co/lllyasviel/ControlNet-v1-1/tree/main

- **control_v11p_sd15_softedge.pth** (Alternative to Canny)
  - Softer edge detection
  - Better for painterly styles
  - Download: https://huggingface.co/lllyasviel/ControlNet-v1-1/tree/main

**Composition Control:**
- **control_v11p_sd15_mlsd.pth** (Optional)
  - Straight line detection (architecture, interiors)
  - Download: https://huggingface.co/lllyasviel/ControlNet-v1-1/tree/main

**Other Useful ControlNets (Optional):**
- **control_v11p_sd15_normalbae.pth** - Normal map control
- **control_v11p_sd15_lineart.pth** - Line art extraction
- **control_v11p_sd15_scribble.pth** - Sketch-based control

### SDXL ControlNets (Essential for 3060, 4060Ti, 5060Ti)

**Pose Control:**
- **diffusers_xl_canny_full.safetensors** ⭐ RECOMMENDED
  - SDXL edge/structure control (often used for pose too)
  - Location: `ComfyUI/models/controlnet/`
  - Download: https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0/tree/main

- **thibaud_xl_openpose.safetensors** (Alternative - if available)
  - SDXL OpenPose control
  - Check ComfyUI community for latest SDXL pose models

**Depth Control:**
- **diffusers_xl_depth_full.safetensors** ⭐ RECOMMENDED
  - SDXL depth control
  - Download: https://huggingface.co/diffusers/controlnet-depth-sdxl-1.0/tree/main

**Note:** SDXL ControlNet ecosystem is less mature than SD1.5, so you may use SD1.5 ControlNets with SDXL checkpoints in some ComfyUI setups (with reduced effectiveness).

---

## 👁️ CLIP Vision Models (REQUIRED for IP-Adapter)

### Essential for ALL IP-Adapter Usage

- **CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors** ⭐ ESSENTIAL
  - Required by IP-Adapter for image encoding
  - Works with both SD1.5 and SDXL IP-Adapters
  - Location: `ComfyUI/models/clip_vision/`
  - Download: https://huggingface.co/h94/IP-Adapter/tree/main
  - Size: ~3.8GB

- **CLIP-ViT-bigG-14-laion2B-39B-b160k.safetensors** (Alternative for SDXL)
  - Larger CLIP vision model
  - Better for SDXL IP-Adapters
  - Location: `ComfyUI/models/clip_vision/`
  - Download: https://huggingface.co/laion/CLIP-ViT-bigG-14-laion2B-39B-b160k
  - Size: ~6.8GB

**Priority:** Get `CLIP-ViT-H-14` first - it's required for any IP-Adapter to work.

---

## 📝 Text Encoders (For SDXL ONLY - SD1.5 has them in checkpoint)

### SDXL Text Encoders (Optional - usually included in SDXL checkpoints)

SDXL uses two text encoders:
1. **CLIP-ViT-L** (OpenAI CLIP)
2. **OpenCLIP-ViT-bigG** (LAION CLIP)

**Do you need separate text encoder files?**
- ❌ **NO** if your SDXL checkpoints are "full" or "base" versions (they include text encoders)
- ✅ **YES** if using "pruned" or "refiner" SDXL checkpoints

**Where to get them (if needed):**
- Included in: `stabilityai/stable-diffusion-xl-base-1.0` on HuggingFace
- Location: `ComfyUI/models/clip/`
- Files:
  - `clip_l.safetensors` (~492MB)
  - `t5xxl_fp16.safetensors` (~9.5GB - only for SDXL Turbo/Lightning)

**Recommendation:** Skip these unless you're using pruned checkpoints. Most SDXL checkpoints include them.

---

## 🔍 ControlNet Preprocessors (Auto-installed by ComfyUI Manager)

These are used to generate control images from reference images:

### Essential Preprocessors:
- **OpenPose Preprocessor** - Detects body pose from images
- **Depth Preprocessor** (MiDaS or Zoe Depth) - Generates depth maps
- **Canny Preprocessor** - Detects edges
- **MLSD Preprocessor** - Detects straight lines
- **SoftEdge Preprocessor** (HED or PiDiNet) - Soft edge detection

**Installation:** These are typically installed automatically when you:
1. Install ComfyUI Manager
2. Use a ControlNet node that requires a preprocessor
3. ComfyUI Manager prompts you to install missing preprocessor models

**Manual download (if needed):**
- Location: `ComfyUI/custom_nodes/comfyui_controlnet_aux/`
- Or use ComfyUI Manager: "Install Missing Custom Nodes"

---

## 📦 Priority Download Order

### Phase 1: Essential for Face Preservation (IP-Adapter)
1. ✅ **CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors** (Required for IP-Adapter)
2. ✅ **ip-adapter-faceid-plus_sd15.bin** (SD1.5 face preservation)
3. ✅ **ip-adapter-faceid-plusv2_sdxl.bin** (SDXL face preservation - skip for 3050Ti)

### Phase 2: Essential for Pose Control
4. ✅ **control_v11p_sd15_openpose.pth** (SD1.5 pose)
5. ✅ **diffusers_xl_canny_full.safetensors** or **thibaud_xl_openpose** (SDXL pose)

### Phase 3: Recommended for Depth/Edges
6. ✅ **control_v11f1p_sd15_depth.pth** (SD1.5 depth)
7. ✅ **control_v11p_sd15_canny.pth** (SD1.5 edges)
8. ✅ **diffusers_xl_depth_full.safetensors** (SDXL depth)

### Phase 4: Optional Enhancements
9. ⭐ **control_v11p_sd15_softedge.pth** (softer edge control)
10. ⭐ **control_v11p_sd15_mlsd.pth** (line detection)
11. ⭐ **ip-adapter_sd15.bin** / **ip-adapter_sdxl.bin** (general image style transfer)

---

## 💾 Storage Requirements

### Per Node Estimates:

**3050Ti (4GB VRAM) - SD1.5 Only:**
- CLIP Vision: ~3.8GB
- IP-Adapter FaceID Plus: ~143MB
- ControlNet OpenPose: ~1.4GB
- ControlNet Depth: ~1.4GB
- ControlNet Canny: ~1.4GB
- **Total: ~8GB disk space**

**3060/4060Ti/5060Ti (8GB+ VRAM) - SD1.5 + SDXL:**
- CLIP Vision: ~3.8GB
- IP-Adapter SD15: ~143MB
- IP-Adapter SDXL: ~721MB
- ControlNet SD15 (3 models): ~4.2GB
- ControlNet SDXL (2 models): ~5GB
- **Total: ~14GB disk space**

---

## 🗂️ Directory Structure

```
ComfyUI/
├── models/
│   ├── checkpoints/           # Your existing SD1.5/SDXL checkpoints
│   ├── loras/                 # Your existing LoRAs
│   ├── ipadapter/             # NEW: IP-Adapter models
│   │   ├── ip-adapter-faceid-plus_sd15.bin
│   │   ├── ip-adapter-faceid-plusv2_sd15.bin
│   │   ├── ip-adapter-faceid-plusv2_sdxl.bin
│   │   ├── ip-adapter_sd15.bin
│   │   └── ip-adapter_sdxl.bin
│   ├── clip_vision/           # NEW: CLIP vision encoders (REQUIRED for IP-Adapter)
│   │   ├── CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors
│   │   └── CLIP-ViT-bigG-14-laion2B-39B-b160k.safetensors
│   ├── controlnet/            # NEW: ControlNet models
│   │   ├── control_v11p_sd15_openpose.pth
│   │   ├── control_v11f1p_sd15_depth.pth
│   │   ├── control_v11p_sd15_canny.pth
│   │   ├── control_v11p_sd15_softedge.pth
│   │   ├── control_v11p_sd15_mlsd.pth
│   │   ├── diffusers_xl_canny_full.safetensors
│   │   └── diffusers_xl_depth_full.safetensors
│   └── clip/                  # Optional: Separate text encoders (only if using pruned SDXL)
│       ├── clip_l.safetensors
│       └── t5xxl_fp16.safetensors
└── custom_nodes/
    └── comfyui_controlnet_aux/  # ControlNet preprocessors (auto-installed)
```

---

## ✅ Quick Checklist

Copy this to track your downloads:

### Minimum Essential (IP-Adapter Face Preservation):
- [ ] CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors
- [ ] ip-adapter-faceid-plus_sd15.bin
- [ ] ip-adapter-faceid-plusv2_sdxl.bin (skip for 3050Ti)

### Minimum Essential (Pose Control):
- [ ] control_v11p_sd15_openpose.pth
- [ ] diffusers_xl_canny_full.safetensors (skip for 3050Ti)

### Recommended (Full Concept Builder):
- [ ] control_v11f1p_sd15_depth.pth
- [ ] control_v11p_sd15_canny.pth
- [ ] diffusers_xl_depth_full.safetensors (skip for 3050Ti)
- [ ] control_v11p_sd15_softedge.pth

### Optional (Advanced):
- [ ] control_v11p_sd15_mlsd.pth
- [ ] ip-adapter_sd15.bin (general style transfer)
- [ ] ip-adapter_sdxl.bin (general style transfer)
- [ ] CLIP-ViT-bigG-14 (better SDXL CLIP vision)

---

## 🚀 Testing After Download

1. **Test IP-Adapter:**
   - Open ComfyUI
   - Load an IP-Adapter node
   - Check if it can find the CLIP vision model
   - Upload a face image
   - Generate with face preservation

2. **Test ControlNet:**
   - Load a ControlNet loader node
   - Check if models appear in dropdown
   - Load an OpenPose preprocessor node
   - Upload a pose reference image
   - Generate with pose control

3. **Test Combined:**
   - Load both IP-Adapter AND ControlNet in same workflow
   - Generate with face + pose control simultaneously
   - This is what Concept Builder will use!

---

## 📚 Download Links Summary

**IP-Adapter:**
- https://huggingface.co/h94/IP-Adapter-FaceID
- https://huggingface.co/h94/IP-Adapter

**CLIP Vision:**
- https://huggingface.co/h94/IP-Adapter (includes CLIP-ViT-H-14)
- https://huggingface.co/laion/CLIP-ViT-bigG-14-laion2B-39B-b160k

**ControlNet SD1.5:**
- https://huggingface.co/lllyasviel/ControlNet-v1-1

**ControlNet SDXL:**
- https://huggingface.co/diffusers/controlnet-canny-sdxl-1.0
- https://huggingface.co/diffusers/controlnet-depth-sdxl-1.0

**Preprocessors:**
- Auto-installed via ComfyUI Manager
- Manual: https://github.com/Fannovel16/comfyui_controlnet_aux

---

## 🔧 NAS Sync Strategy

For your hybrid NAS + local cache setup:

1. **Store ALL models on NAS** at `192.168.0.103:/volume1/comfyui/models/`
2. **3050Ti cache:** Only IP-Adapter SD15 + ControlNet SD15 + CLIP-ViT-H-14
3. **Other nodes cache:** All IP-Adapters + All ControlNets + CLIP vision models
4. **Preprocessors:** Install on each node locally (they're small and node-specific)

This way, the model sync script you already built will handle distribution to each GPU node based on VRAM constraints.
