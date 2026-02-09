import { useState, useCallback } from "react";
import { useSessionStore } from "@/stores/sessionStore";
import { useGenerationStore } from "@/stores/generationStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { PromptEditor, NegativePromptEditor } from "@/components/shared/PromptEditor";
import { ImageGrid } from "@/components/shared/ImageGrid";
import { FeedbackBar } from "@/components/shared/FeedbackBar";
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

  const activeBatch = useGenerationStore((s) => s.activeBatch);
  const getStageGenerations = useGenerationStore((s) => s.getStageGenerations);
  const getSelectedIds = useGenerationStore((s) => s.getSelectedIds);
  const clearSelections = useGenerationStore((s) => s.clearSelections);
  const setBatch = useGenerationStore((s) => s.setBatch);

  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);

  // WebSocket connection
  useWebSocket(session?.id ?? null);

  const stageGens = getStageGenerations(iterationRound);
  const selectedIds = getSelectedIds();
  const currentStageConfig = STAGE_CONFIG[Math.min(iterationRound, STAGE_CONFIG.length - 1)];

  const handleGenerate = useCallback(async () => {
    if (!session || !prompt.trim()) return;
    setIsGenerating(true);
    setStage("generating");

    try {
      const config = currentStageConfig;
      const resp = await api.generateBatch({
        session_id: session.id,
        prompt: prompt.trim(),
        negative_prompt: negativePrompt.trim(),
        model_family: config.model,
        task_type: config.task,
        width: config.width,
        height: config.height,
        steps: config.steps,
        count: config.count,
        checkpoint: config.model === "sd15" ? "beenyouLite_l15.safetensors" : "epicrealismXL_pureFix.safetensors",
      });
      setBatch(resp.batch_id, resp.total_count);
    } catch (e) {
      console.error("Generation failed:", e);
    } finally {
      setIsGenerating(false);
    }
  }, [session, prompt, negativePrompt, currentStageConfig, setStage, setBatch]);

  const handleAdvance = useCallback(async () => {
    if (!session || selectedIds.length === 0) return;

    try {
      const resp = await api.submitFeedback({
        session_id: session.id,
        selected_image_ids: selectedIds,
        action: "select",
      });

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
      setPrompt(resp.refined_prompt);
    } catch (e) {
      console.error("Refine failed:", e);
    }
  }, [session, prompt, selectedIds]);

  return (
    <div className="flex flex-col h-full">
      {/* Funnel breadcrumb */}
      <div className="flex items-center gap-2 px-4 py-2 bg-surface-1 border-b border-surface-3">
        {STAGE_CONFIG.map((config, i) => (
          <div key={i} className="flex items-center gap-2">
            {i > 0 && <span className="text-gray-600">&rarr;</span>}
            <span
              className={`text-sm px-2 py-0.5 rounded ${
                i === iterationRound
                  ? "bg-accent text-white"
                  : i < iterationRound
                    ? "bg-surface-3 text-gray-300"
                    : "text-gray-500"
              }`}
            >
              {config.count} {config.label}
            </span>
          </div>
        ))}
      </div>

      {/* Prompt input area */}
      <div className="px-4 py-3 bg-surface-1 border-b border-surface-3 space-y-2">
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <PromptEditor value={prompt} onChange={setPrompt} />
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
        <NegativePromptEditor value={negativePrompt} onChange={setNegativePrompt} />
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
          onMoreLikeThis={handleMoreLikeThis}
          onRefine={handleRefine}
          onAdvance={handleAdvance}
          onClearSelection={clearSelections}
          advanceLabel={
            iterationRound < STAGE_CONFIG.length - 1
              ? `Advance to ${STAGE_CONFIG[iterationRound + 1].label}`
              : "Finalize"
          }
        />
      )}
    </div>
  );
}
