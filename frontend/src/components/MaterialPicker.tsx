import type { Material } from '../types';

const MATERIALS: { id: Material; label: string; hint: string }[] = [
  { id: 'Si', label: 'Silicon', hint: 'Eg 1.12 eV — the baseline switch' },
  { id: 'CNT', label: 'CNT', hint: 'light m*, high mobility — more drive' },
  { id: 'Graphene', label: 'Graphene', hint: 'gapless — great conductor, poor switch' },
];

export function MaterialPicker({
  value,
  onChange,
}: {
  value: Material;
  onChange: (m: Material) => void;
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-slate-400 mb-2">
        Channel material
      </div>
      <div className="inline-flex flex-wrap gap-1 rounded-lg bg-slate-900 border border-zinc-800 p-1">
        {MATERIALS.map((m) => {
          const active = m.id === value;
          return (
            <button
              key={m.id}
              title={m.hint}
              onClick={() => onChange(m.id)}
              className={`px-2.5 py-1.5 text-xs rounded-md transition-all ${
                active
                  ? 'bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-400/40'
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
