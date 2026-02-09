import { useEffect, useRef } from "react";
import { useGenerationStore } from "@/stores/generationStore";
import type { WSMessage } from "@/types";

/**
 * Connects to the backend WebSocket for a session.
 * Routes incoming messages to the generation store.
 * Auto-reconnects with exponential backoff.
 */
export function useWebSocket(sessionId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<ReturnType<typeof setTimeout>>(undefined);
  const backoff = useRef(1000);

  useEffect(() => {
    if (!sessionId) return;

    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const url = `${protocol}//${host}/ws/session/${sessionId}`;

      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        backoff.current = 1000; // reset on success
      };

      ws.onmessage = (event) => {
        try {
          const msg: WSMessage = JSON.parse(event.data);
          handleMessage(msg);
        } catch {
          // ignore non-JSON messages
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        // Reconnect with backoff
        reconnectTimeout.current = setTimeout(() => {
          backoff.current = Math.min(backoff.current * 2, 30000);
          connect();
        }, backoff.current);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    function handleMessage(msg: WSMessage) {
      const s = useGenerationStore.getState();

      switch (msg.type) {
        case "generation_progress":
          s.updateProgress(msg.generationId, msg.step, msg.totalSteps);
          break;

        case "generation_complete":
          s.clearProgress(msg.generationId);
          s.addGeneration({
            id: msg.generationId,
            sessionId: sessionId!,
            stage: 0, // will be updated when we fetch full details
            prompt: "",
            negativePrompt: "",
            imageUrl: msg.imageUrl,
            thumbnailUrl: msg.thumbnailUrl,
            gpuId: msg.gpuId,
            generationTimeMs: msg.generationTimeMs,
            parameters: null,
            seed: msg.seed,
            createdAt: new Date().toISOString(),
            selected: false,
            rejected: false,
          });
          break;

        case "batch_progress":
          s.incrementBatchCompleted();
          if (msg.latestResult) {
            s.addGeneration({
              id: msg.latestResult.generationId,
              sessionId: sessionId!,
              stage: 0,
              prompt: "",
              negativePrompt: "",
              imageUrl: msg.latestResult.imageUrl,
              thumbnailUrl: msg.latestResult.thumbnailUrl,
              gpuId: null,
              generationTimeMs: null,
              parameters: null,
              seed: null,
              createdAt: new Date().toISOString(),
              selected: false,
              rejected: false,
            });
          }
          break;

        case "batch_complete":
          s.completeBatch();
          break;

        case "error":
          console.error("Generation error:", msg.message);
          s.clearProgress(msg.generationId);
          break;
      }
    }

    connect();

    // Send periodic keepalive
    const keepalive = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send("ping");
      }
    }, 30000);

    return () => {
      clearInterval(keepalive);
      clearTimeout(reconnectTimeout.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [sessionId]);
}
