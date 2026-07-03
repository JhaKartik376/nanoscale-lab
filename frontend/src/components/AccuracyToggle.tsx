import type { Accuracy } from '../types';

const LEVELS: { id: Accuracy; label: string }[] = [
  { id: 'low', label: 'Low' },
  { id: 'medium', label: 'Med' },
  { id: 'high', label: 'High' },
];

export function AccuracyToggle({
  value,
  onChange,
}: {
  value: Accuracy;
  onChange: (a: Accuracy) => void;
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">
        Accuracy <span className="text-slate-600">(grid resolution)</span>
      </div>
      <div className="inline-flex rounded-lg bg-slate-900 border border-zinc-800 p-1">
        {LEVELS.map((l) => {
          const active = l.id === value;
          return (
            <button
              key={l.id}
              onClick={() => onChange(l.id)}
              className={`px-3 py-1.5 text-xs rounded-md transition-all ${
                active
                  ? 'bg-cyan-500/15 text-cyan-300 ring-1 ring-cyan-400/40'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {l.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
