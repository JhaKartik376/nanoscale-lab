import type { Sweep } from '../types';

const SWEEPS: { id: Sweep; label: string }[] = [
  { id: 'idvg', label: 'Id-Vg' },
  { id: 'idvd', label: 'Id-Vd' },
  { id: 'leakage', label: 'Leakage vs Node' },
  { id: 'tunneling', label: 'Tunneling vs Width' },
];

export function SweepSelector({
  value,
  onChange,
}: {
  value: Sweep;
  onChange: (s: Sweep) => void;
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">
        Sweep
      </div>
      <div className="flex flex-col gap-1">
        {SWEEPS.map((s) => (
          <button
            key={s.id}
            onClick={() => onChange(s.id)}
            className={`text-left px-3 py-1.5 text-sm rounded-md transition-colors ${
              s.id === value
                ? 'bg-slate-800 text-cyan-300'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            {s.id === value ? '▸ ' : '  '}
            {s.label}
          </button>
        ))}
      </div>
    </div>
  );
}
