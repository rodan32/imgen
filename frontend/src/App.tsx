import { useCallback } from "react";
import { useSessionStore } from "@/stores/sessionStore";
import { useGenerationStore } from "@/stores/generationStore";
import { GPUStatusBar } from "@/components/shared/GPUStatusBar";
import { FlowSelector } from "@/components/flows/FlowSelector";
import { DraftGridFlow } from "@/components/flows/DraftGrid/DraftGridFlow";
import type { FlowType } from "@/types";

export default function App() {
  const session = useSessionStore((s) => s.currentSession);
  const sessionStage = useSessionStore((s) => s.sessionStage);
  const createSession = useSessionStore((s) => s.createSession);
  const reset = useSessionStore((s) => s.reset);
  const resetGenerations = useGenerationStore((s) => s.reset);

  const handleSelectFlow = useCallback(
    async (flow: FlowType) => {
      resetGenerations();
      await createSession(flow);
    },
    [createSession, resetGenerations]
  );

  const handleBackToMenu = useCallback(() => {
    reset();
    resetGenerations();
  }, [reset, resetGenerations]);

  return (
    <div className="flex flex-col h-screen bg-surface-0">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-surface-1 border-b border-surface-3">
        <button
          onClick={handleBackToMenu}
          className="text-sm font-semibold text-accent hover:text-accent-hover"
        >
          Vibes ImGen
        </button>
        {session && (
          <span className="text-xs text-gray-500">
            Session: {session.id.slice(0, 8)}... | Flow: {session.flowType}
          </span>
        )}
      </div>

      {/* GPU status */}
      <GPUStatusBar />

      {/* Main content */}
      <div className="flex-1 overflow-hidden">
        {!session || sessionStage === "idle" ? (
          <FlowSelector onSelect={handleSelectFlow} />
        ) : session.flowType === "draft_grid" ? (
          <DraftGridFlow />
        ) : session.flowType === "concept_builder" ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            Concept Builder — coming soon
          </div>
        ) : session.flowType === "explorer" ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            Concept Explorer — coming soon
          </div>
        ) : null}
      </div>
    </div>
  );
}
