// Mode vocabulary is UNIFIED with the backend enum (fix #2).
// The UI exposes an extra "auto" that sends no mode (backend picks the
// node's default); "Experimental" = free choice of any mode at any node.
export type Mode = 'classical' | 'near_quantum' | 'quantum';
export type ModeChoice = Mode | 'auto';
export type NodeId = '45nm' | '14nm' | '7nm' | '3nm' | '1nm' | 'sub-1nm';
export type Sweep = 'idvg' | 'idvd' | 'leakage' | 'tunneling';
export type Material = 'Si' | 'CNT' | 'Graphene';
export type Accuracy = 'low' | 'medium' | 'high';

export interface SimState {
  node: NodeId;
  mode: ModeChoice;
  sweep: Sweep;
  material: Material;
  accuracy: Accuracy;
  vd: number;
  vg: number;
}

// ---- server contract (schemas.SimulateResponse) ----
export interface Series {
  x: number[];
  y: number[];
  label: string;
  unit: string;
  xunit: string;
}
export interface Metrics {
  vth_eff: number;
  ss: number;
  dibl: number;
  ion: number;
  ioff: number;
  on_off: number;
}
export interface Meta {
  node: string;
  arch: string;
  mode: Mode;
  sweep: Sweep;
  material: string;
  accuracy: string;
  Lg_nm: number;
  cached: boolean;
  xticks: string[] | null;
}
export interface SimResult {
  series: Series[];
  metrics: Metrics;
  meta: Meta;
  insight: string;
}
