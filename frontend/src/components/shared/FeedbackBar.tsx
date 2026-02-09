import { useState } from "react";

interface FeedbackBarProps {
  selectedCount: number;
  onMoreLikeThis: () => void;
  onRefine: (feedback: string) => void;
  onAdvance: () => void;
  onClearSelection: () => void;
  advanceLabel?: string;
  showRefine?: boolean;
}

export function FeedbackBar({
  selectedCount,
  onMoreLikeThis,
  onRefine,
  onAdvance,
  onClearSelection,
  advanceLabel = "Refine Selected",
  showRefine = true,
}: FeedbackBarProps) {
  const [feedbackText, setFeedbackText] = useState("");
  const [showInput, setShowInput] = useState(false);

  return (
    <div className="bg-surface-1 border-t border-surface-3 px-4 py-3">
      <div className="flex items-center gap-3">
        <span className="text-sm text-gray-400">
          {selectedCount} selected
        </span>

        <button
          onClick={onClearSelection}
          disabled={selectedCount === 0}
          className="text-xs text-gray-500 hover:text-gray-300 disabled:opacity-30"
        >
          Clear
        </button>

        <div className="flex-1" />

        <button
          onClick={onMoreLikeThis}
          disabled={selectedCount === 0}
          className="px-3 py-1.5 bg-surface-2 text-sm text-gray-300 rounded-lg
            hover:bg-surface-3 disabled:opacity-30 transition-colors"
        >
          More Like This
        </button>

        {showRefine && (
          <button
            onClick={() => setShowInput(!showInput)}
            disabled={selectedCount === 0}
            className="px-3 py-1.5 bg-surface-2 text-sm text-gray-300 rounded-lg
              hover:bg-surface-3 disabled:opacity-30 transition-colors"
          >
            Refine
          </button>
        )}

        <button
          onClick={onAdvance}
          disabled={selectedCount === 0}
          className="px-4 py-1.5 bg-accent text-sm text-white rounded-lg
            hover:bg-accent-hover disabled:opacity-30 transition-colors font-medium"
        >
          {advanceLabel} &rarr;
        </button>
      </div>

      {showInput && (
        <div className="mt-3 flex gap-2">
          <input
            type="text"
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            placeholder="What would you like to change? (e.g., 'make it darker', 'more dramatic lighting')"
            className="flex-1 bg-surface-2 border border-surface-3 rounded-lg px-3 py-2
              text-sm text-gray-100 placeholder-gray-500
              focus:outline-none focus:border-accent"
            onKeyDown={(e) => {
              if (e.key === "Enter" && feedbackText.trim()) {
                onRefine(feedbackText);
                setFeedbackText("");
                setShowInput(false);
              }
            }}
          />
          <button
            onClick={() => {
              if (feedbackText.trim()) {
                onRefine(feedbackText);
                setFeedbackText("");
                setShowInput(false);
              }
            }}
            className="px-4 py-2 bg-accent text-sm text-white rounded-lg hover:bg-accent-hover"
          >
            Apply
          </button>
        </div>
      )}
    </div>
  );
}
