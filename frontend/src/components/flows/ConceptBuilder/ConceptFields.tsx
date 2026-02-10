import type { ConceptFieldState } from "./ConceptBuilderFlow";

interface ConceptFieldsProps {
  concept: ConceptFieldState;
  onChange: (field: keyof ConceptFieldState, value: string) => void;
  onToggleLock: (field: keyof ConceptFieldState) => void;
}

const FIELD_CONFIGS: Array<{
  key: keyof ConceptFieldState;
  label: string;
  placeholder: string;
  description: string;
}> = [
  {
    key: "subject",
    label: "Subject",
    placeholder: "e.g., a woman with long brown hair, green eyes",
    description: "The main subject of the image",
  },
  {
    key: "pose",
    label: "Pose & Action",
    placeholder: "e.g., standing confidently, arms crossed",
    description: "Body position and activity",
  },
  {
    key: "background",
    label: "Background",
    placeholder: "e.g., cyberpunk city at night, neon lights",
    description: "Scene and environment",
  },
  {
    key: "style",
    label: "Art Style",
    placeholder: "e.g., digital art, cinematic, photorealistic",
    description: "Overall visual style",
  },
  {
    key: "lighting",
    label: "Lighting",
    placeholder: "e.g., dramatic rim lighting, golden hour",
    description: "Light quality and direction",
  },
  {
    key: "mood",
    label: "Mood & Atmosphere",
    placeholder: "e.g., mysterious, energetic, serene",
    description: "Emotional tone",
  },
  {
    key: "camera",
    label: "Camera Angle",
    placeholder: "e.g., close-up portrait, wide angle, from below",
    description: "Perspective and framing",
  },
];

export function ConceptFields({ concept, onChange, onToggleLock }: ConceptFieldsProps) {
  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-2 text-xs text-gray-500 mb-4">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <span>Lock fields to preserve them during refinement</span>
      </div>

      {FIELD_CONFIGS.map((field) => {
        const fieldState = concept[field.key];
        const isLocked = fieldState.locked;
        const hasValue = fieldState.value.trim() !== "";

        return (
          <div
            key={field.key}
            className={`relative rounded-lg border-2 transition-all ${
              isLocked
                ? "border-yellow-500/50 bg-yellow-500/5"
                : "border-surface-3 bg-surface-2"
            }`}
          >
            <div className="p-3">
              {/* Header */}
              <div className="flex items-center justify-between mb-2">
                <div>
                  <label className="block text-xs font-semibold text-gray-300">
                    {field.label}
                  </label>
                  <p className="text-xs text-gray-500">{field.description}</p>
                </div>
                <button
                  onClick={() => onToggleLock(field.key)}
                  disabled={!hasValue}
                  className={`p-1.5 rounded transition-colors ${
                    isLocked
                      ? "text-yellow-400 hover:text-yellow-300"
                      : hasValue
                      ? "text-gray-500 hover:text-gray-400"
                      : "text-gray-700 cursor-not-allowed"
                  }`}
                  title={isLocked ? "Unlock field" : "Lock field"}
                >
                  {isLocked ? (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M10 2a5 5 0 00-5 5v2a2 2 0 00-2 2v5a2 2 0 002 2h10a2 2 0 002-2v-5a2 2 0 00-2-2H7V7a3 3 0 015.905-.75 1 1 0 001.937-.5A5.002 5.002 0 0010 2z" />
                    </svg>
                  )}
                </button>
              </div>

              {/* Input */}
              <textarea
                value={fieldState.value}
                onChange={(e) => onChange(field.key, e.target.value)}
                placeholder={field.placeholder}
                disabled={isLocked}
                className={`w-full px-3 py-2 bg-surface-0 border rounded-md text-sm
                  placeholder-gray-600 focus:outline-none resize-none transition-colors ${
                    isLocked
                      ? "border-yellow-500/30 text-gray-400 cursor-not-allowed"
                      : "border-surface-3 text-gray-100 focus:border-accent"
                  }`}
                rows={2}
              />

              {/* Locked indicator */}
              {isLocked && (
                <div className="flex items-center gap-1.5 mt-2 text-xs text-yellow-400">
                  <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                    <path
                      fillRule="evenodd"
                      d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <span>Locked - will remain unchanged during refinement</span>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
