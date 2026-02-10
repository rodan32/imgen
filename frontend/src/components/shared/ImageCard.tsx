import type { GenerationResult } from "@/types";
import { useGenerationStore } from "@/stores/generationStore";

interface ImageCardProps {
  generation: GenerationResult;
  size?: "sm" | "md" | "lg";
  showInfo?: boolean;
}

// Base widths for each size - height will be calculated from aspect ratio
const sizeWidths = {
  sm: 128,  // w-32
  md: 192,  // w-48
  lg: 288,  // w-72
};

function getImageDimensions(generation: GenerationResult, size: "sm" | "md" | "lg") {
  const baseWidth = sizeWidths[size];

  // Try to get actual aspect ratio from generation parameters
  const params = generation.parameters as any;
  const width = params?.width || 512;
  const height = params?.height || 512;
  const aspectRatio = width / height;

  // Calculate actual dimensions
  const cardWidth = baseWidth;
  const cardHeight = Math.round(baseWidth / aspectRatio);

  return {
    width: cardWidth,
    height: cardHeight,
    aspectRatio,
  };
}

export function ImageCard({ generation, size = "md", showInfo = false }: ImageCardProps) {
  const toggleSelect = useGenerationStore((s) => s.toggleSelect);
  const progress = useGenerationStore((s) => s.activeProgress[generation.id]);

  // Subscribe to this specific generation's state from the store
  const storeGeneration = useGenerationStore((s) => s.generations[generation.id]);
  const selected = storeGeneration?.selected ?? generation.selected;
  const rejected = storeGeneration?.rejected ?? generation.rejected;

  const isLoading = !!progress;
  const borderColor = selected
    ? "border-accent"
    : rejected
      ? "border-danger/50"
      : "border-surface-3";

  const handleClick = () => {
    console.log("ImageCard clicked:", generation.id, "current selected:", selected);
    toggleSelect(generation.id);
  };

  const dimensions = getImageDimensions(generation, size);

  return (
    <div
      className={`relative rounded-lg overflow-hidden border-2 cursor-pointer
        transition-all hover:border-accent/50 ${borderColor}`}
      style={{ width: `${dimensions.width}px`, height: `${dimensions.height}px` }}
      onClick={handleClick}
    >
      {isLoading ? (
        <div className="w-full h-full flex flex-col items-center justify-center bg-surface-2">
          <div className="w-3/4 h-2 bg-surface-3 rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all duration-300"
              style={{ width: `${progress.percent}%` }}
            />
          </div>
          <span className="text-xs text-gray-400 mt-2">
            {progress.step}/{progress.totalSteps}
          </span>
        </div>
      ) : (
        <img
          src={generation.thumbnailUrl}
          alt=""
          className="w-full h-full object-cover"
          loading="lazy"
        />
      )}

      {/* Selection indicator */}
      {selected && (
        <div className="absolute top-1 right-1 w-6 h-6 bg-accent rounded-full flex items-center justify-center">
          <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        </div>
      )}

      {/* Info overlay */}
      {showInfo && !isLoading && (
        <div className="absolute bottom-0 left-0 right-0 bg-black/60 px-2 py-1 text-xs text-gray-300">
          {generation.seed != null && <span>seed: {generation.seed}</span>}
          {generation.generationTimeMs != null && (
            <span className="ml-2">{(generation.generationTimeMs / 1000).toFixed(1)}s</span>
          )}
        </div>
      )}
    </div>
  );
}
