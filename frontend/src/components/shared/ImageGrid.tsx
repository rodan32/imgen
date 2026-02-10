import type { GenerationResult } from "@/types";
import { ImageCard } from "./ImageCard";

interface ImageGridProps {
  generations: GenerationResult[];
  size?: "sm" | "md" | "lg";
  showInfo?: boolean;
  emptyMessage?: string;
  emptyAction?: {
    label: string;
    onClick: () => void;
  };
}

export function ImageGrid({
  generations,
  size = "md",
  showInfo = false,
  emptyMessage = "No images yet",
  emptyAction,
}: ImageGridProps) {
  console.log("ImageGrid render:", generations.length, "generations");

  if (generations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[300px] text-gray-500">
        <svg
          className="w-16 h-16 mb-4 text-gray-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
        <p className="text-center text-lg mb-2">{emptyMessage}</p>
        {emptyAction && (
          <button
            onClick={emptyAction.onClick}
            className="mt-4 px-6 py-2.5 bg-accent text-white rounded-lg font-medium
              hover:bg-accent-hover transition-colors"
          >
            {emptyAction.label}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-3">
      {generations.map((gen) => {
        console.log("Rendering ImageCard:", gen.id, "selected:", gen.selected);
        return <ImageCard key={gen.id} generation={gen} size={size} showInfo={showInfo} />;
      })}
    </div>
  );
}
