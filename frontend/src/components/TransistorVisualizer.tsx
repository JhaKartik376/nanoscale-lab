import type { NodeId, ModeChoice } from '../types';

// Schematic cross-section. Only the gate length (Lg) is bound to real node data;
// it tweens via CSS transitions as the node changes. Electrons drift S->D; in
// non-classical modes a standing-wave overlay leaks through the barrier.
const gateW = (Lg: number) => 20 + (Lg / 40) * 120; // 40nm->140px, 5nm->35px

export function TransistorVisualizer({
  node,
  Lg,
  mode,
  loading,
}: {
  node: NodeId;
  Lg: number;
  mode: ModeChoice;
  loading: boolean;
}) {
  const gw = gateW(Lg);
  const gx = 160 - gw / 2;
  const quantum = mode === 'quantum' || mode === 'near_quantum';

  // build a schematic wavefunction poly-line: oscillate, decay in barrier, re-emerge
  const wavePts: string[] = [];
  for (let x = 80; x <= 240; x += 2) {
    const inBarrier = x >= gx && x <= gx + gw;
    const decay = inBarrier ? Math.exp(-(x - gx) / (gw * 0.6)) : 1;
    const amp = 9 * decay;
    wavePts.push(`${x},${98 - amp * Math.sin(x / 6)}`);
  }

  return (
    <div
      className={`rounded-xl bg-slate-900/70 border border-zinc-800 p-4 transition-opacity ${
        loading ? 'opacity-60' : ''
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-slate-200">
          Device cross-section
        </h3>
        <span className="font-mono text-xs text-slate-400">
          {node} · Lg {Lg} nm · {quantum ? 'wave' : 'drift'} view
        </span>
      </div>
      <svg viewBox="0 0 320 160" className="w-full h-44">
        <rect x="0" y="104" width="320" height="56" fill="#0b1220" />
        {/* source / drain */}
        <rect x="8" y="64" width="70" height="44" rx="3" fill="#1e293b" stroke="#334155" />
        <rect x="242" y="64" width="70" height="44" rx="3" fill="#1e293b" stroke="#334155" />
        <text x="43" y="90" textAnchor="middle" fill="#94a3b8" fontSize="10">S</text>
        <text x="277" y="90" textAnchor="middle" fill="#94a3b8" fontSize="10">D</text>
        {/* channel */}
        <rect x="78" y="94" width="164" height="12" fill="#0f2536" />
        {/* gate oxide + electrode (tween x/width) */}
        <rect
          x={gx}
          y="88"
          width={gw}
          height="6"
          fill="#34d399"
          opacity="0.5"
          style={{ transition: 'all 350ms ease-out' }}
        />
        <rect
          x={gx}
          y="40"
          width={gw}
          height="48"
          rx="3"
          fill="#0e7490"
          stroke="#22d3ee"
          strokeWidth="1.5"
          style={{ transition: 'all 350ms ease-out' }}
        />
        <text x="160" y="34" textAnchor="middle" fill="#67e8f9" fontSize="10">
          G · Lg {Lg}nm
        </text>
        {/* electrons drifting S->D */}
        {!quantum &&
          Array.from({ length: 6 }).map((_, i) => (
            <circle key={i} r="2.2" cx="80" cy="100" fill="#22d3ee"
              style={{
                // @ts-expect-error CSS custom property
                '--drift-dx': '160px',
                animation: `drift ${Math.max(0.6, 1.4 - (1 / Lg) * 6)}s linear ${
                  (i / 6) * 1.2
                }s infinite`,
              }}
            />
          ))}
        {/* quantum standing-wave leaking through the barrier */}
        {quantum && (
          <polyline
            points={wavePts.join(' ')}
            fill="none"
            stroke="#34d399"
            strokeWidth="1.5"
            style={{ animation: 'wavepulse 1.4s ease-in-out infinite' }}
          />
        )}
      </svg>
    </div>
  );
}
