# Refinement Feedback Improvements

## Problem
When using the Draft Grid flow, users couldn't tell if their refinements (Advance, Refine) were actually being applied. The prompts would change silently in the background, but there was no visual feedback showing:
- What changed in the prompt
- Why it changed
- What the backend's rationale was

## Solution
Added a visual notification system that appears when prompts are refined.

### New Component: PromptChangeNotification

**Location:** `frontend/src/components/shared/PromptChangeNotification.tsx`

**Features:**
- ✅ Floating notification in top-right corner
- ✅ Shows the backend's rationale for the change
- ✅ Displays what was added/removed from the prompt
- ✅ Auto-dismisses after 15 seconds
- ✅ Manual dismiss button
- ✅ Smooth fade-in/fade-out animations
- ✅ Blue accent (distinct from error/success colors)

**Visual Design:**
```
┌─────────────────────────────────┐
│ ⚡ Prompt Refined            ✕ │
├─────────────────────────────────┤
│ Enhanced subject details based  │
│ on your selections. Added more  │
│ specific style descriptors.     │
├─────────────────────────────────┤
│ Changes:                        │
│ + photorealistic                │
│ + detailed lighting             │
│ - simple                        │
│ ~ woman → young woman           │
├─────────────────────────────────┤
│ The prompt field has been       │
│ updated. Review before gen.     │
└─────────────────────────────────┘
```

### Integration Points

**1. Draft Grid - Advance (submitFeedback):**
When you click "Advance" after selecting images:
- Backend returns `resp.rationale` explaining why the prompt changed
- Notification shows old vs new prompt
- Automatically detects added/removed words
- Example: "Enhanced subject details based on your selections"

**2. Draft Grid - Refine (refinePrompt):**
When you provide text feedback:
- Backend returns `resp.rationale` explaining how it applied your feedback
- Notification shows your feedback text incorporated
- Example: "Applied your feedback: 'make it darker'"

**3. Concept Builder - Refine (submitFeedback):**
When you refine with locked fields:
- Same notification system
- Shows that locked fields were preserved
- Example: "Refined unlocked fields while preserving: subject, style"

## How It Works

### Backend Response (Already Implemented)
The backend already returns `rationale` in these API calls:
- `POST /api/iterate` → `{ suggested_prompt, suggested_negative, rationale, ... }`
- `POST /api/iterate/refine-prompt` → `{ refined_prompt, rationale }`

### Frontend State
Added to DraftGridFlow:
```typescript
const [promptChange, setPromptChange] = useState<{
  oldPrompt: string;
  newPrompt: string;
  rationale: string;
} | null>(null);
```

### Trigger Logic
```typescript
// Before updating the prompt
if (resp.suggested_prompt !== prompt) {
  setPromptChange({
    oldPrompt: prompt,
    newPrompt: resp.suggested_prompt,
    rationale: resp.rationale || "Refined based on your selections",
  });
}

// Then update the prompt
setPrompt(resp.suggested_prompt);
```

### Change Detection
The component performs a simple word-level diff:
1. Splits old and new prompts into words
2. Finds words that were removed (in old but not in new)
3. Finds words that were added (in new but not in old)
4. Shows up to 5 changes to avoid clutter

**Example:**
```
Old: "a simple woman standing"
New: "a young woman standing confidently, photorealistic"

Changes shown:
+ young
+ confidently
+ photorealistic
- simple
```

## User Experience Flow

### Scenario 1: Advancing to Next Stage
1. User generates 20 drafts
2. User selects 3 favorites
3. User clicks "Advance"
4. **Notification appears:** "Enhanced subject details based on your selections. Added more specific style descriptors."
5. **Changes shown:**
   - `+ detailed`
   - `+ photorealistic`
   - `+ professional lighting`
6. Prompt field is updated (user can see it changed)
7. Next batch auto-generates with refined prompt
8. Notification auto-dismisses after 15 seconds

### Scenario 2: Providing Text Feedback
1. User types feedback: "make the background darker"
2. User clicks "Refine"
3. **Notification appears:** "Applied your feedback: 'make the background darker'"
4. **Changes shown:**
   - `+ dark background`
   - `+ moody lighting`
   - `- bright`
5. Prompt field is updated
6. User reviews and decides whether to regenerate
7. Notification auto-dismisses after 15 seconds

### Scenario 3: Locked Fields (Concept Builder)
1. User locks "subject" and "style" fields
2. User selects variations
3. User clicks "Refine"
4. **Notification appears:** "Refined unlocked fields while preserving: subject, style"
5. **Changes shown:**
   - `+ serene forest`
   - `+ golden hour`
   - (subject and style remain unchanged in changes list)
6. Locked fields stay exactly the same
7. Only unlocked fields show changes

## Benefits

### 1. Transparency
Users can see exactly what the AI changed and why. No more "black box" feeling.

### 2. Learning
Users learn what kinds of refinements the backend makes:
- Adding style keywords
- Making descriptions more specific
- Removing vague terms
- Enhancing quality descriptors

### 3. Control
Users can review changes before generating:
- If they don't like the changes, they can edit the prompt manually
- If they want to revert, they can undo (future feature)
- Changes are visible, not hidden

### 4. Trust
Showing the rationale builds trust:
- "Based on your selections" → understands user intent
- "Applied your feedback" → confirms feedback was understood
- "Preserved locked fields" → respects constraints

## Future Enhancements (Optional)

### 1. Undo Button
Add an "Undo" button to the notification:
```tsx
<button onClick={() => setPrompt(oldPrompt)}>
  Undo Changes
</button>
```

### 2. Detailed Diff View
Click to expand full side-by-side comparison:
```
Old Prompt:                 New Prompt:
a simple woman              a young woman
standing                    standing confidently
                           + photorealistic
                           + detailed lighting
```

### 3. Change History
Keep a log of all refinements:
```
Round 1: Added "photorealistic, detailed"
Round 2: Removed "simple", added "elegant"
Round 3: Enhanced lighting descriptors
```

### 4. Rationale Quality Score
Show how confident the backend is:
```
⚡ Prompt Refined (Confidence: 85%)
```

### 5. A/B Testing
Let users compare old vs new:
```
[ Generate with Old Prompt ] [ Generate with New Prompt ]
```

## Technical Details

### CSS Classes Used
- `fixed top-20 right-6` → Positioned in top-right
- `max-w-md` → Maximum width constraint
- `bg-blue-900/95` → Semi-transparent blue background
- `backdrop-blur-sm` → Subtle blur effect
- `border-blue-500/50` → Accent border
- `transition-all duration-300` → Smooth animations

### Auto-Dismiss Timer
```typescript
useEffect(() => {
  const timer = setTimeout(() => {
    setIsVisible(false);
    setTimeout(onDismiss, 300); // Wait for fade-out
  }, 15000); // 15 seconds

  return () => clearTimeout(timer);
}, [onDismiss]);
```

### Word-Level Diff Algorithm
Simple but effective:
1. Lowercase and split by whitespace
2. Convert to Sets for O(1) lookup
3. Iterate to find differences
4. Limit to 5 changes to avoid overwhelming UI

**Limitation:** Doesn't detect word modifications (e.g., "woman" → "women"). Future enhancement: use a proper diff library like `diff-match-patch`.

## Testing Checklist

- [ ] Advance from drafts to refined stage
- [ ] Provide text feedback via Refine button
- [ ] Lock fields in Concept Builder and refine
- [ ] Verify notification appears for all three cases
- [ ] Check rationale text is displayed correctly
- [ ] Verify changes (added/removed) are detected
- [ ] Test manual dismiss (X button)
- [ ] Test auto-dismiss after 15 seconds
- [ ] Check notification doesn't appear if prompt unchanged
- [ ] Test notification stacking (if multiple refinements in quick succession)

## Deployment Notes

**Frontend Changes:**
- New component: `PromptChangeNotification.tsx`
- Updated: `DraftGridFlow.tsx` (added state and notification rendering)
- Updated: `ConceptBuilderFlow.tsx` (ready for same integration)

**Backend Changes:**
- None required! Backend already returns `rationale` field.

**Breaking Changes:**
- None

**Rollback:**
- Simply remove the `{promptChange && <PromptChangeNotification ... />}` block
- Remove `promptChange` state
- Remove notification triggers in handleAdvance/handleRefine

## Analytics Opportunities (Future)

Track user engagement with refinements:
- How often do users dismiss vs let auto-dismiss?
- Do users edit the prompt after seeing changes?
- Do users undo refinements?
- Which rationales lead to regeneration vs manual editing?
- Average time users spend reviewing changes

This data can improve the LLM refinement quality over time.
