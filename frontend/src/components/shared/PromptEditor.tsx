import { useState } from "react";

interface PromptEditorProps {
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  label?: string;
}

export function PromptEditor({
  value,
  onChange,
  placeholder = "Enter your prompt...",
  label = "Prompt",
}: PromptEditorProps) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-300 mb-1">{label}</label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={3}
        className="w-full bg-surface-2 border border-surface-3 rounded-lg px-3 py-2
          text-gray-100 placeholder-gray-500 resize-none
          focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent"
      />
      <div className="text-xs text-gray-500 mt-1 text-right">
        {value.split(/[,\s]+/).filter(Boolean).length} tokens
      </div>
    </div>
  );
}

interface NegativePromptProps {
  value: string;
  onChange: (val: string) => void;
}

export function NegativePromptEditor({ value, onChange }: NegativePromptProps) {
  const [open, setOpen] = useState(false);

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="text-xs text-gray-400 hover:text-gray-300 flex items-center gap-1"
      >
        <svg
          className={`w-3 h-3 transition-transform ${open ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        Negative prompt
      </button>
      {open && (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Things to avoid..."
          rows={2}
          className="w-full mt-1 bg-surface-2 border border-surface-3 rounded-lg px-3 py-2
            text-gray-100 placeholder-gray-500 resize-none text-sm
            focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent"
        />
      )}
    </div>
  );
}
