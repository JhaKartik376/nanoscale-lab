import type { NodeId } from '../types';

const NODES: { id: NodeId; Lg: number }[] = [
  { id: '45nm', Lg: 40 },
  { id: '14nm', Lg: 20 },
  { id: '7nm', Lg: 16 },
  { id: '3nm', Lg: 12 },
  { id: '1nm', Lg: 8 },
  { id: 'sub-1nm', Lg: 5 },
];

export function NodeScalingSlider({
  value,
  onChange,
}: {
  value: NodeId;
  onChange: (n: NodeId) => void;
}) {
  const idx = NODES.findIndex((n) => n.id === value);
  return (
    <div className="w-full">
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-xs uppercase tracking-wider text-slate-400">
          Technology node
        </span>
        <span className="font-mono text-lg text-cyan-400">{value}</span>
      </div>
      <input
        type="range"
        min={0}
        max={NODES.length - 1}
        step={1}
        value={idx}
        onChange={(e) => onChange(NODES[Number(e.target.value)].id)}
        className="w-full accent-cyan-400 cursor-pointer"
      />
      <div className="mt-2 flex justify-between text-[10px] font-mono text-slate-500">
        {NODES.map((n) => (
          <button
            key={n.id}
            onClick={() => onChange(n.id)}
            className={`transition-colors hover:text-cyan-300 ${
              n.id === value ? 'text-cyan-400' : ''
            }`}
          >
            {n.id}
          </button>
        ))}
      </div>
    </div>
  );
}

export const NODE_LG: Record<NodeId, number> = Object.fromEntries(
  NODES.map((n) => [n.id, n.Lg]),
) as Record<NodeId, number>;
