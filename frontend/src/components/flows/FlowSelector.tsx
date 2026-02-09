import type { FlowType } from "@/types";

interface FlowSelectorProps {
  onSelect: (flow: FlowType) => void;
}

const flows = [
  {
    id: "draft_grid" as FlowType,
    title: "Draft Grid",
    description: "Start with a simple prompt, generate a grid of quick drafts, then refine your favorites through a quality funnel.",
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM14 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zM14 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
      </svg>
    ),
  },
  {
    id: "concept_builder" as FlowType,
    title: "Concept Builder",
    description: "Define subjects, poses, and backgrounds step by step. Lock concepts you like and iterate on the rest.",
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
      </svg>
    ),
  },
  {
    id: "explorer" as FlowType,
    title: "Concept Explorer",
    description: "Browse LoRAs and concepts, generate showcase images, combine styles, and compare results side by side.",
    icon: (
      <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
  },
];

export function FlowSelector({ onSelect }: FlowSelectorProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4">
      <h1 className="text-3xl font-bold text-gray-100 mb-2">Vibes ImGen</h1>
      <p className="text-gray-400 mb-10">Choose a generation flow to get started</p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl w-full">
        {flows.map((flow) => (
          <button
            key={flow.id}
            onClick={() => onSelect(flow.id)}
            className="bg-surface-1 border border-surface-3 rounded-xl p-6 text-left
              hover:border-accent/50 hover:bg-surface-2 transition-all group"
          >
            <div className="text-accent group-hover:text-accent-hover mb-4">
              {flow.icon}
            </div>
            <h3 className="text-lg font-semibold text-gray-100 mb-2">{flow.title}</h3>
            <p className="text-sm text-gray-400 leading-relaxed">{flow.description}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
