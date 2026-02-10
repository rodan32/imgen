import { useState, useCallback } from "react";
import { useSessionStore } from "@/stores/sessionStore";
import { useGenerationStore } from "@/stores/generationStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import { ConceptFields } from "./ConceptFields";
import { ReferenceImagePanel, type ReferenceImage } from "./ReferenceImagePanel";
import { ImageGrid } from "@/components/shared/ImageGrid";
import * as api from "@/api/client";

export interface ConceptFieldState {
  subject: { value: string; locked: boolean };
  pose: { value: string; locked: boolean };
  background: { value: string; locked: boolean };
  style: { value: string; locked: boolean };
  lighting: { value: string; locked: boolean };
  mood: { value: string; locked: boolean };
  camera: { value: string; locked: boolean };
}

const INITIAL_CONCEPT: ConceptFieldState = {
  subject: { value: "", locked: false },
  pose: { value: "", locked: false },
  background: { value: "", locked: false },
  style: { value: "", locked: false },
  lighting: { value: "", locked: false },
  mood: { value: "", locked: false },
  camera: { value: "", locked: false },
};

export function ConceptBuilderFlow() {
  const session = useSessionStore((s) => s.currentSession);
  const iterationRound = useSessionStore((s) => s.iterationRound);
  const setStage = useSessionStore((s) => s.setStage);
  const advanceIteration = useSessionStore((s) => s.advanceIteration);

  const allGenerations = useGenerationStore((s) => s.generations);
  const clearSelections = useGenerationStore((s) => s.clearSelections);
  const rejectAllInStage = useGenerationStore((s) => s.rejectAllInStage);
  const setBatch = useGenerationStore((s) => s.setBatch);

  const [concept, setConcept] = useState<ConceptFieldState>(INITIAL_CONCEPT);
  const [negativePrompt, setNegativePrompt] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [variationCount, setVariationCount] = useState(6);
  const [aspectRatio, setAspectRatio] = useState<"square" | "portrait" | "landscape">("portrait");
  const [references, setReferences] = useState<ReferenceImage[]>([]);
  const [activeTab, setActiveTab] = useState<"concept" | "references">("concept");

  // WebSocket connection
  useWebSocket(session?.id ?? null);

  // Derive stage generations and selected IDs
  const stageGens = Object.values(allGenerations)
    .filter((g) => g.stage === iterationRound)
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt));

  const selectedIds = Object.values(allGenerations)
    .filter((g) => g.selected)
    .map((g) => g.id);

  // Build prompt from concept fields
  const buildPrompt = useCallback(() => {
    const parts: string[] = [];
    if (concept.subject.value) parts.push(concept.subject.value);
    if (concept.pose.value) parts.push(concept.pose.value);
    if (concept.background.value) parts.push(concept.background.value);
    if (concept.style.value) parts.push(concept.style.value);
    if (concept.lighting.value) parts.push(concept.lighting.value);
    if (concept.mood.value) parts.push(concept.mood.value);
    if (concept.camera.value) parts.push(concept.camera.value);
    return parts.join(", ");
  }, [concept]);

  const handleGenerate = useCallback(async () => {
    if (!session) return;
    const prompt = buildPrompt();
    if (!prompt.trim()) return;

    setIsGenerating(true);
    setStage("generating");

    try {
      // For concept builder, we use quality settings from the start
      const baseSize = 1024;
      let dimensions = { width: baseSize, height: baseSize };
      if (aspectRatio === "portrait") {
        dimensions = { width: 832, height: 1216 }; // SDXL 2:3
      } else if (aspectRatio === "landscape") {
        dimensions = { width: 1216, height: 832 }; // SDXL 3:2
      }

      const resp = await api.generateBatch({
        session_id: session.id,
        prompt: prompt.trim(),
        negative_prompt: negativePrompt.trim(),
        model_family: "sdxl",
        task_type: "standard",
        width: dimensions.width,
        height: dimensions.height,
        steps: 30,
        count: variationCount,
        checkpoint: "epicrealismXL_pureFix.safetensors",
        explore_mode: false, // Concept builder uses structured prompts
        auto_lora: false,
      });
      setBatch(resp.batch_id, resp.total_count);
    } catch (e) {
      console.error("Generation failed:", e);
    } finally {
      setIsGenerating(false);
    }
  }, [session, buildPrompt, negativePrompt, aspectRatio, variationCount, setStage, setBatch]);

  const handleRefine = useCallback(async () => {
    if (!session || selectedIds.length === 0) return;

    setIsGenerating(true);
    setStage("iterating");

    try {
      const resp = await api.submitFeedback({
        session_id: session.id,
        selected_image_ids: selectedIds,
        rejected_image_ids: [],
        action: "refine",
        feedback_text: "Refine with locked concepts",
      });

      if (resp) {
        clearSelections();
        advanceIteration();
        // Use the suggested prompt from backend
        // TODO: Parse structured fields from suggested prompt
      }
    } catch (e) {
      console.error("Refine failed:", e);
    } finally {
      setIsGenerating(false);
    }
  }, [session, selectedIds, iterationRound, setStage, clearSelections, advanceIteration]);

  const handleToggleLock = useCallback((field: keyof ConceptFieldState) => {
    setConcept((prev) => ({
      ...prev,
      [field]: {
        ...prev[field],
        locked: !prev[field].locked,
      },
    }));
  }, []);

  const handleFieldChange = useCallback((field: keyof ConceptFieldState, value: string) => {
    setConcept((prev) => ({
      ...prev,
      [field]: {
        ...prev[field],
        value,
      },
    }));
  }, []);

  const handleAddReference = useCallback((file: File, type: ReferenceImage["type"]) => {
    // Create a local URL for preview
    const url = URL.createObjectURL(file);
    const newRef: ReferenceImage = {
      id: `ref-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      url,
      type,
      strength: type === "face" ? 0.8 : 0.6, // Higher default for face preservation
      filename: file.name,
    };
    setReferences((prev) => [...prev, newRef]);
    // TODO: Upload to backend and get permanent URL
  }, []);

  const handleRemoveReference = useCallback((id: string) => {
    setReferences((prev) => {
      const ref = prev.find((r) => r.id === id);
      if (ref) {
        URL.revokeObjectURL(ref.url); // Clean up object URL
      }
      return prev.filter((r) => r.id !== id);
    });
  }, []);

  const handleUpdateReferenceStrength = useCallback((id: string, strength: number) => {
    setReferences((prev) =>
      prev.map((ref) => (ref.id === id ? { ...ref, strength } : ref))
    );
  }, []);


  const handleRejectAll = useCallback(async (feedbackText?: string) => {
    if (!session) return;

    rejectAllInStage(iterationRound);
    const rejectedIds = stageGens.map((g) => g.id);

    try {
      await api.rejectAll({
        session_id: session.id,
        stage: iterationRound,
        rejected_image_ids: rejectedIds,
        feedback_text: feedbackText,
      });
      console.log("Reject all recorded");
    } catch (e) {
      console.error("Reject all failed:", e);
    }
  }, [session, iterationRound, stageGens, rejectAllInStage]);

  const canGenerate = Object.values(concept).some((field) => field.value.trim() !== "");
  const hasResults = stageGens.length > 0;
  const canRefine = selectedIds.length > 0;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 bg-surface-1 border-b border-surface-3">
        <h2 className="text-xl font-bold text-gray-100 mb-1">Concept Builder</h2>
        <p className="text-sm text-gray-400">
          Define your concept field by field. Lock what you like, iterate on the rest.
        </p>
      </div>

      {/* Main content - split view */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left panel - Concept fields */}
        <div className="w-96 flex-shrink-0 bg-surface-1 border-r border-surface-3 flex flex-col">
          {/* Tabs */}
          <div className="flex border-b border-surface-3 flex-shrink-0">
            <button
              onClick={() => setActiveTab("concept")}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
                activeTab === "concept"
                  ? "border-accent text-accent"
                  : "border-transparent text-gray-400 hover:text-gray-300"
              }`}
            >
              Concept Fields
            </button>
            <button
              onClick={() => setActiveTab("references")}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
                activeTab === "references"
                  ? "border-accent text-accent"
                  : "border-transparent text-gray-400 hover:text-gray-300"
              }`}
            >
              References
              {references.length > 0 && (
                <span className="ml-1.5 px-1.5 py-0.5 bg-accent text-white text-xs rounded-full">
                  {references.length}
                </span>
              )}
            </button>
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto">
            {activeTab === "concept" ? (
              <ConceptFields
                concept={concept}
                onChange={handleFieldChange}
                onToggleLock={handleToggleLock}
              />
            ) : (
              <div className="p-4">
                <ReferenceImagePanel
                  references={references}
                  onAdd={handleAddReference}
                  onRemove={handleRemoveReference}
                  onUpdateStrength={handleUpdateReferenceStrength}
                />
              </div>
            )}
          </div>

          {/* Generation controls */}
          <div className="p-4 border-t border-surface-3 space-y-3">
            {/* Negative prompt */}
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">
                Negative Prompt
              </label>
              <textarea
                value={negativePrompt}
                onChange={(e) => setNegativePrompt(e.target.value)}
                placeholder="What to avoid..."
                className="w-full px-3 py-2 bg-surface-2 border border-surface-3 rounded-lg text-sm text-gray-100
                  placeholder-gray-500 focus:outline-none focus:border-accent resize-none"
                rows={2}
              />
            </div>

            {/* Aspect ratio */}
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">
                Aspect Ratio
              </label>
              <div className="flex gap-2">
                <button
                  onClick={() => setAspectRatio("portrait")}
                  className={`flex-1 px-3 py-2 text-xs rounded-lg transition-colors ${
                    aspectRatio === "portrait"
                      ? "bg-accent text-white"
                      : "bg-surface-2 text-gray-400 hover:bg-surface-3"
                  }`}
                >
                  Portrait
                </button>
                <button
                  onClick={() => setAspectRatio("landscape")}
                  className={`flex-1 px-3 py-2 text-xs rounded-lg transition-colors ${
                    aspectRatio === "landscape"
                      ? "bg-accent text-white"
                      : "bg-surface-2 text-gray-400 hover:bg-surface-3"
                  }`}
                >
                  Landscape
                </button>
                <button
                  onClick={() => setAspectRatio("square")}
                  className={`flex-1 px-3 py-2 text-xs rounded-lg transition-colors ${
                    aspectRatio === "square"
                      ? "bg-accent text-white"
                      : "bg-surface-2 text-gray-400 hover:bg-surface-3"
                  }`}
                >
                  Square
                </button>
              </div>
            </div>

            {/* Variation count */}
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1.5">
                Variations: {variationCount}
              </label>
              <input
                type="range"
                min="4"
                max="12"
                step="2"
                value={variationCount}
                onChange={(e) => setVariationCount(Number(e.target.value))}
                className="w-full"
              />
            </div>

            {/* Generate button */}
            <button
              onClick={handleGenerate}
              disabled={!canGenerate || isGenerating}
              className="w-full px-4 py-3 bg-accent hover:bg-accent-hover disabled:bg-surface-3 disabled:text-gray-600
                text-white font-semibold rounded-lg transition-colors"
            >
              {isGenerating ? "Generating..." : "Generate Variations"}
            </button>
          </div>
        </div>

        {/* Right panel - Results */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {!hasResults ? (
            <div className="flex-1 flex items-center justify-center text-gray-500">
              <div className="text-center">
                <svg
                  className="w-16 h-16 mx-auto mb-4 text-gray-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.5}
                    d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"
                  />
                </svg>
                <p className="text-lg font-medium mb-2">Build Your Concept</p>
                <p className="text-sm text-gray-600">
                  Fill in the fields on the left and generate variations
                </p>
              </div>
            </div>
          ) : (
            <>
              <div className="flex-1 overflow-y-auto p-6">
                <ImageGrid
                  generations={stageGens}
                  size="md"
                  showInfo={false}
                />
              </div>

              {/* Simple feedback bar for Concept Builder */}
              <div className="bg-surface-1 border-t border-surface-3 px-4 py-3 flex items-center gap-3">
                <span className="text-sm text-gray-400">
                  {selectedIds.length} selected of {stageGens.length}
                </span>

                {selectedIds.length > 0 && (
                  <button
                    onClick={() => clearSelections()}
                    className="text-xs text-gray-500 hover:text-gray-300"
                  >
                    Clear Selection
                  </button>
                )}

                <div className="flex-1" />

                {/* Reject All */}
                <button
                  onClick={() => handleRejectAll()}
                  disabled={isGenerating}
                  className="px-3 py-1.5 bg-red-900/20 hover:bg-red-900/30 text-sm text-red-400 rounded-lg
                    disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Reject All
                </button>

                {/* Refine */}
                <button
                  onClick={handleRefine}
                  disabled={!canRefine || isGenerating}
                  className="px-4 py-2 bg-accent hover:bg-accent-hover text-white font-medium rounded-lg
                    disabled:bg-surface-3 disabled:text-gray-600 disabled:cursor-not-allowed transition-colors"
                >
                  Refine Selected
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
