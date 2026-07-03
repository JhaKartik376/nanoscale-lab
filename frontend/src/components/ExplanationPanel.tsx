import type { Metrics } from '../types';

const fmtExp = (v?: number) => (v == null ? '—' : v.toExponential(1));

export function ExplanationPanel({
  metrics,
  insight,
  loading,
}: {
  metrics?: Metrics;
  insight?: string;
  loading: boolean;
}) {
  const rows = [
    { k: 'SS', v: metrics && `${metrics.ss} mV/dec` },
    { k: 'DIBL', v: metrics && `${metrics.dibl} mV/V` },
    { k: 'Vth_eff', v: metrics && `${metrics.vth_eff.toFixed(3)} V` },
    { k: 'I_on', v: fmtExp(metrics?.ion) },
    { k: 'I_off', v: fmtExp(metrics?.ioff) },
  ];
  return (
    <aside className="w-full space-y-4">
      <div className="rounded-xl bg-slate-900/70 border border-zinc-800 p-4">
        <div className="text-xs uppercase tracking-wider text-slate-400">
          On/Off ratio
        </div>
        <div className="font-mono text-2xl text-cyan-400">
          {loading ? '···' : fmtExp(metrics?.on_off)}
        </div>
      </div>
      <dl className="rounded-xl bg-slate-900/70 border border-zinc-800 divide-y divide-zinc-800">
        {rows.map((r) => (
          <div key={r.k} className="flex justify-between px-4 py-2">
            <dt className="text-sm text-slate-400">{r.k}</dt>
            <dd className="font-mono text-sm text-slate-100">
              {loading ? '—' : r.v}
            </dd>
          </div>
        ))}
      </dl>
      <div className="rounded-xl bg-slate-900/70 border border-zinc-800 p-4 text-sm leading-relaxed text-slate-300">
        {loading ? 'analyzing node…' : insight}
      </div>
    </aside>
  );
}
