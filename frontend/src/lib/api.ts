import type { SimState, SimResult, Series } from '../types';
import { simulateLocal, localChat } from './localEngine';

// LOCAL mode: physics runs client-side (no backend). Enabled for the static
// GitHub Pages demo via VITE_LOCAL=1 at build time.
const LOCAL = import.meta.env.VITE_LOCAL === '1';

// Base URL for the FastAPI backend. Default hits localhost:8000 (CORS is
// allowed there); set VITE_API_URL="" to use the same-origin Vite proxy. (fix #7)
const API_BASE =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : 'http://localhost:8000';

export async function fetchSimulate(
  s: SimState,
  signal?: AbortSignal,
): Promise<SimResult> {
  if (LOCAL) return simulateLocal(s); // in-browser physics, no network
  const body = {
    node: s.node,
    mode: s.mode === 'auto' ? undefined : s.mode, // omit -> backend default (fix #2)
    sweep: s.sweep,
    material: s.material,
    accuracy: s.accuracy,
    bias: { vd: s.vd, vg: s.vg },
  };
  const r = await fetch(`${API_BASE}/simulate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok) {
    const detail = await r.json().catch(() => ({}));
    throw new Error(detail?.detail ?? `simulate failed: ${r.status}`);
  }
  return r.json();
}

export async function fetchChat(
  node: string,
  mode: string,
  material: string,
  question: string,
): Promise<{ source: string; answer: string }> {
  if (LOCAL) return localChat(node, material); // grounded rule-based, no LLM
  const r = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      node,
      mode: mode === 'auto' ? undefined : mode,
      material,
      question,
    }),
  });
  if (!r.ok) throw new Error(`chat failed: ${r.status}`);
  return r.json();
}

// ---- adapter: columnar {x[],y[]} series -> Recharts row data (fix #3) ----
export interface ChartLine {
  key: string;
  color: string;
}
export interface ChartData {
  rows: Record<string, number | string>[];
  lines: ChartLine[];
  xLabel: string;
  yLabel: string;
  logY: boolean;
  categorical: boolean;
}

function colorFor(label: string): string {
  const l = label.toLowerCase();
  if (l.includes('i_sub')) return '#fbbf24'; // amber
  if (l.includes('i_gate')) return '#ef4444'; // red
  if (l.includes('i_total')) return '#e2e8f0'; // slate-200
  if (l.startsWith('wkb') || l.includes('t(')) return '#34d399'; // emerald
  if (l.includes('ballistic')) return '#34d399';
  return '#22d3ee'; // cyan (Id)
}

function xLabelFor(sweep: string, xunit: string): string {
  if (xunit === 'nm') return 'barrier width (nm)';
  if (xunit === 'node') return 'technology node';
  if (sweep === 'idvd') return 'Vd (V)';
  return 'Vg (V)';
}

function yLabelFor(series: Series[]): string {
  const u = series[0]?.unit ?? '';
  if (u === 'prob') return 'T (transmission)';
  if (u === 'A/um') return 'I (A/µm)';
  return u;
}

export function adapt(res: SimResult): ChartData {
  const { series, meta } = res;
  const categorical = series[0]?.xunit === 'node';
  const n = series[0]?.x.length ?? 0;

  const rows: Record<string, number | string>[] = [];
  for (let i = 0; i < n; i++) {
    const row: Record<string, number | string> = {
      x: categorical ? meta.xticks?.[i] ?? String(i) : series[0].x[i],
    };
    for (const s of series) row[s.label] = s.y[i];
    rows.push(row);
  }

  return {
    rows,
    lines: series.map((s) => ({ key: s.label, color: colorFor(s.label) })),
    xLabel: xLabelFor(meta.sweep, series[0]?.xunit ?? 'V'),
    yLabel: yLabelFor(series),
    logY: meta.sweep !== 'idvd', // idvg / leakage / tunneling on log-y
    categorical,
  };
}
