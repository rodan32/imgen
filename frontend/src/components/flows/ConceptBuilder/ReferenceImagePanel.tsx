import { useState, useCallback, useRef } from "react";

export interface ReferenceImage {
  id: string;
  url: string;
  type: "face" | "pose" | "depth" | "canny" | "composition";
  strength: number;
  filename: string;
}

interface ReferenceImagePanelProps {
  references: ReferenceImage[];
  onAdd: (file: File, type: ReferenceImage["type"]) => void;
  onRemove: (id: string) => void;
  onUpdateStrength: (id: string, strength: number) => void;
}

const REFERENCE_TYPES = [
  { value: "face", label: "Face/Character", icon: "👤", description: "Preserve face/character identity" },
  { value: "pose", label: "Pose Control", icon: "🧍", description: "Guide body pose" },
  { value: "depth", label: "Depth Map", icon: "🗺️", description: "Control depth/distance" },
  { value: "canny", label: "Edge Control", icon: "📐", description: "Follow edge structure" },
  { value: "composition", label: "Composition", icon: "🖼️", description: "Overall layout guide" },
] as const;

export function ReferenceImagePanel({
  references,
  onAdd,
  onRemove,
  onUpdateStrength,
}: ReferenceImagePanelProps) {
  const [selectedType, setSelectedType] = useState<ReferenceImage["type"]>("face");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        onAdd(file, selectedType);
        // Reset input
        e.target.value = "";
      }
    },
    [onAdd, selectedType]
  );

  const handleUploadClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  return (
    <div className="space-y-4">
      {/* Upload section */}
      <div className="bg-surface-2 rounded-lg p-4 border border-surface-3">
        <h3 className="text-sm font-semibold text-gray-300 mb-3">Add Reference Image</h3>

        {/* Type selector */}
        <div className="mb-3">
          <label className="block text-xs text-gray-400 mb-2">Reference Type</label>
          <div className="grid grid-cols-1 gap-2">
            {REFERENCE_TYPES.map((type) => (
              <button
                key={type.value}
                onClick={() => setSelectedType(type.value)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-colors text-xs ${
                  selectedType === type.value
                    ? "bg-accent text-white"
                    : "bg-surface-3 text-gray-400 hover:bg-surface-3/70"
                }`}
              >
                <span className="text-base">{type.icon}</span>
                <div className="flex-1">
                  <div className="font-medium">{type.label}</div>
                  <div className="text-xs opacity-80">{type.description}</div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Upload button */}
        <button
          onClick={handleUploadClick}
          className="w-full px-4 py-3 bg-surface-3 hover:bg-surface-3/70 text-gray-300 rounded-lg
            border-2 border-dashed border-gray-600 hover:border-accent transition-colors text-sm font-medium"
        >
          <span className="flex items-center justify-center gap-2">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
            Upload Image
          </span>
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>

      {/* Active references */}
      {references.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-gray-300">Active References</h3>
          {references.map((ref) => {
            const typeConfig = REFERENCE_TYPES.find((t) => t.value === ref.type);
            return (
              <div
                key={ref.id}
                className="bg-surface-2 rounded-lg border border-surface-3 p-3 space-y-2"
              >
                <div className="flex items-start gap-3">
                  {/* Thumbnail */}
                  <img
                    src={ref.url}
                    alt={ref.filename}
                    className="w-16 h-16 object-cover rounded border border-surface-3 flex-shrink-0"
                  />

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-base">{typeConfig?.icon}</span>
                        <span className="text-xs font-medium text-gray-300">
                          {typeConfig?.label}
                        </span>
                      </div>
                      <button
                        onClick={() => onRemove(ref.id)}
                        className="text-gray-500 hover:text-red-400 transition-colors"
                        title="Remove reference"
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
                    <p className="text-xs text-gray-500 truncate" title={ref.filename}>
                      {ref.filename}
                    </p>
                  </div>
                </div>

                {/* Strength slider */}
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="text-xs text-gray-400">Influence</label>
                    <span className="text-xs text-gray-300 font-mono">
                      {(ref.strength * 100).toFixed(0)}%
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="5"
                    value={ref.strength * 100}
                    onChange={(e) => onUpdateStrength(ref.id, Number(e.target.value) / 100)}
                    className="w-full h-2 bg-surface-3 rounded-lg appearance-none cursor-pointer
                      [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4
                      [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full
                      [&::-webkit-slider-thumb]:bg-accent [&::-webkit-slider-thumb]:cursor-pointer"
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Help text */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
        <div className="flex items-start gap-2">
          <svg
            className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
              clipRule="evenodd"
            />
          </svg>
          <div className="text-xs text-blue-300 leading-relaxed">
            <strong>Tip:</strong> Use Face/Character references to maintain consistent characters
            across generations. Pose Control helps guide body positions. Multiple references can be
            combined.
          </div>
        </div>
      </div>
    </div>
  );
}
