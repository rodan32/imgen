import { create } from "zustand";
import type { GPUStatus } from "@/types";
import * as api from "@/api/client";

interface GPUState {
  gpus: GPUStatus[];
  loading: boolean;

  fetchGPUs: () => Promise<void>;
  startPolling: (intervalMs?: number) => () => void;
}

export const useGPUStore = create<GPUState>((set) => ({
  gpus: [],
  loading: false,

  fetchGPUs: async () => {
    set({ loading: true });
    try {
      const data = await api.getGPUs();
      set({
        gpus: data.map((g) => ({
          id: g.id,
          name: g.name,
          tier: g.tier,
          vramGb: g.vram_gb,
          healthy: g.healthy,
          currentQueueLength: g.current_queue_length,
          capabilities: g.capabilities,
          lastResponseMs: g.last_response_ms,
        })),
        loading: false,
      });
    } catch {
      set({ loading: false });
    }
  },

  startPolling: (intervalMs = 10000) => {
    const id = setInterval(() => {
      useGPUStore.getState().fetchGPUs();
    }, intervalMs);
    // Fetch immediately
    useGPUStore.getState().fetchGPUs();
    // Return cleanup function
    return () => clearInterval(id);
  },
}));
