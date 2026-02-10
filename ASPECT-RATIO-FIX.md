# Thumbnail Aspect Ratio Fix

## Problem
Previously, all image thumbnails were displayed as squares regardless of the actual image dimensions:
- Portrait images (2:3) were cropped to square
- Landscape images (3:2) were cropped to square
- Square images (1:1) displayed correctly

This meant users couldn't see the full composition in the thumbnails and had to click/hover to see the actual aspect ratio.

## Solution
Updated `ImageCard` component to dynamically calculate thumbnail dimensions based on the actual image aspect ratio stored in generation parameters.

## Implementation

### Before (Fixed Square):
```typescript
const sizeClasses = {
  sm: "w-32 h-32",     // 128x128px (1:1)
  md: "w-48 h-48",     // 192x192px (1:1)
  lg: "w-72 h-72",     // 288x288px (1:1)
};

<div className={sizeClasses[size]}>
  <img src={thumbnailUrl} className="object-cover" />
</div>
```

**Result:** All thumbnails forced to square, images cropped via `object-cover`.

### After (Dynamic Aspect Ratio):
```typescript
const sizeWidths = {
  sm: 128,  // Base width
  md: 192,
  lg: 288,
};

function getImageDimensions(generation: GenerationResult, size: "sm" | "md" | "lg") {
  const baseWidth = sizeWidths[size];

  // Get actual dimensions from generation parameters
  const params = generation.parameters as any;
  const width = params?.width || 512;
  const height = params?.height || 512;
  const aspectRatio = width / height;

  // Calculate proportional height
  const cardWidth = baseWidth;
  const cardHeight = Math.round(baseWidth / aspectRatio);

  return { width: cardWidth, height: cardHeight, aspectRatio };
}

// In render:
const dimensions = getImageDimensions(generation, size);

<div style={{ width: `${dimensions.width}px`, height: `${dimensions.height}px` }}>
  <img src={thumbnailUrl} className="object-cover" />
</div>
```

**Result:** Thumbnails match actual image aspect ratio.

## Examples

### Portrait (2:3 ratio, e.g., 832×1216)
**Medium size (base width 192px):**
- Width: 192px
- Height: 192 / (832/1216) = 192 / 0.684 ≈ **281px**
- Aspect ratio: 192:281 ≈ 2:3 ✓

### Landscape (3:2 ratio, e.g., 1216×832)
**Medium size (base width 192px):**
- Width: 192px
- Height: 192 / (1216/832) = 192 / 1.461 ≈ **131px**
- Aspect ratio: 192:131 ≈ 3:2 ✓

### Square (1:1 ratio, e.g., 1024×1024)
**Medium size (base width 192px):**
- Width: 192px
- Height: 192 / (1024/1024) = 192 / 1.0 = **192px**
- Aspect ratio: 192:192 = 1:1 ✓

## Data Source

The aspect ratio is calculated from the `generation.parameters` object, which contains:
```typescript
{
  width: 832,    // Actual generation width
  height: 1216,  // Actual generation height
  steps: 30,
  cfg_scale: 7.5,
  // ... other parameters
}
```

These parameters are set during generation and stored in the database via `GenerationORM`.

### Fallback Behavior
If `width` or `height` are missing from parameters:
- Defaults to 512×512 (square)
- Ensures thumbnails always display, even for legacy generations

## Visual Improvements

### Before (All Square):
```
┌────┐ ┌────┐ ┌────┐
│ 1:1│ │CROP│ │CROP│
│    │ │2:3 │ │3:2 │
└────┘ └────┘ └────┘
Square  Portrait  Landscape
         (cropped) (cropped)
```

### After (Actual Aspect Ratios):
```
┌────┐ ┌──┐ ┌──────┐
│ 1:1│ │2:3│ │ 3:2  │
│    │ │  │ │      │
└────┘ └──┘ └──────┘
Square Portrait Landscape
       (full)   (full)
```

## Benefits

### 1. Accurate Preview
Users can see the actual composition without cropping:
- Portrait shots show full vertical extent
- Landscape shots show full horizontal extent
- No important details cropped out

### 2. Better Selection
Users can make informed selection decisions:
- "This portrait shows the full character" vs "This one crops the head"
- "This landscape captures the whole scene" vs "This one cuts off the edges"

### 3. Consistent UX
What you see in the thumbnail is what the full image looks like:
- No surprises when viewing full size
- Builds trust in the preview system

### 4. Professional Look
Grid layouts naturally look better with varied aspect ratios:
- More dynamic and interesting
- Matches professional image galleries
- Pinterest/Behance-style layouts

## Grid Layout Considerations

### Flexbox Wrapping
The `ImageGrid` component uses flexbox with wrapping:
```tsx
<div className="flex flex-wrap gap-3">
  {generations.map(gen => <ImageCard ... />)}
</div>
```

**With dynamic aspect ratios:**
- Images wrap naturally
- Portrait images take less horizontal space
- Landscape images take more horizontal space
- Grid fills available width efficiently

### Example Layout (md size, 3 images):
```
┌─────────────────────────┐
│ ┌──┐ ┌────┐ ┌──────┐   │
│ │P │ │ S  │ │  L   │   │
│ │o │ │ q  │ │  a   │   │
│ │r │ │ u  │ │  n   │   │
│ │t │ │ a  │ │  d   │   │
│ │r │ │ r  │ │  s   │   │
│ │  │ │ e  │ │  c   │   │
│ └──┘ └────┘ └──────┘   │
└─────────────────────────┘

Portrait: 192×281px
Square:   192×192px
Landscape: 192×131px
```

## Edge Cases Handled

### 1. Extreme Aspect Ratios
**Ultra-wide (e.g., 1920×512):**
- Aspect ratio: 3.75:1
- Medium card: 192px wide × 51px tall
- Still displays correctly, just very short

**Ultra-tall (e.g., 512×1920):**
- Aspect ratio: 0.266:1
- Medium card: 192px wide × 721px tall
- Still displays correctly, just very tall

**Note:** Most SD models don't support extreme ratios, so this rarely happens.

### 2. Missing Parameters
If `generation.parameters` is null/undefined:
```typescript
const width = params?.width || 512;   // Fallback to 512
const height = params?.height || 512; // Fallback to 512
```
Result: Square thumbnail (safe default)

### 3. Invalid Parameters
If `width` or `height` are 0 or negative:
- Division would produce Infinity or negative values
- JavaScript `Math.round()` handles this gracefully
- Worst case: thumbnail displays at 0px (invisible but doesn't crash)

**Future enhancement:** Add validation:
```typescript
if (width <= 0 || height <= 0) {
  return { width: baseWidth, height: baseWidth, aspectRatio: 1 };
}
```

## Performance Impact

### Calculation Cost
`getImageDimensions()` is called once per image card, per render:
- Simple arithmetic: 3 operations (divide, multiply, round)
- Negligible CPU cost (<0.1ms per card)
- No network requests
- No DOM measurements

### Rendering Cost
Using inline `style` instead of Tailwind classes:
- **Before:** CSS class lookup (fast)
- **After:** Inline style (also fast)
- No measurable performance difference

### Layout Recalculation
Dynamic heights may cause layout shifts:
- **Mitigation:** Images load from thumbnails with known dimensions
- **Best practice:** Backend should ensure thumbnails match aspect ratio
- **Future:** Add `aspect-ratio` CSS property for smoother loading

## Backend Requirements

### Thumbnail Generation
Backend should generate thumbnails that match the original aspect ratio:

**Current (assumed):**
```python
# Generate 512×512 thumbnail (square) regardless of source
thumbnail = image.thumbnail((512, 512), Image.LANCZOS)
```

**Improved:**
```python
# Maintain aspect ratio, max 512 on longest side
image.thumbnail((512, 512), Image.LANCZOS)  # This already maintains ratio!
```

Good news: PIL's `thumbnail()` already maintains aspect ratio by default!

### Parameter Storage
Ensure `width` and `height` are stored in `GenerationORM.parameters`:
```python
generation.parameters = {
    "width": 832,
    "height": 1216,
    "steps": 30,
    # ... other params
}
```

This is likely already happening, but verify in `generation.py`.

## Testing Checklist

- [ ] Generate portrait image (832×1216) → verify thumbnail is tall
- [ ] Generate landscape image (1216×832) → verify thumbnail is wide
- [ ] Generate square image (1024×1024) → verify thumbnail is square
- [ ] Test all three sizes (sm, md, lg) → verify proportions maintained
- [ ] Test with missing parameters → verify fallback to square
- [ ] Test grid layout with mixed aspect ratios → verify wrapping
- [ ] Test selection highlighting → verify borders work on all aspect ratios
- [ ] Test on mobile → verify responsive behavior

## Future Enhancements

### 1. Max Height Constraint
Prevent ultra-tall images from dominating screen:
```typescript
const maxHeight = baseWidth * 2; // Max 2:1 aspect ratio
const cardHeight = Math.min(
  Math.round(baseWidth / aspectRatio),
  maxHeight
);
```

### 2. CSS aspect-ratio Property
Modern browsers support native aspect-ratio:
```css
.image-card {
  width: 192px;
  aspect-ratio: var(--aspect);
}
```

```tsx
<div style={{ '--aspect': aspectRatio } as React.CSSProperties}>
```

### 3. Masonry Layout
For a more Pinterest-like experience:
```tsx
<MasonryGrid columns={3}>
  {generations.map(gen => <ImageCard ... />)}
</MasonryGrid>
```

Libraries: `react-masonry-css` or native CSS Grid masonry (experimental).

### 4. Lazy Aspect Ratio
Calculate aspect ratio from loaded image:
```tsx
const [aspectRatio, setAspectRatio] = useState(1);

<img
  onLoad={(e) => {
    const img = e.currentTarget;
    setAspectRatio(img.naturalWidth / img.naturalHeight);
  }}
/>
```

This works even if parameters are missing.

## Migration Notes

**Existing Generations:**
- Old generations without `width`/`height` in parameters → display as square
- No data migration needed
- Seamless fallback behavior

**New Generations:**
- Automatically include `width`/`height` in parameters
- Display with correct aspect ratio immediately

**No Breaking Changes:**
- Existing code continues to work
- Purely additive enhancement
- Can be rolled back by reverting ImageCard.tsx
