import { useState, useEffect } from "react";

interface PromptChangeNotificationProps {
  oldPrompt: string;
  newPrompt: string;
  rationale: string;
  onDismiss: () => void;
}

export function PromptChangeNotification({
  oldPrompt,
  newPrompt,
  rationale,
  onDismiss,
}: PromptChangeNotificationProps) {
  const [isVisible, setIsVisible] = useState(true);

  // Auto-dismiss after 15 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(false);
      setTimeout(onDismiss, 300); // Wait for fade-out animation
    }, 15000);

    return () => clearTimeout(timer);
  }, [onDismiss]);

  if (!isVisible) {
    return null;
  }

  // Find what changed
  const changes = findChanges(oldPrompt, newPrompt);

  return (
    <div
      className={`fixed top-20 right-6 max-w-md bg-blue-900/95 border border-blue-500/50 rounded-lg shadow-lg
        backdrop-blur-sm transition-all duration-300 ${isVisible ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-4"}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between px-4 py-3 border-b border-blue-500/30">
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 10V3L4 14h7v7l9-11h-7z"
            />
          </svg>
          <h3 className="text-sm font-semibold text-blue-100">Prompt Refined</h3>
        </div>
        <button
          onClick={() => {
            setIsVisible(false);
            setTimeout(onDismiss, 300);
          }}
          className="text-blue-300 hover:text-blue-100 transition-colors"
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </div>

      {/* Rationale */}
      <div className="px-4 py-3 border-b border-blue-500/30">
        <p className="text-sm text-blue-100 leading-relaxed">{rationale}</p>
      </div>

      {/* Changes */}
      {changes.length > 0 && (
        <div className="px-4 py-3">
          <p className="text-xs font-medium text-blue-300 mb-2">Changes:</p>
          <div className="space-y-1">
            {changes.map((change, idx) => (
              <div key={idx} className="flex items-start gap-2 text-xs">
                {change.type === "added" && (
                  <>
                    <span className="text-green-400 flex-shrink-0">+</span>
                    <span className="text-green-300">{change.text}</span>
                  </>
                )}
                {change.type === "removed" && (
                  <>
                    <span className="text-red-400 flex-shrink-0">-</span>
                    <span className="text-red-300 line-through">{change.text}</span>
                  </>
                )}
                {change.type === "modified" && (
                  <>
                    <span className="text-yellow-400 flex-shrink-0">~</span>
                    <span className="text-yellow-300">{change.text}</span>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-2 bg-blue-950/50 rounded-b-lg">
        <p className="text-xs text-blue-400">
          The prompt field has been updated. Review before generating.
        </p>
      </div>
    </div>
  );
}

interface Change {
  type: "added" | "removed" | "modified";
  text: string;
}

function findChanges(oldText: string, newText: string): Change[] {
  // Simple word-level diff
  const oldWords = new Set(oldText.toLowerCase().split(/\s+/));
  const newWords = newText.toLowerCase().split(/\s+/);
  const newWordsSet = new Set(newWords);

  const changes: Change[] = [];

  // Find removed words/phrases
  for (const word of oldWords) {
    if (!newWordsSet.has(word) && word.length > 2) {
      changes.push({ type: "removed", text: word });
    }
  }

  // Find added words/phrases
  for (const word of newWords) {
    if (!oldWords.has(word) && word.length > 2) {
      changes.push({ type: "added", text: word });
    }
  }

  // Limit to first 5 changes to avoid clutter
  return changes.slice(0, 5);
}
