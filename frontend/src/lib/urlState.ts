// Shareable deep-links: encode the current controls in the URL query string so
// any view (e.g. "3nm / graphene / tunneling") is a copy-pasteable link.
import type { SimState, NodeId, ModeChoice, Sweep, Material, Accuracy } from '../types';

const NODES: NodeId[] = ['45nm', '14nm', '7nm', '3nm', '1nm', 'sub-1nm'];
const MODES: ModeChoice[] = ['auto', 'classical', 'near_quantum', 'quantum'];
const SWEEPS: Sweep[] = ['idvg', 'idvd', 'leakage', 'tunneling'];
const MATERIALS: Material[] = ['Si', 'CNT', 'Graphene'];
const ACCS: Accuracy[] = ['low', 'medium', 'high'];

const pick = <T,>(v: string | null, allowed: T[], fallback: T): T =>
  (allowed as unknown as string[]).includes(v ?? '') ? (v as unknown as T) : fallback;

export interface UiState {
  node: NodeId;
  mode: ModeChoice;
  sweep: Sweep;
  material: Material;
  accuracy: Accuracy;
}

export function readUrlState(): UiState {
  const q = new URLSearchParams(window.location.search);
  return {
    node: pick(q.get('node'), NODES, '7nm'),
    mode: pick(q.get('mode'), MODES, 'auto'),
    sweep: pick(q.get('sweep'), SWEEPS, 'idvg'),
    material: pick(q.get('material'), MATERIALS, 'Si'),
    accuracy: pick(q.get('accuracy'), ACCS, 'medium'),
  };
}

export function writeUrlState(s: Pick<SimState, keyof UiState>): void {
  const q = new URLSearchParams({
    node: s.node,
    mode: s.mode,
    sweep: s.sweep,
    material: s.material,
    accuracy: s.accuracy,
  });
  const url = `${window.location.pathname}?${q.toString()}`;
  window.history.replaceState(null, '', url);
}
