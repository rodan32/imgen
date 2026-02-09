import { useEffect } from "react";
import { useGPUStore } from "@/stores/gpuStore";

const tierColors: Record<string, string> = {
  premium: "text-purple-400",
  quality: "text-blue-400",
  standard: "text-green-400",
  draft: "text-yellow-400",
};

export function GPUStatusBar() {
  const gpus = useGPUStore((s) => s.gpus);
  const startPolling = useGPUStore((s) => s.startPolling);

  useEffect(() => {
    const stop = startPolling(10000);
    return stop;
  }, [startPolling]);

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-surface-1 border-b border-surface-3">
      <span className="text-xs text-gray-500 uppercase tracking-wide">GPUs</span>
      {gpus.map((gpu) => (
        <div key={gpu.id} className="flex items-center gap-1.5">
          <div
            className={`w-2 h-2 rounded-full ${gpu.healthy ? "bg-success" : "bg-danger"}`}
          />
          <span className={`text-xs ${tierColors[gpu.tier] || "text-gray-400"}`}>
            {gpu.name}
          </span>
          {gpu.currentQueueLength > 0 && (
            <span className="text-xs text-gray-500">({gpu.currentQueueLength})</span>
          )}
        </div>
      ))}
      {gpus.length === 0 && (
        <span className="text-xs text-gray-500">No GPUs registered</span>
      )}
    </div>
  );
}
