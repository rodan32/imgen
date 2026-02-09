import type { GenerationResult } from "@/types";
import { ImageCard } from "./ImageCard";

interface ImageGridProps {
  generations: GenerationResult[];
  size?: "sm" | "md" | "lg";
  showInfo?: boolean;
}

export function ImageGrid({ generations, size = "md", showInfo = false }: ImageGridProps) {
  console.log("ImageGrid render:", generations.length, "generations");

  if (generations.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-500">
        No images yet
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
