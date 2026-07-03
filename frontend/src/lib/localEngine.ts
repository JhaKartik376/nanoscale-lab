// ---------------------------------------------------------------------------
// localEngine.ts — a faithful TypeScript port of the Python physics core, so
// the app can run FULLY CLIENT-SIDE (e.g. on GitHub Pages) with no backend.
// Mirrors backend/physics/* and backend/services/* exactly; numbers match the
// FastAPI backend. Used when VITE_LOCAL === '1' (see lib/api.ts).
// ---------------------------------------------------------------------------
import type { SimState, SimResult, Series } from '../types';

// ---- constants (SI) ----
const Q = 1.602176634e-19;
const KB = 1.380649e-23;
const T = 300.0;
const VT = (KB * T) / Q; // ~0.025852 V (classical / tunneling)
const V_T_LEAK = 0.0259; // literal used by the leakage model
const EPS0 = 8.8541878128e-12;
const EPS_OX = 3.9 * EPS0;
const HBAR = 1.054571817e-34;
const H = 6.62607015e-34;
const M0 = 9.1093837015e-31;
const M_SI = 0.26 * M0;
const LN10 = Math.log(10);
const MU0 = 0.04;

// model constants (illustrative)
const ALPHA_CS = 0.2, L0_CS = 5.0, I0_SUB = 1e-7;
const A_GATE = 1e4, B_GATE = 6.0, PHI_B = 3.1, I0_ON = 1e-4;
const A_GAP = 1e-3, EG_REF = 0.06;

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
const linspace = (a: number, b: number, n: number) =>
  Array.from({ length: n }, (_, i) => a + ((b - a) * i) / (n - 1));

// ---- node table + materials + accuracy (mirror node_params.py) ----
const NODES = ['45nm', '14nm', '7nm', '3nm', '1nm', 'sub-1nm'] as const;
const NODE_TABLE: Record<string, any> = {
  '45nm':    { arch: 'Planar bulk',   Lg: 40, Vdd: 1.0,  Vth0: 0.4,  EOT: 1.2, SS: 70,  DIBL: 50,  mu_rel: 1.0 },
  '14nm':    { arch: 'FinFET',        Lg: 20, Vdd: 0.8,  Vth0: 0.32, EOT: 0.9, SS: 75,  DIBL: 70,  mu_rel: 0.9 },
  '7nm':     { arch: 'FinFET',        Lg: 16, Vdd: 0.7,  Vth0: 0.28, EOT: 0.8, SS: 80,  DIBL: 95,  mu_rel: 0.82 },
  '3nm':     { arch: 'GAA nanosheet', Lg: 12, Vdd: 0.65, Vth0: 0.24, EOT: 0.7, SS: 85,  DIBL: 120, mu_rel: 0.75 },
  '1nm':     { arch: 'GAA / CFET',    Lg: 8,  Vdd: 0.6,  Vth0: 0.2,  EOT: 0.6, SS: 95,  DIBL: 160, mu_rel: 0.65 },
  'sub-1nm': { arch: '2D-FET / CNT',  Lg: 5,  Vdd: 0.5,  Vth0: 0.15, EOT: 0.5, SS: 115, DIBL: 220, mu_rel: 0.55 },
};
const MATERIALS: Record<string, any> = {
  Si:       { m_rel: 1.0,  mu_mat: 1.0,  eg: 1.12, dispersion: 'parabolic' },
  CNT:      { m_rel: 0.06, mu_mat: 4.0,  eg: 0.6,  dispersion: 'parabolic' },
  Graphene: { m_rel: 0.02, mu_mat: 10.0, eg: 0.02, dispersion: 'linear' },
};
const ACCURACY: Record<string, number> = { low: 60, medium: 120, high: 300 };
const DEFAULT_MODE: Record<string, string> = {
  '45nm': 'classical', '14nm': 'classical', '7nm': 'near_quantum',
  '3nm': 'near_quantum', '1nm': 'quantum', 'sub-1nm': 'quantum',
};

function buildParams(node: string, material: string) {
  const r = NODE_TABLE[node], m = MATERIALS[material];
  return {
    node, arch: r.arch, Lg: r.Lg, Vdd: r.Vdd, Vth0: r.Vth0, EOT: r.EOT,
    SS: r.SS, DIBL: r.DIBL, mu_rel: r.mu_rel * m.mu_mat, W: 1.0,
    material, m_rel: m.m_rel, eg: m.eg, dispersion: m.dispersion,
  };
}

// ---- classical compact MOSFET (classical_model.py) ----
function modelParams(p: any) {
  const L = p.Lg * 1e-9, W = 1e-6, eot = p.EOT * 1e-9;
  const cox = EPS_OX / eot, mu = MU0 * p.mu_rel;
  const n_id = (p.SS * 1e-3) / (LN10 * VT);
  const lam = 0.05 * (20.0 / p.Lg), dibl = p.DIBL * 1e-3;
  const I0 = mu * cox * (n_id - 1.0) * VT * VT;
  return { L, W, cox, mu, n_id, lam, dibl, I0, Vth0: p.Vth0 };
}
function idCore(mp: any, vgs: number, vds: number) {
  const vth = mp.Vth0 - mp.dibl * vds;
  const vov = vgs - vth, wl = mp.W / mp.L, k = mp.mu * mp.cox * wl;
  const vdse = Math.min(vds, Math.max(vov, 0));
  const id_si = vov > 0 ? k * (vov * vdse - 0.5 * vdse * vdse) * (1 + mp.lam * vds) : 0;
  const expArg = clamp(Math.min(vov, 0) / (mp.n_id * VT), -60, 0);
  const id_sub = mp.I0 * wl * Math.exp(expArg) * (1 - Math.exp(-vds / VT));
  return id_si + id_sub; // W=1um -> already per micron
}

// ---- near-quantum (quantum_correction.py) ----
const vthShortChannel = (p: any, vds: number) =>
  p.Vth0 - (p.DIBL / 1000) * vds - ALPHA_CS * Math.exp(-p.Lg / L0_CS);
const bodyFactor = (p: any) => p.SS / 60;
function leakageCurrent(p: any) {
  const W = p.W, LgUm = p.Lg * 1e-3, aspect = W / LgUm;
  const n = bodyFactor(p), vthEff = vthShortChannel(p, p.Vdd);
  const iSub = I0_SUB * aspect * Math.exp(-vthEff / (n * V_T_LEAK));
  const field = p.Vdd / p.EOT;
  const jGate = A_GATE * field * field * Math.exp(-B_GATE * p.EOT * Math.sqrt(PHI_B));
  const areaCm2 = W * 1e-4 * (p.Lg * 1e-7);
  const iGate = jGate * areaCm2;
  const iGap = A_GAP * W * Math.exp(-p.eg / EG_REF);
  return { i_sub: iSub, i_gate: iGate, i_total: iSub + iGate + iGap };
}
function onCurrent(p: any) {
  const aspect = p.W / (p.Lg * 1e-3);
  const vov = Math.max(p.Vdd - vthShortChannel(p, p.Vdd), 0);
  return I0_ON * p.mu_rel * aspect * vov * vov;
}

// ---- quantum (tunneling_model.py) ----
function rectBarrierT(E: number, phi: number, width: number, mEff: number) {
  const barrier = (phi - E) * Q;
  if (barrier <= 0) return 1.0;
  const kappa = Math.sqrt(2 * mEff * barrier) / HBAR;
  return Math.exp(-2 * kappa * width);
}
const fermi = (Eev: number, muEv: number) =>
  1 / (1 + Math.exp(clamp((Eev - muEv) / VT, -500, 500)));
function ballisticCurrent(p: any, vg: number, vd: number, nE = 1500) {
  const mEff = p.m_rel * M_SI, vth = p.Vth0, dibl = p.DIBL * 1e-3;
  const Lg = p.Lg * 1e-9, W = 1e-6, eg = p.eg;
  const linear = p.dispersion === 'linear';
  const phi0 = Math.min(0.45, 0.5 * eg + 0.03);
  const Ec = 0, muS = 0.05, muD = muS - vd;
  const Etop = Ec + Math.max(phi0 - (vg - vth) - dibl * vd, -0.15);
  const Emin = Ec - 5 * VT, Emax = Math.max(muS, Etop) + 0.6;
  const E = linspace(Emin, Emax, nE);
  const xJ = E.map((e) => e * Q);
  const y = E.map((e) => {
    const de = Math.max((e - Ec) * Q, 0);
    const M = linear
      ? (W * Math.max(e - Ec, 0) * Q) / (Math.PI * HBAR * 1e6)
      : (W * Math.sqrt(2 * mEff * de)) / (Math.PI * HBAR);
    const barrier = (Etop - e) * Q;
    const kappa = Math.sqrt(2 * mEff * Math.max(barrier, 0)) / HBAR;
    const Tr = barrier > 0 ? Math.exp(-2 * kappa * Lg) : 1;
    return M * Tr * (fermi(e, muS) - fermi(e, muD));
  });
  let integ = 0;
  for (let i = 1; i < E.length; i++) integ += 0.5 * (y[i] + y[i - 1]) * (xJ[i] - xJ[i - 1]);
  return (2 * Q / H) * integ;
}

// ---- metrics + rule-based explanation (physics_bridge + explanation_engine) ----
function deviceMetrics(p: any) {
  const ss = p.SS, dibl = p.DIBL, vthEff = vthShortChannel(p, p.Vdd);
  const gateControl = clamp(1 - p.DIBL / 300, 0, 1);
  const mEff = p.m_rel * M_SI, phi = Math.min(0.9, 0.5 * p.eg + 0.03);
  const wEff = Math.max(0.15 * p.Lg, 0.3) * 1e-9;
  const tunnelProb = rectBarrierT(0.1, phi, wEff, mEff);
  const ion = Math.max(onCurrent(p), 1e-30);
  const ioff = Math.max(leakageCurrent(p).i_total, 1e-30);
  return {
    ss, dibl, vth_eff: vthEff, gate_control: gateControl, tunnel_prob: tunnelProb,
    ion, ioff, on_off: ion / ioff, leakage_frac: Math.min(ioff / ion, 1),
  };
}

const SEVERITY = ['healthy scaling', 'watch', 'marginal', 'degraded', 'quantum breakdown'];
function explain(node: string, m: any) {
  const leakPct = m.leakage_frac * 100;
  let worstSev = 0, worstLabel = 'a key metric';
  const insights: { metric: string; severity: number; text: string }[] = [];
  const add = (metric: string, sev: number, text: string) => {
    insights.push({ metric, severity: sev, text });
    if (sev > worstSev) { worstSev = sev; worstLabel = metric.toLowerCase(); }
  };
  // on/off
  const oo = m.on_off;
  if (oo >= 1e6) add('On/off ratio', 0, `On/off ratio is ~${oo.toExponential(1)}x: switches cleanly.`);
  else if (oo >= 1e4) add('On/off ratio', 1, `On/off ratio is ~${oo.toExponential(1)}x: usable, but the off-state is no longer negligible at ${node}.`);
  else if (oo >= 1e2) add('On/off ratio', 2, `On/off ratio has collapsed to ~${oo.toFixed(0)}x at ${node}: static power starts to dominate.`);
  else add('On/off ratio', 4, `On/off ratio is only ~${oo.toFixed(1)}x at ${node}: on and off are nearly indistinguishable — barely a switch.`);
  // SS
  if (m.ss <= 65) add('Subthreshold swing', 0, `SS is ${m.ss.toFixed(0)} mV/dec, near the 60 mV/dec Boltzmann limit.`);
  else if (m.ss <= 85) add('Subthreshold swing', 1, `SS is ${m.ss.toFixed(0)} mV/dec vs the 60 mV/dec ideal.`);
  else if (m.ss <= 110) add('Subthreshold swing', 2, `SS has degraded to ${m.ss.toFixed(0)} mV/dec at ${node}.`);
  else add('Subthreshold swing', 3, `SS is ${m.ss.toFixed(0)} mV/dec at ${node} — far above the floor.`);
  // leakage frac
  if (m.leakage_frac < 0.01) add('Leakage fraction', 0, `Off-state leakage is ~${leakPct.toFixed(2)}% of on-current: negligible.`);
  else if (m.leakage_frac < 0.1) add('Leakage fraction', 1, `Leakage is ~${leakPct.toFixed(1)}% of on-current at ${node}.`);
  else if (m.leakage_frac < 0.3) add('Leakage fraction', 2, `Leakage is ~${leakPct.toFixed(0)}% of on-current.`);
  else add('Leakage fraction', 4, `At ${node}, leakage is ~${leakPct.toFixed(0)}% of on-current: barely turns off.`);
  // tunnel prob
  const tp = m.tunnel_prob;
  if (tp < 1e-3) add('Tunneling probability', 0, `Barrier tunneling is ~${tp.toExponential(1)}: classical barrier still blocks carriers.`);
  else if (tp < 1e-2) add('Tunneling probability', 1, `Tunneling probability is ~${tp.toExponential(1)} at ${node}: emerging.`);
  else if (tp < 0.1) add('Tunneling probability', 2, `Tunneling probability is ~${tp.toFixed(2)}: ~1 in ${(1 / tp).toFixed(0)} carriers tunnels through.`);
  else add('Tunneling probability', 4, `Tunneling probability is ~${tp.toFixed(2)} at ${node}: direct source-to-drain tunneling.`);
  // gate control
  const gc = m.gate_control;
  if (gc >= 0.9) add('Gate control', 0, `Gate control is ${gc.toFixed(2)} (1.0 = ideal).`);
  else if (gc >= 0.7) add('Gate control', 1, `Gate control is ${gc.toFixed(2)}: the drain is starting to steal influence (DIBL).`);
  else if (gc >= 0.5) add('Gate control', 2, `Gate control has dropped to ${gc.toFixed(2)}: the drain co-controls the barrier.`);
  else add('Gate control', 3, `Gate control is only ${gc.toFixed(2)} at ${node}: more drain- than gate-controlled.`);

  const weights: Record<string, number> = { 'On/off ratio': 1.0, 'Subthreshold swing': 1.3, 'Leakage fraction': 1.4, 'Tunneling probability': 1.1, 'Gate control': 1.2 };
  let ws = 0, wt = 0;
  for (const i of insights) { ws += i.severity * weights[i.metric]; wt += weights[i.metric]; }
  const overall = Math.min(Math.max(Math.round(ws / wt), worstSev), 4);
  insights.sort((a, b) => b.severity - a.severity);
  const headline = overall <= 0
    ? `At ${node}, the transistor still behaves like a clean switch: good gate control and negligible leakage.`
    : overall === 1 ? `At ${node}, scaling is holding up — ${worstLabel} is the first metric starting to slip.`
    : overall === 2 ? `At ${node}, the device is marginal: ${worstLabel} has degraded enough to hurt static power.`
    : overall === 3 ? `At ${node}, electrostatic control is breaking down — ${worstLabel} is the dominant failure.`
    : `At ${node}, the switch has entered quantum breakdown: ${worstLabel} shows carriers bypassing the barrier outright.`;
  return { verdict: { severity: overall, label: SEVERITY[overall] }, headline, insights };
}

// ---- sweep dispatch -> SimResult (same shape as the FastAPI backend) ----
const series = (x: number[], y: number[], label: string, unit: string, xunit = 'V'): Series =>
  ({ x, y, label, unit, xunit });

export function simulateLocal(s: SimState): SimResult {
  const material = s.material;
  const mode = s.mode === 'auto' ? DEFAULT_MODE[s.node] : s.mode;
  const p = buildParams(s.node, material);
  const pts = ACCURACY[s.accuracy] ?? 120;
  const m = deviceMetrics(p);

  let ser: Series[] = [];
  let xticks: string[] | null = null;

  if (s.sweep === 'idvg') {
    const vd = s.vd ?? p.Vdd;
    const vg = linspace(0, p.Vdd, pts);
    if (mode === 'classical') {
      const mp = modelParams(p);
      ser = [series(vg, vg.map((g) => idCore(mp, g, vd)), `Id-Vg classical @Vd=${vd}V`, 'A/um')];
    } else if (mode === 'near_quantum') {
      const mp = modelParams({ ...p, Vth0: vthShortChannel(p, vd) });
      ser = [series(vg, vg.map((g) => idCore(mp, g, vd)), `Id-Vg near-quantum (Vth_eff) @Vd=${vd}V`, 'A/um')];
    } else {
      ser = [series(vg, vg.map((g) => ballisticCurrent(p, g, vd)), `Id-Vg ballistic @Vd=${vd}V`, 'A/um')];
    }
  } else if (s.sweep === 'idvd') {
    const vg = s.vg ?? p.Vdd;
    const vd = linspace(0, p.Vdd, pts);
    if (mode === 'quantum') {
      ser = [series(vd, vd.map((d) => ballisticCurrent(p, vg, d)), `Id-Vd ballistic @Vg=${vg}V`, 'A/um')];
    } else {
      const mp = modelParams(p);
      ser = [series(vd, vd.map((d) => idCore(mp, vg, d)), `Id-Vd @Vg=${vg}V`, 'A/um')];
    }
  } else if (s.sweep === 'leakage') {
    const xi = NODES.map((_, i) => i);
    const iSub: number[] = [], iGate: number[] = [], iTot: number[] = [];
    for (const n of NODES) {
      const lk = leakageCurrent(buildParams(n, material));
      iSub.push(lk.i_sub); iGate.push(lk.i_gate); iTot.push(lk.i_total);
    }
    ser = [
      series(xi, iSub, 'I_sub', 'A/um', 'node'),
      series(xi, iGate, 'I_gate', 'A/um', 'node'),
      series(xi, iTot, 'I_total', 'A/um', 'node'),
    ];
    xticks = [...NODES];
  } else {
    // tunneling vs barrier width
    const mEff = p.m_rel * M_SI;
    const widths = linspace(3.0, 0.3, pts);
    ser = [series(widths, widths.map((w) => rectBarrierT(0.1, 0.9, w * 1e-9, mEff)),
      `WKB T(width) ${material} phi=0.9eV`, 'prob', 'nm')];
  }

  const results = {
    on_off_ratio: m.on_off, ss_mv_dec: m.ss, leakage_frac: m.leakage_frac,
    tunnel_prob: m.tunnel_prob, gate_control: m.gate_control,
    i_on_a_um: m.ion, i_off_a_um: m.ioff,
  };
  const ex = explain(s.node, m);

  return {
    series: ser,
    metrics: { vth_eff: m.vth_eff, ss: m.ss, dibl: m.dibl, ion: m.ion, ioff: m.ioff, on_off: m.on_off },
    meta: {
      node: s.node, arch: p.arch, mode: mode as any, sweep: s.sweep,
      material, accuracy: s.accuracy, Lg_nm: p.Lg, cached: false, xticks,
    },
    insight: ex.headline,
  };
}

// grounded rule-based "chat" answer for the static (no-LLM) build
export function localChat(node: string, material: string): { source: string; answer: string } {
  const m = deviceMetrics(buildParams(node, material));
  const ex = explain(node, m);
  return {
    source: 'rule-based-fallback',
    answer: ex.headline + ' ' + ex.insights.slice(0, 2).map((i) => i.text).join(' '),
  };
}
