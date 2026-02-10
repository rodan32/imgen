import { useState, useCallback, useEffect } from "react";
import { useSessionStore } from "@/stores/sessionStore";
import { useGenerationStore } from "@/stores/generationStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { PromptEditor, NegativePromptEditor } from "@/components/shared/PromptEditor";
import { ImageGrid } from "@/components/shared/ImageGrid";
import { FeedbackBar } from "@/components/shared/FeedbackBar";
import { PromptChangeNotification } from "@/components/shared/PromptChangeNotification";
import * as api from "@/api/client";

const STAGE_CONFIG = [
  { label: "Drafts", count: 20, model: "sd15", task: "draft", width: 512, height: 512, steps: 10, size: "sm" as const },
  { label: "Refined", count: 8, model: "sdxl", task: "standard", width: 1024, height: 1024, steps: 25, size: "md" as const },
  { label: "Polished", count: 3, model: "sdxl", task: "quality", width: 1024, height: 1024, steps: 35, size: "lg" as const },
  { label: "Final", count: 1, model: "sdxl", task: "quality", width: 1024, height: 1024, steps: 50, size: "lg" as const },
];

export function DraftGridFlow() {
  const session = useSessionStore((s) => s.currentSession);
  const iterationRound = useSessionStore((s) => s.iterationRound);
  const setStage = useSessionStore((s) => s.setStage);
  const advanceIteration = useSessionStore((s) => s.advanceIteration);
  const goToStage = useSessionStore((s) => s.goToStage);

  const activeBatch = useGenerationStore((s) => s.activeBatch);
  const allGenerations = useGenerationStore((s) => s.generations);
  const clearSelections = useGenerationStore((s) => s.clearSelections);
  const rejectAllInStage = useGenerationStore((s) => s.rejectAllInStage);
  const setBatch = useGenerationStore((s) => s.setBatch);

  // Derive stage generations and selected IDs from store
  const stageGens = Object.values(allGenerations)
    .filter((g) => g.stage === iterationRound)
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt));

  const selectedIds = Object.values(allGenerations)
    .filter((g) => g.selected)
    .map((g) => g.id);

  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [aspectRatio, setAspectRatio] = useState<"square" | "portrait" | "landscape">("portrait");
  const [exploreMode, setExploreMode] = useState(true);  // Default ON for draft stage
  const [autoLora, setAutoLora] = useState(false);

  // Prompt change notification state
  const [promptChange, setPromptChange] = useState<{
    oldPrompt: string;
    newPrompt: string;
    rationale: string;
  } | null>(null);

  // WebSocket connection
  useWebSocket(session?.id ?? null);

  const currentStageConfig = STAGE_CONFIG[Math.min(iterationRound, STAGE_CONFIG.length - 1)];

  console.log("DraftGridFlow render:", {
    iterationRound,
    stageGensCount: stageGens.length,
    selectedIdsCount: selectedIds.length,
    allGenerations: Object.keys(useGenerationStore.getState().generations).length,
  });

  const handleGenerate = useCallback(async () => {
    if (!session || !prompt.trim()) return;
    setIsGenerating(true);
    setStage("generating");

    try {
      const config = currentStageConfig;
      // Get dimensions based on aspect ratio
      const baseSize = config.model === "sd15" ? 512 : 1024;
      let dimensions = { width: baseSize, height: baseSize };
      if (aspectRatio === "portrait") {
        dimensions = config.model === "sd15"
          ? { width: 512, height: 768 }   // 2:3 ratio
          : { width: 832, height: 1216 }; // SDXL 2:3
      } else if (aspectRatio === "landscape") {
        dimensions = config.model === "sd15"
          ? { width: 768, height: 512 }   // 3:2 ratio
          : { width: 1216, height: 832 }; // SDXL 3:2
      }

      const resp = await api.generateBatch({
        session_id: session.id,
        prompt: prompt.trim(),
        negative_prompt: negativePrompt.trim(),
        model_family: config.model,
        task_type: config.task,
        width: dimensions.width,
        height: dimensions.height,
        steps: config.steps,
        count: config.count,
        checkpoint: config.model === "sd15" ? "beenyouLite_l15.safetensors" : "epicrealismXL_pureFix.safetensors",
        explore_mode: exploreMode,
        auto_lora: autoLora,
      });
      setBatch(resp.batch_id, resp.total_count);
    } catch (e) {
      console.error("Generation failed:", e);
    } finally {
      setIsGenerating(false);
    }
  }, [session, prompt, negativePrompt, currentStageConfig, aspectRatio, exploreMode, autoLora, setStage, setBatch]);

  const handleAdvance = useCallback(async () => {
    if (!session || selectedIds.length === 0) return;

    try {
      const resp = await api.submitFeedback({
        session_id: session.id,
        selected_image_ids: selectedIds,
        action: "select",
      });

      // Show what changed
      if (resp.suggested_prompt !== prompt || resp.suggested_negative !== negativePrompt) {
        setPromptChange({
          oldPrompt: prompt,
          newPrompt: resp.suggested_prompt,
          rationale: resp.rationale || "Refined based on your selections",
        });
      }

      // Update prompt with suggestion
      setPrompt(resp.suggested_prompt);
      if (resp.suggested_negative) setNegativePrompt(resp.suggested_negative);

      advanceIteration();

      // Auto-generate next stage
      const nextConfig = STAGE_CONFIG[Math.min(iterationRound + 1, STAGE_CONFIG.length - 1)];
      const batchResp = await api.generateBatch({
        session_id: session.id,
        prompt: resp.suggested_prompt,
        negative_prompt: resp.suggested_negative,
        model_family: nextConfig.model,
        task_type: nextConfig.task,
        width: nextConfig.width,
        height: nextConfig.height,
        steps: nextConfig.steps,
        count: nextConfig.count,
        checkpoint: nextConfig.model === "sd15" ? "beenyouLite_l15.safetensors" : "epicrealismXL_pureFix.safetensors",
      });
      setBatch(batchResp.batch_id, batchResp.total_count);
    } catch (e) {
      console.error("Advance failed:", e);
    }
  }, [session, selectedIds, iterationRound, advanceIteration, setBatch]);

  const handleMoreLikeThis = useCallback(async () => {
    if (!session || selectedIds.length === 0) return;
    try {
      await api.autoIterate({
        session_id: session.id,
        selected_image_ids: selectedIds,
        action: "more_like_this",
      });
    } catch (e) {
      console.error("More like this failed:", e);
    }
  }, [session, selectedIds]);

  const handleRefine = useCallback(async (feedback: string) => {
    if (!session) return;
    try {
      const resp = await api.refinePrompt({
        session_id: session.id,
        current_prompt: prompt,
        feedback_text: feedback,
        reference_image_ids: selectedIds,
      });

      // Show what changed
      if (resp.refined_prompt !== prompt) {
        setPromptChange({
          oldPrompt: prompt,
          newPrompt: resp.refined_prompt,
          rationale: resp.rationale || `Applied your feedback: "${feedback}"`,
        });
      }

      setPrompt(resp.refined_prompt);
    } catch (e) {
      console.error("Refine failed:", e);
    }
  }, [session, prompt, selectedIds]);

  const handleRejectAll = useCallback(async (feedback?: string) => {
    if (!session) return;

    // Mark all current stage images as rejected in the store
    rejectAllInStage(iterationRound);

    // Get IDs of rejected images
    const rejectedIds = stageGens.map((g) => g.id);

    // Send rejection feedback to backend for learning
    try {
      await api.rejectAll({
        session_id: session.id,
        stage: iterationRound,
        feedback_text: feedback,
        rejected_image_ids: rejectedIds,
      });
      console.log("Rejection recorded for checkpoint/LoRA learning");
    } catch (e) {
      console.error("Failed to record rejection:", e);
    }

    // Navigation behavior
    if (iterationRound > 0) {
      // Go back to previous stage to try again
      goToStage(iterationRound - 1);
    } else {
      // At first stage, could regenerate with different settings
      // For now, user can manually adjust and regenerate
      console.log("Reject all at stage 0 - adjust settings and regenerate");
    }
  }, [session, iterationRound, stageGens, rejectAllInStage, goToStage]);

  // Keyboard navigation: Alt+Left/Right to navigate stages
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!e.altKey) return;

      if (e.key === "ArrowLeft" && iterationRound > 0) {
        // Go back to previous stage if it has generations
        for (let i = iterationRound - 1; i >= 0; i--) {
          const hasGens = Object.values(allGenerations).some((g) => g.stage === i);
          if (hasGens) {
            e.preventDefault();
            goToStage(i);
            break;
          }
        }
      } else if (e.key === "ArrowRight" && iterationRound < STAGE_CONFIG.length - 1) {
        // Go forward to next stage if it has generations
        for (let i = iterationRound + 1; i < STAGE_CONFIG.length; i++) {
          const hasGens = Object.values(allGenerations).some((g) => g.stage === i);
          if (hasGens) {
            e.preventDefault();
            goToStage(i);
            break;
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [iterationRound, allGenerations, goToStage]);

  return (
    <div className="flex flex-col h-full">
      {/* Funnel breadcrumb - clickable navigation */}
      <div className="flex items-center gap-2 px-4 py-2 bg-surface-1 border-b border-surface-3">
        {STAGE_CONFIG.map((config, i) => {
          // Check if this stage has any generations
          const hasGenerations = Object.values(allGenerations).some((g) => g.stage === i);
          const isClickable = hasGenerations && i !== iterationRound;

          return (
            <div key={i} className="flex items-center gap-2">
              {i > 0 && <span className="text-gray-600">&rarr;</span>}
              <button
                onClick={() => isClickable && goToStage(i)}
                disabled={!isClickable}
                className={`text-sm px-2 py-0.5 rounded transition-colors ${
                  i === iterationRound
                    ? "bg-accent text-white"
                    : isClickable
                      ? "bg-surface-3 text-gray-300 hover:bg-surface-4 cursor-pointer"
                      : "text-gray-500 cursor-default"
                }`}
              >
                {config.count} {config.label}
              </button>
            </div>
          );
        })}
      </div>

      {/* Prompt input area */}
      <div className="px-4 py-3 bg-surface-1 border-b border-surface-3 space-y-2">
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <PromptEditor value={prompt} onChange={setPrompt} />
          </div>

          {/* Aspect ratio selector */}
          <div className="flex flex-col gap-1">
            <span className="text-xs text-gray-400">Aspect</span>
            <div className="flex gap-1 bg-surface-2 rounded-lg p-1">
              <button
                onClick={() => setAspectRatio("portrait")}
                className={`px-3 py-1.5 text-xs rounded transition-colors ${
                  aspectRatio === "portrait"
                    ? "bg-accent text-white"
                    : "text-gray-400 hover:text-gray-200"
                }`}
                title="Portrait (2:3)"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="8" y="4" width="8" height="16" rx="1" />
                </svg>
              </button>
              <button
                onClick={() => setAspectRatio("landscape")}
                className={`px-3 py-1.5 text-xs rounded transition-colors ${
                  aspectRatio === "landscape"
                    ? "bg-accent text-white"
                    : "text-gray-400 hover:text-gray-200"
                }`}
                title="Landscape (3:2)"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="4" y="8" width="16" height="8" rx="1" />
                </svg>
              </button>
              <button
                onClick={() => setAspectRatio("square")}
                className={`px-3 py-1.5 text-xs rounded transition-colors ${
                  aspectRatio === "square"
                    ? "bg-accent text-white"
                    : "text-gray-400 hover:text-gray-200"
                }`}
                title="Square (1:1)"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" rx="1" />
                </svg>
              </button>
            </div>
          </div>

          <button
            onClick={handleGenerate}
            disabled={isGenerating || !prompt.trim()}
            className="px-6 py-2.5 bg-accent text-white rounded-lg font-medium
              hover:bg-accent-hover disabled:opacity-50 transition-colors whitespace-nowrap"
          >
            {isGenerating ? "Generating..." : `Generate ${currentStageConfig.count}`}
          </button>
        </div>

        {/* Second row: Negative prompt and feature toggles */}
        <div className="flex gap-3 items-center">
          <div className="flex-1">
            <NegativePromptEditor value={negativePrompt} onChange={setNegativePrompt} />
          </div>

          {/* Feature toggles */}
          <div className="flex gap-3 items-center text-sm">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={exploreMode}
                onChange={(e) => setExploreMode(e.target.checked)}
                className="w-4 h-4 rounded border-gray-600 bg-surface-2 text-accent
                  focus:ring-accent focus:ring-offset-0"
              />
              <span className="text-gray-300">Explore Mode</span>
            </label>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={autoLora}
                onChange={(e) => setAutoLora(e.target.checked)}
                className="w-4 h-4 rounded border-gray-600 bg-surface-2 text-accent
                  focus:ring-accent focus:ring-offset-0"
              />
              <span className="text-gray-300">Auto-LoRA</span>
            </label>
          </div>
        </div>
      </div>

      {/* Batch progress */}
      {activeBatch && (
        <div className="px-4 py-2 bg-surface-1 border-b border-surface-3">
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 bg-surface-3 rounded-full overflow-hidden">
              <div
                className="h-full bg-accent rounded-full transition-all duration-500"
                style={{ width: `${(activeBatch.completed / activeBatch.total) * 100}%` }}
              />
            </div>
            <span className="text-sm text-gray-400">
              {activeBatch.completed}/{activeBatch.total}
            </span>
          </div>
        </div>
      )}

      {/* Image grid */}
      <div className="flex-1 overflow-y-auto p-4">
        <ImageGrid
          generations={stageGens}
          size={currentStageConfig.size}
          showInfo={iterationRound > 0}
        />
      </div>

      {/* Feedback bar */}
      {stageGens.length > 0 && (
        <FeedbackBar
          selectedCount={selectedIds.length}
          totalCount={stageGens.length}
          onMoreLikeThis={handleMoreLikeThis}
          onRefine={handleRefine}
          onAdvance={handleAdvance}
          onClearSelection={clearSelections}
          onRejectAll={handleRejectAll}
          advanceLabel={
            iterationRound < STAGE_CONFIG.length - 1
              ? `Advance to ${STAGE_CONFIG[iterationRound + 1].label}`
              : "Finalize"
          }
        />
      )}

      {/* Prompt change notification */}
      {promptChange && (
        <PromptChangeNotification
          oldPrompt={promptChange.oldPrompt}
          newPrompt={promptChange.newPrompt}
          rationale={promptChange.rationale}
          onDismiss={() => setPromptChange(null)}
        />
      )}
    </div>
  );
}
