import { create } from "zustand";
import type { FlowType, Session, SessionStage } from "@/types";
import * as api from "@/api/client";

interface SessionState {
  currentSession: Session | null;
  sessionStage: SessionStage;
  iterationRound: number;
  error: string | null;

  createSession: (flowType: FlowType) => Promise<void>;
  loadSession: (id: string) => Promise<void>;
  setStage: (stage: SessionStage) => void;
  advanceIteration: () => void;
  reset: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  currentSession: null,
  sessionStage: "idle",
  iterationRound: 0,
  error: null,

  createSession: async (flowType) => {
    try {
      const resp = await api.createSession(flowType);
      set({
        currentSession: {
          id: resp.id,
          flowType: resp.flow_type as FlowType,
          createdAt: resp.created_at,
          currentStage: 0,
          config: null,
        },
        sessionStage: "configuring",
        iterationRound: 0,
        error: null,
      });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  loadSession: async (id) => {
    try {
      const resp = await api.getSession(id);
      set({
        currentSession: {
          id: resp.id,
          flowType: resp.flow_type as FlowType,
          createdAt: "",
          currentStage: resp.current_stage,
          config: null,
        },
        sessionStage: "reviewing",
        iterationRound: resp.current_stage,
        error: null,
      });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  setStage: (stage) => set({ sessionStage: stage }),

  advanceIteration: () =>
    set((s) => ({
      iterationRound: s.iterationRound + 1,
      sessionStage: "generating",
    })),

  reset: () =>
    set({
      currentSession: null,
      sessionStage: "idle",
      iterationRound: 0,
      error: null,
    }),
}));
