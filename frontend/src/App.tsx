import { useMemo, useState } from 'react';
import type {
  NodeId,
  ModeChoice,
  Sweep,
  Material,
  Accuracy,
  SimState,
} from './types';
import { useSimulation } from './hooks/useSimulation';
import { NodeScalingSlider, NODE_LG } from './components/NodeScalingSlider';
import { ModeToggle } from './components/ModeToggle';
import { SweepSelector } from './components/SweepSelector';
import { MaterialPicker } from './components/MaterialPicker';
import { AccuracyToggle } from './components/AccuracyToggle';
import { GraphPanel } from './components/GraphPanel';
import { TransistorVisualizer } from './components/TransistorVisualizer';
import { ExplanationPanel } from './components/ExplanationPanel';
import { TutorChat } from './components/TutorChat';

const SWEEP_TITLE: Record<Sweep, string> = {
  idvg: 'Id–Vg (transfer)',
  idvd: 'Id–Vd (output)',
  leakage: 'Leakage vs Node',
  tunneling: 'Tunneling T vs Barrier Width',
};

export default function App() {
  const [node, setNode] = useState<NodeId>('7nm');
  const [mode, setMode] = useState<ModeChoice>('auto');
  const [sweep, setSweep] = useState<Sweep>('idvg');
  const [material, setMaterial] = useState<Material>('Si');
  const [accuracy, setAccuracy] = useState<Accuracy>('medium');

  const sim: SimState = useMemo(
    () => ({ node, mode, sweep, material, accuracy, vd: 0.7, vg: 0.7 }),
    [node, mode, sweep, material, accuracy],
  );
  const { data, loading, error } = useSimulation(sim);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <header className="flex items-center gap-4 px-6 py-3 border-b border-zinc-800 text-sm">
        <span className="font-semibold tracking-wide">NanoScale&nbsp;Lab</span>
        <span className="font-mono text-slate-400">
          {node} · {data?.meta.mode ?? mode} · {material}
          {data ? ` · ${data.meta.arch}` : ''}
        </span>
        <span
          className={`ml-auto flex items-center gap-2 ${
            loading ? 'text-amber-400' : 'text-emerald-400'
          }`}
        >
          <span className="h-2 w-2 rounded-full bg-current animate-pulse" />
          {loading ? 'simulating…' : 'live'}
        </span>
      </header>

      <div className="flex flex-1 min-h-0">
        <nav className="w-64 shrink-0 border-r border-zinc-800 p-4 space-y-6 overflow-auto">
          <NodeScalingSlider value={node} onChange={setNode} />
          <ModeToggle value={mode} onChange={setMode} />
          <MaterialPicker value={material} onChange={setMaterial} />
          <AccuracyToggle value={accuracy} onChange={setAccuracy} />
          <SweepSelector value={sweep} onChange={setSweep} />
        </nav>

        <main className="flex-1 min-w-0 p-4 space-y-4 overflow-auto">
          {error && (
            <div className="text-red-400 text-sm border border-red-900/50 rounded-lg p-3">
              error: {error} — is the backend running on :8000?
            </div>
          )}
          {/* one panel bound to the ACTIVE sweep (fix #6) */}
          {data && <GraphPanel title={SWEEP_TITLE[sweep]} data={data} />}
          <TransistorVisualizer
            node={node}
            Lg={NODE_LG[node]}
            mode={mode}
            loading={loading}
          />
        </main>

        <aside className="w-80 shrink-0 border-l border-zinc-800 p-4 space-y-4 overflow-auto">
          <ExplanationPanel
            metrics={data?.metrics}
            insight={data?.insight}
            loading={loading}
          />
          <TutorChat node={node} mode={data?.meta.mode ?? 'auto'} material={material} />
        </aside>
      </div>
    </div>
  );
}
