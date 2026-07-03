import type { ModeChoice } from '../types';

// Emits backend enum values directly (fix #2). "Auto" sends no mode so the
// backend uses the node default; picking any explicit mode = "Experimental"
// (any model at any node).
const MODES: { id: ModeChoice; label: string; hint: string }[] = [
  { id: 'auto', label: 'Auto', hint: "node's default mode" },
  { id: 'classical', label: 'Classical', hint: 'drift-diffusion' },
  { id: 'near_quantum', label: 'Near-Q', hint: 'leakage + short-channel' },
  { id: 'quantum', label: 'Quantum', hint: 'tunneling + ballistic' },
];

export function ModeToggle({
  value,
  onChange,
}: {
  value: ModeChoice;
  onChange: (m: ModeChoice) => void;
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">
        Physics mode
      </div>
      <div className="inline-flex flex-wrap gap-1 rounded-lg bg-slate-900 border border-zinc-800 p-1">
        {MODES.map((m) => {
          const active = m.id === value;
          return (
            <button
              key={m.id}
              title={m.hint}
              onClick={() => onChange(m.id)}
              className={`px-2.5 py-1.5 text-xs rounded-md transition-all ${
                active
                  ? 'bg-cyan-500/15 text-cyan-300 ring-1 ring-cyan-400/40'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {m.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
