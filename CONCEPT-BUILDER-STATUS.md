# Concept Builder - Current Status

## ✅ Completed (Ready to Use)

### Frontend (100% Complete)
- [x] **ConceptBuilderFlow** - Main container with split-panel layout
- [x] **ConceptFields** - 7 structured fields (Subject, Pose, Background, Style, Lighting, Mood, Camera)
- [x] **Lock System** - Lock/unlock any field to preserve during iteration
- [x] **ReferenceImagePanel** - Upload and manage 5 types of reference images:
  - Face/Character (IP-Adapter)
  - Pose Control (ControlNet OpenPose)
  - Depth Map (ControlNet Depth)
  - Edge Control (ControlNet Canny)
  - Composition (ControlNet MLSD/Softedge)
- [x] **Strength Sliders** - Per-reference influence control (0-100%)
- [x] **Tab Navigation** - Switch between Concept Fields and References
- [x] **Generation Controls** - Aspect ratio, variation count, negative prompt
- [x] **Image Grid** - Display generated variations
- [x] **Selection & Refinement** - Select favorites, reject all, refine selected
- [x] **TypeScript Build** - Compiles without errors
- [x] **Integration** - Fully integrated into App.tsx

### Backend (Partially Complete)
- [x] **ModelSyncManager** - Discovers and tracks:
  - IP-Adapter models ✅
  - ControlNet models ✅
  - CLIP Vision models ✅ (just added)
  - All model types synced to NAS
- [x] **Model Discovery** - Queries ComfyUI for available models
- [x] **Node Constraints** - 3050Ti restricted to SD1.5, others support SDXL
- [x] **Cache Management** - Smart caching based on usage patterns
- [x] **Basic Generation** - Can generate images from Concept Builder (no references yet)

### Documentation (100% Complete)
- [x] **CONCEPT-BUILDER.md** - Complete design document with:
  - UI component architecture
  - Workflow explanations
  - Backend integration requirements
  - API endpoint specifications
  - Model requirements
  - Workflow template examples
  - Testing strategy
- [x] **MODELS-CHECKLIST.md** - Comprehensive download guide with:
  - Essential vs optional models
  - Download links for all models
  - Directory structure
  - Storage requirements per GPU tier
  - Quick checklist for tracking downloads
  - NAS sync strategy
- [x] **TESTING-CONTROLNET-IPADAPTER.md** - Testing guide with:
  - Verification steps
  - ComfyUI workflow examples
  - Common issues and fixes
  - Performance expectations
  - Integration checklist
  - Example workflow JSON snippets

### Scripts & Tools
- [x] **organize_models.py** - Helper script to move downloaded models to correct folders
  - Auto-categorizes by filename
  - Dry-run mode by default
  - Creates missing directories
  - Checks for duplicates

---

## ⏳ In Progress (Downloads)

### Models Currently Downloading
According to your status, these are being downloaded from HuggingFace:

**IP-Adapter Models:**
- [ ] ip-adapter-faceid-plus_sd15.bin (~143MB)
- [ ] ip-adapter-faceid-plusv2_sd15.bin (~143MB)
- [ ] ip-adapter-faceid-plusv2_sdxl.bin (~721MB)
- [ ] ip-adapter_sd15.bin (optional, ~143MB)
- [ ] ip-adapter_sdxl.bin (optional, ~721MB)

**CLIP Vision Models (CRITICAL!):**
- [ ] CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors (~3.8GB)
- [ ] CLIP-ViT-bigG-14-laion2B-39B-b160k.safetensors (optional, ~6.8GB)

**ControlNet SD1.5 Models:**
- [ ] control_v11p_sd15_openpose.pth (~1.4GB)
- [ ] control_v11f1p_sd15_depth.pth (~1.4GB)
- [ ] control_v11p_sd15_canny.pth (~1.4GB)
- [ ] control_v11p_sd15_softedge.pth (~1.4GB)
- [ ] control_v11p_sd15_mlsd.pth (~1.4GB)

**ControlNet SDXL Models:**
- [ ] diffusers_xl_canny_full.safetensors (~5GB)
- [ ] diffusers_xl_depth_full.safetensors (~5GB)

**Total Download Size:** ~25-30GB

---

## 📋 Next Steps (After Downloads Complete)

### Phase 1: Model Organization & Testing (1-2 hours)

1. **Organize Downloaded Models:**
   ```bash
   # Dry run first to see what would happen
   python scripts/organize_models.py ~/Downloads

   # Actually move files
   python scripts/organize_models.py ~/Downloads --execute --comfyui /path/to/ComfyUI
   ```

2. **Verify Models in ComfyUI:**
   - Start ComfyUI on one node
   - Open web UI
   - Check if models appear in loader node dropdowns:
     - IPAdapterModelLoader → should show ip-adapter files
     - CLIPVisionLoader → should show CLIP-ViT files
     - ControlNetLoader → should show control_v11p files

3. **Test IP-Adapter Workflow:**
   - Follow guide in `TESTING-CONTROLNET-IPADAPTER.md`
   - Load face reference image
   - Generate with face preservation
   - **Success criteria:** Generated face matches reference

4. **Test ControlNet Workflow:**
   - Load pose reference image
   - Generate with pose control
   - **Success criteria:** Generated pose matches reference

5. **Test Combined Workflow:**
   - Use both IP-Adapter AND ControlNet
   - **Success criteria:** Same face + same pose + your prompt style

### Phase 2: NAS Sync (30 minutes)

1. **Copy Models to NAS:**
   ```bash
   # From one GPU node
   rsync -av --progress ComfyUI/models/ipadapter/ 192.168.0.103:/volume1/comfyui/models/ipadapter/
   rsync -av --progress ComfyUI/models/clip_vision/ 192.168.0.103:/volume1/comfyui/models/clip_vision/
   rsync -av --progress ComfyUI/models/controlnet/ 192.168.0.103:/volume1/comfyui/models/controlnet/
   ```

2. **Mount NAS on All Nodes:**
   - Follow `MODEL-SYNC-SETUP.md` instructions
   - Mount `192.168.0.103:/volume1/comfyui` on each node
   - Create symlinks or set up local cache

3. **Verify All Nodes Can See Models:**
   - Check ComfyUI on each node
   - Confirm all models appear in dropdowns

4. **Run Backend Model Discovery:**
   - Restart backend to trigger model discovery
   - Check logs for: "Discovered X IP-Adapters, Y ControlNets, Z CLIP Vision"
   - Verify counts match your downloads

### Phase 3: Backend Integration (4-6 hours)

This is where the real work begins! Follow the checklist in `TESTING-CONTROLNET-IPADAPTER.md`.

1. **Create Workflow Templates:** (2 hours)
   - [ ] `workflow_sd15_base.json` (already exists)
   - [ ] `workflow_sd15_ipadapter.json` (face preservation)
   - [ ] `workflow_sd15_controlnet_pose.json` (pose control)
   - [ ] `workflow_sd15_controlnet_depth.json` (depth control)
   - [ ] `workflow_sd15_controlnet_canny.json` (edge control)
   - [ ] `workflow_sd15_combined_face_pose.json` (face + pose)
   - [ ] SDXL variants of above

2. **Reference Image Upload API:** (1 hour)
   - [ ] `POST /api/references/upload` - Upload reference image
   - [ ] `GET /api/references/{ref_id}` - Retrieve reference
   - [ ] `DELETE /api/references/{ref_id}` - Delete reference
   - [ ] Storage in `data/references/{session_id}/`
   - [ ] Thumbnail generation

3. **Extend WorkflowEngine:** (2 hours)
   - [ ] Detect `reference_images` in generation request
   - [ ] Select correct workflow template based on reference types
   - [ ] Inject reference image paths into workflow JSON
   - [ ] Set strength parameters from request
   - [ ] Handle locked fields (pass to LLM refinement)

4. **Update GenerationRequest Schema:** (30 minutes)
   - [ ] Add `reference_images: List[ReferenceImageSpec]` to request
   - [ ] Add `locked_fields: Dict[str, str]` to request
   - [ ] Update `POST /api/generate/batch` endpoint

5. **Test End-to-End:** (30 minutes)
   - [ ] Generate from Concept Builder UI with face reference
   - [ ] Generate with pose reference
   - [ ] Generate with both combined
   - [ ] Verify locked fields stay unchanged during refinement
   - [ ] Test strength adjustments

### Phase 4: Polish & Optimization (Optional, 2-4 hours)

- [ ] Cache preprocessor outputs (depth maps, pose skeletons)
- [ ] Add reference image preview in generation history
- [ ] Show which references were used for each generation
- [ ] Add "extract pose from generated image" feature
- [ ] Add "use generated image as face reference" feature
- [ ] Optimize VRAM usage for combined workflows
- [ ] Add batch reference processing

---

## 🎯 Current Capabilities

### What Works NOW (Basic Concept Builder):
✅ Fill in 7 structured concept fields
✅ Lock/unlock any field
✅ Generate variations (6-12 images)
✅ Select aspect ratio (portrait/landscape/square)
✅ View results in grid
✅ Select favorites
✅ Reject all
✅ Refine selected (with locked fields)
✅ Upload reference images (frontend only - not sent to backend yet)
✅ Adjust reference strength (frontend only)

### What Works AFTER Phase 3:
✅ Face/character preservation (IP-Adapter)
✅ Pose control (ControlNet)
✅ Depth/composition control (ControlNet)
✅ Combined face + pose control
✅ Locked fields respected during refinement
✅ Reference strength adjustments applied
✅ Multi-reference combinations

---

## 📊 Resource Requirements

### Disk Space (per node):
- **3050Ti (SD1.5 only):** ~10GB
  - IP-Adapter SD15: 143MB
  - CLIP Vision: 3.8GB
  - ControlNet SD15 (3 models): ~4.2GB

- **3060/4060Ti/5060Ti (SD1.5 + SDXL):** ~20GB
  - IP-Adapter SD15 + SDXL: 864MB
  - CLIP Vision: 3.8GB
  - ControlNet SD15 (5 models): ~7GB
  - ControlNet SDXL (2 models): ~10GB

### VRAM Requirements:
- **IP-Adapter alone:** +500MB
- **ControlNet alone:** +500-800MB
- **Both combined:** +1-1.5GB
- **Total for SD1.5 + both:** ~4-5GB
- **Total for SDXL + both:** ~8-9GB

**Conclusion:**
- 3050Ti: SD1.5 + one technique (IP-Adapter OR ControlNet)
- 3060: SD1.5 + both, or SDXL + one
- 4060Ti/5060Ti: SDXL + both comfortably

---

## 🚀 Quick Start (When Downloads Complete)

```bash
# 1. Organize models
cd I:/Vibes/ImGen
python scripts/organize_models.py ~/Downloads --execute

# 2. Test in ComfyUI (any node)
# - Open http://GPU-NODE-IP:8188
# - Load IP-Adapter test workflow
# - Queue prompt with face reference

# 3. Sync to NAS
rsync -av ComfyUI/models/ 192.168.0.103:/volume1/comfyui/models/

# 4. Restart backend to discover new models
cd I:/Vibes/ImGen
docker compose restart backend

# 5. Check backend logs
docker compose logs -f backend | grep "Discovered models"
# Should show: "X IP-Adapters, Y CLIP Vision, Z ControlNets"

# 6. Test Concept Builder
# - Open http://localhost:3000
# - Select "Concept Builder" flow
# - Fill in fields
# - Upload reference image (frontend works, backend needs Phase 3)
# - Generate!
```

---

## 📝 Notes

- **CLIP Vision is REQUIRED** for IP-Adapter to work at all - make sure it downloads completely!
- **Preprocessors** (OpenPose, Depth, Canny) are auto-installed by ComfyUI Manager when first used
- **Text encoders** are already in your checkpoint files (no separate download needed)
- **Model sync** already supports all these model types (just added CLIP Vision detection)
- **Frontend is 100% complete** - all features work (uploads just stay local for now)
- **Backend needs ~6 hours of work** to connect everything (mostly workflow templates)

---

## 💡 Tips

- Test each model type individually before combining (easier to debug)
- Start with SD1.5 models (faster, less VRAM, easier to test)
- Use lower resolutions initially (512x512) to save VRAM during testing
- Check ComfyUI console for errors if models don't appear
- The preprocessor models download automatically on first use (be patient)
- Face preservation works best with clear, front-facing reference photos
- Pose control works best with full-body reference images
- You can combine multiple ControlNets (e.g., pose + depth) for even more control!

---

Let me know when downloads finish and we'll test everything! 🎨
