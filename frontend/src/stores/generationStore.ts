import { create } from "zustand";
import type { GenerationResult, BatchProgress } from "@/types";

interface GenerationState {
  // All generations for current session, keyed by ID
  generations: Record<string, GenerationResult>;
  // Batch tracking
  activeBatch: BatchProgress | null;
  // Per-generation progress (step tracking for active generations)
  activeProgress: Record<string, { step: number; totalSteps: number; percent: number }>;

  // Actions
  addGeneration: (gen: GenerationResult) => void;
  addGenerationFromServer: (raw: {
    id: string; session_id: string; stage: number; prompt: string;
    negative_prompt: string; image_url: string; thumbnail_url: string;
    gpu_id: string; generation_time_ms: number; seed: number; created_at: string;
  }) => void;
  updateProgress: (genId: string, step: number, totalSteps: number) => void;
  clearProgress: (genId: string) => void;
  toggleSelect: (genId: string) => void;
  toggleReject: (genId: string) => void;
  clearSelections: () => void;
  rejectAllInStage: (stage: number) => void;
  getSelectedIds: () => string[];
  getRejectedIds: () => string[];
  getStageGenerations: (stage: number) => GenerationResult[];
  setBatch: (batchId: string, total: number) => void;
  incrementBatchCompleted: () => void;
  completeBatch: () => void;
  reset: () => void;
}

export const useGenerationStore = create<GenerationState>((set, get) => ({
  generations: {},
  activeBatch: null,
  activeProgress: {},

  addGeneration: (gen) =>
    set((s) => {
      // If generation already exists, preserve user state (selected/rejected)
      const existing = s.generations[gen.id];
      if (existing) {
        return {
          generations: {
            ...s.generations,
            [gen.id]: { ...gen, selected: existing.selected, rejected: existing.rejected },
          },
        };
      }
      return {
        generations: { ...s.generations, [gen.id]: gen },
      };
    }),

  addGenerationFromServer: (raw) =>
    set((s) => ({
      generations: {
        ...s.generations,
        [raw.id]: {
          id: raw.id,
          sessionId: raw.session_id,
          stage: raw.stage,
          prompt: raw.prompt,
          negativePrompt: raw.negative_prompt,
          imageUrl: raw.image_url,
          thumbnailUrl: raw.thumbnail_url,
          gpuId: raw.gpu_id,
          generationTimeMs: raw.generation_time_ms,
          parameters: null,
          seed: raw.seed,
          createdAt: raw.created_at,
          selected: false,
          rejected: false,
        },
      },
    })),

  updateProgress: (genId, step, totalSteps) =>
    set((s) => ({
      activeProgress: {
        ...s.activeProgress,
        [genId]: { step, totalSteps, percent: totalSteps > 0 ? (step / totalSteps) * 100 : 0 },
      },
    })),

  clearProgress: (genId) =>
    set((s) => {
      const { [genId]: _, ...rest } = s.activeProgress;
      return { activeProgress: rest };
    }),

  toggleSelect: (genId) =>
    set((s) => {
      const gen = s.generations[genId];
      console.log("toggleSelect:", genId, "exists:", !!gen, "current selected:", gen?.selected);
      if (!gen) return s;
      const updated = { ...gen, selected: !gen.selected, rejected: false };
      console.log("toggleSelect: new selected state:", updated.selected);
      return {
        generations: {
          ...s.generations,
          [genId]: updated,
        },
      };
    }),

  toggleReject: (genId) =>
    set((s) => {
      const gen = s.generations[genId];
      if (!gen) return s;
      return {
        generations: {
          ...s.generations,
          [genId]: { ...gen, rejected: !gen.rejected, selected: false },
        },
      };
    }),

  clearSelections: () =>
    set((s) => {
      const updated: Record<string, GenerationResult> = {};
      for (const [id, gen] of Object.entries(s.generations)) {
        updated[id] = { ...gen, selected: false, rejected: false };
      }
      return { generations: updated };
    }),

  rejectAllInStage: (stage) =>
    set((s) => {
      const updated: Record<string, GenerationResult> = {};
      for (const [id, gen] of Object.entries(s.generations)) {
        if (gen.stage === stage) {
          updated[id] = { ...gen, rejected: true, selected: false };
        } else {
          updated[id] = gen;
        }
      }
      return { generations: updated };
    }),

  getSelectedIds: () =>
    Object.values(get().generations)
      .filter((g) => g.selected)
      .map((g) => g.id),

  getRejectedIds: () =>
    Object.values(get().generations)
      .filter((g) => g.rejected)
      .map((g) => g.id),

  getStageGenerations: (stage) =>
    Object.values(get().generations)
      .filter((g) => g.stage === stage)
      .sort((a, b) => a.createdAt.localeCompare(b.createdAt)),

  setBatch: (batchId, total) =>
    set({ activeBatch: { batchId, completed: 0, total } }),

  incrementBatchCompleted: () =>
    set((s) => ({
      activeBatch: s.activeBatch
        ? { ...s.activeBatch, completed: s.activeBatch.completed + 1 }
        : null,
    })),

  completeBatch: () => set({ activeBatch: null }),

  reset: () =>
    set({
      generations: {},
      activeBatch: null,
      activeProgress: {},
    }),
}));
