# Concept Builder Flow - Design Document

## Overview
The Concept Builder is a structured approach to image generation that allows users to:
1. Define concepts field-by-field (subject, pose, background, style, etc.)
2. Lock fields they like while iterating on others
3. Upload reference images for face/pose/composition control
4. Generate variations with precise control over what changes

## UI Components

### 1. ConceptBuilderFlow (Main Container)
- **Split-panel layout**: Left panel for controls, right panel for results
- **Tabbed left panel**: Switch between "Concept Fields" and "References"
- **State management**: Tracks concept fields, locks, references, generations
- **WebSocket integration**: Real-time updates for generation progress

### 2. ConceptFields Component
Seven structured fields:
- **Subject**: Main subject description (person, object, character)
- **Pose & Action**: Body position, activity
- **Background**: Scene and environment
- **Art Style**: Visual style (photorealistic, digital art, etc.)
- **Lighting**: Light quality, direction, mood
- **Mood & Atmosphere**: Emotional tone
- **Camera Angle**: Perspective and framing

Each field has:
- **Lock/unlock toggle**: Preserve field during refinement (yellow locked state)
- **Visual feedback**: Locked fields show yellow border and disabled state
- **Independent editing**: Edit any unlocked field without affecting locked ones

### 3. ReferenceImagePanel Component
Five reference types for ControlNet/IP-Adapter:

#### Face/Character (IP-Adapter)
- **Purpose**: Maintain consistent character identity across generations
- **Default strength**: 80%
- **Use case**: Same person in different poses, scenes, outfits
- **Backend**: IP-Adapter or similar face preservation model

#### Pose Control (ControlNet - OpenPose)
- **Purpose**: Guide body position and posture
- **Default strength**: 60%
- **Use case**: Specific pose without matching the original person
- **Backend**: ControlNet OpenPose preprocessor

#### Depth Map (ControlNet - Depth)
- **Purpose**: Control spatial relationships and distance
- **Default strength**: 60%
- **Use case**: Match composition and depth without matching content
- **Backend**: ControlNet Depth preprocessor

#### Edge Control (ControlNet - Canny)
- **Purpose**: Follow edge structure and outlines
- **Default strength**: 60%
- **Use case**: Precise structural control
- **Backend**: ControlNet Canny preprocessor

#### Composition (ControlNet - MLSD or Softedge)
- **Purpose**: Overall layout and structure
- **Default strength**: 60%
- **Use case**: Match general composition and lines
- **Backend**: ControlNet MLSD or Softedge preprocessor

Each reference includes:
- **Image upload**: Drag/drop or click to upload
- **Strength slider**: 0-100% influence control
- **Remove button**: Delete reference
- **Type indicator**: Icon and label showing reference type
- **Thumbnail preview**: See what image is being used

## Workflow

### Initial Generation
1. User fills in concept fields (at least one required)
2. Optionally uploads reference images
3. Clicks "Generate Variations" (default: 6 images)
4. Backend combines:
   - Prompt from concept fields
   - Reference images via ControlNet/IP-Adapter
   - User's selected checkpoint and LoRAs

### Refinement Iteration
1. User reviews generated images
2. Selects favorites (or rejects all)
3. Locks fields they want to preserve
4. Optionally adds/removes/adjusts reference images
5. Clicks "Refine" to generate new variations
6. **Backend behavior**:
   - Locked fields remain exactly the same in prompt
   - Unlocked fields can be varied by LLM prompt refinement
   - Reference images persist across iterations (unless removed)
   - Preference learning influences checkpoint/LoRA selection

### Lock System Benefits
- **Iterative refinement**: "I love the pose but want a different background"
- **Concept exploration**: Lock subject + style, explore different scenes
- **Character consistency**: Lock subject description, iterate on everything else
- **Artistic control**: Lock artistic choices (style, lighting) while varying content

## Backend Integration Requirements

### 1. Reference Image Upload API
```python
POST /api/references/upload
{
  "session_id": str,
  "image": file,
  "type": "face" | "pose" | "depth" | "canny" | "composition",
  "strength": float  # 0.0 - 1.0
}
Response: {
  "reference_id": str,
  "url": str,
  "type": str,
  "strength": float
}
```

### 2. Reference Image Management
```python
DELETE /api/references/{reference_id}
PATCH /api/references/{reference_id}/strength
{
  "strength": float
}
```

### 3. Enhanced Generation Endpoint
Extend existing `POST /api/generate/batch` to accept:
```python
{
  # Existing fields...
  "reference_images": [
    {
      "reference_id": str,
      "type": "face" | "pose" | "depth" | "canny" | "composition",
      "strength": float
    }
  ],
  "locked_fields": {
    "subject": str | null,
    "pose": str | null,
    "background": str | null,
    "style": str | null,
    "lighting": str | null,
    "mood": str | null,
    "camera": str | null
  }
}
```

### 4. Workflow Engine Enhancements
The WorkflowEngine needs to:
1. **Detect reference images** in generation request
2. **Select appropriate ComfyUI workflow** based on reference types:
   - Base workflow (no references)
   - IP-Adapter workflow (face references)
   - ControlNet workflow (pose/depth/canny/composition)
   - Combined workflow (multiple reference types)
3. **Inject reference images** into workflow JSON:
   - Load uploaded images from storage
   - Add preprocessor nodes (for ControlNet)
   - Add IP-Adapter nodes (for face)
   - Set strength parameters
4. **Merge with locked concepts**:
   - Build base prompt from all concept fields
   - Mark locked fields for exclusion from LLM refinement

### 5. Model Requirements
Need to sync these model types to GPU nodes (already planned in model sync):
- **IP-Adapter models**: `ip-adapter-faceid-plus_sd15.bin`, `ip-adapter-faceid-plusv2_sdxl.bin`
- **ControlNet models**:
  - `control_v11p_sd15_openpose.pth` (pose)
  - `control_v11f1p_sd15_depth.pth` (depth)
  - `control_v11p_sd15_canny.pth` (edges)
  - `control_v11p_sd15_mlsd.pth` (lines/composition)
  - `control_v11p_sd15_softedge.pth` (soft edges)
  - SDXL equivalents: `diffusers_xl_canny_*`, etc.
- **CLIP vision models**: For IP-Adapter face encoding
- **Preprocessor models**: For automatic ControlNet preprocessing

### 6. Storage Structure
```
data/
  references/
    {session_id}/
      {reference_id}.png         # Original uploaded image
      {reference_id}_thumb.jpg   # Thumbnail for UI
      {reference_id}_meta.json   # Type, strength, created_at
```

### 7. Workflow Template Examples

#### Base Workflow (No References)
```json
{
  "nodes": {
    "1": {"class_type": "CheckpointLoaderSimple", ...},
    "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{prompt}}", ...}},
    "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{negative}}", ...}},
    "4": {"class_type": "KSampler", ...},
    "5": {"class_type": "VAEDecode", ...},
    "6": {"class_type": "SaveImage", ...}
  }
}
```

#### IP-Adapter Workflow (Face Reference)
```json
{
  "nodes": {
    "1": {"class_type": "CheckpointLoaderSimple", ...},
    "2": {"class_type": "CLIPTextEncode", ...},
    "3": {"class_type": "CLIPTextEncode", ...},
    "10": {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": "ip-adapter-faceid-plus_sd15.bin"}},
    "11": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"}},
    "12": {"class_type": "LoadImage", "inputs": {"image": "{{reference_face}}"}},
    "13": {"class_type": "CLIPVisionEncode", "inputs": {"clip_vision": ["11", 0], "image": ["12", 0]}},
    "14": {"class_type": "IPAdapterApply", "inputs": {
      "ipadapter": ["10", 0],
      "image_embed": ["13", 0],
      "model": ["1", 0],
      "weight": {{reference_face_strength}}
    }},
    "4": {"class_type": "KSampler", "inputs": {"model": ["14", 0], ...}},
    ...
  }
}
```

#### ControlNet Workflow (Pose Reference)
```json
{
  "nodes": {
    "1": {"class_type": "CheckpointLoaderSimple", ...},
    "20": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": "control_v11p_sd15_openpose.pth"}},
    "21": {"class_type": "LoadImage", "inputs": {"image": "{{reference_pose}}"}},
    "22": {"class_type": "OpenposePreprocessor", "inputs": {"image": ["21", 0]}},
    "23": {"class_type": "ControlNetApply", "inputs": {
      "conditioning": ["2", 0],
      "control_net": ["20", 0],
      "image": ["22", 0],
      "strength": {{reference_pose_strength}}
    }},
    "4": {"class_type": "KSampler", "inputs": {"positive": ["23", 0], ...}},
    ...
  }
}
```

#### Combined Workflow (Face + Pose)
- Merges both IP-Adapter and ControlNet nodes
- Chains model modifications: Checkpoint → IP-Adapter → ControlNet → KSampler
- Applies both reference images with individual strength controls

## Frontend State Flow

```typescript
// User fills fields
concept.subject.value = "young woman with blue hair"
concept.pose.value = "standing confidently"
concept.subject.locked = false

// User generates → sees results → likes one
handleSelectImage(result_id)

// User locks subject
concept.subject.locked = true

// User uploads pose reference
handleAddReference(pose_image_file, "pose")

// User refines
handleRefine() → backend receives:
{
  locked_fields: { subject: "young woman with blue hair" },
  reference_images: [{ type: "pose", reference_id: "ref-123", strength: 0.6 }],
  prompt: "young woman with blue hair, standing confidently, ..."
}

// Backend LLM refinement:
// - MUST keep locked fields verbatim
// - Can vary unlocked fields (pose, background, style, etc.)
// - Applies pose ControlNet to maintain pose structure
// - New generation maintains character but explores new poses/backgrounds
```

## Next Steps

### Immediate (Frontend Complete ✅)
- [x] ConceptBuilderFlow component with field locking
- [x] ConceptFields with lock UI
- [x] ReferenceImagePanel with 5 reference types
- [x] Tab navigation between Concept and References
- [x] Strength sliders for each reference
- [x] Integration into App.tsx

### Backend (To Implement)
- [ ] Reference image upload/storage endpoints
- [ ] Extend WorkflowEngine to support ControlNet/IP-Adapter injection
- [ ] Create workflow templates for each reference type + combinations
- [ ] Update LLM refinement to respect locked fields
- [ ] Sync IP-Adapter and ControlNet models to GPU nodes
- [ ] Add CLIP vision models for IP-Adapter
- [ ] Add ControlNet preprocessor models

### Testing Strategy
1. **Unit tests**: Reference upload/delete/update strength
2. **Workflow tests**: Verify correct nodes injected for each reference type
3. **Integration tests**: End-to-end generation with various reference combinations
4. **Model tests**: Verify all required models present on GPU nodes
5. **UI tests**: Lock/unlock fields, add/remove references, strength adjustments

### Performance Considerations
- Reference images stored on NAS (shared across GPU nodes)
- Preprocessor execution cached (depth/canny/openpose results stored)
- CLIP vision encoding cached per reference image
- Workflow selection optimized (don't load models if not needed)
- Face reference works best with VRAM >= 8GB (3050Ti excluded from IP-Adapter tasks)

## User Benefits

1. **Precise Control**: Lock exactly what you want to keep
2. **Character Consistency**: Face references maintain identity across variations
3. **Pose Guidance**: ControlNet ensures desired body positions
4. **Iterative Exploration**: Refine step-by-step without losing progress
5. **Multi-Reference**: Combine face + pose + depth for maximum control
6. **Visual Feedback**: Clear UI showing what's locked and what references are active
7. **Strength Control**: Fine-tune influence of each reference independently
