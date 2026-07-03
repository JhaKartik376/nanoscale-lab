"""services/computation_engine.py

Mode dispatch + memoized sweeps + uniform {x, y, label, unit, xunit} series.
The API layer never touches physics directly -- it calls run_sweep() here.

Fixes applied vs. the first draft:
  * cache/snapshot keyed by (node | mode | sweep)  -- not just node|mode
  * tunneling sweep is over BARRIER WIDTH (nm), matching the frontend panel
  * one response contract: series + metrics + insight (see schemas.SimulateResponse)
"""
import json
import numpy as np
from functools import lru_cache

from node_params import build_params, DEFAULT_MODE, list_nodes, ACCURACY
from schemas import Mode, Sweep, BiasParams
from physics.classical_model import idvg_classical, idvd_classical
from physics.quantum_correction import vth_short_channel, leakage_current
from physics.tunneling_model import rect_barrier_T, ballistic_current
from services.physics_bridge import metrics_block, run_sim
from services.explanation_engine import explain


# --------------------------------------------------------------------------
# Uniform series helper
# --------------------------------------------------------------------------
def _series(x, y, label, unit, xunit="V") -> dict:
    return {
        "x": np.asarray(x, dtype=float).tolist(),
        "y": np.asarray(y, dtype=float).tolist(),
        "label": label, "unit": unit, "xunit": xunit,
    }


# --------------------------------------------------------------------------
# Snapshot (for /graph-data) -- keyed by node|mode|SWEEP  (fix #1)
# --------------------------------------------------------------------------
_LAST_SERIES = {}   # "node|mode|sweep" -> {"series":[...], "xticks":[...]|None}


def _snap_key(node: str, mode: Mode, sweep: Sweep, material: str) -> str:
    return f"{node}|{mode.value}|{sweep.value}|{material}"


def resolve_mode(node: str, mode) -> Mode:
    if mode is not None:
        return mode if isinstance(mode, Mode) else Mode(mode)
    return Mode(DEFAULT_MODE[node])


def _bias_key(bias: BiasParams) -> str:
    return json.dumps(bias.model_dump(), sort_keys=True)


@lru_cache(maxsize=256)
def _compute_cached(node: str, mode: str, sweep: str, material: str,
                    pts: int, bias_json: str) -> str:
    """Heavy path, memoized. Returns JSON {series, xticks}."""
    bias = BiasParams(**json.loads(bias_json))
    p = build_params(node, material)
    series, xticks = _dispatch(p, Mode(mode), Sweep(sweep), bias, pts, material)
    return json.dumps({"series": series, "xticks": xticks})


def run_sweep(node: str, mode, sweep: Sweep, bias: BiasParams,
              material: str = "Si", accuracy: str = "medium"):
    """Public entry. Returns (series_list, xticks, metrics, insight, cached)."""
    m = resolve_mode(node, mode)
    pts = ACCURACY.get(accuracy, ACCURACY["medium"])["points"]
    key = _bias_key(bias)
    before = _compute_cached.cache_info().hits
    payload = json.loads(_compute_cached(node, m.value, sweep.value, material, pts, key))
    cached = _compute_cached.cache_info().hits > before

    _LAST_SERIES[_snap_key(node, m, sweep, material)] = payload   # snapshot

    metrics = metrics_block(node, m.value, material)
    insight = explain(run_sim(node, m.value, material), node, m.value)["headline"]
    return payload["series"], payload["xticks"], metrics, insight, cached


def last_series(node: str, mode: Mode, sweep: Sweep, material: str = "Si"):
    return _LAST_SERIES.get(_snap_key(node, mode, sweep, material))


# --------------------------------------------------------------------------
# Mode routing
# --------------------------------------------------------------------------
def _dispatch(p: dict, mode: Mode, sweep: Sweep, bias: BiasParams,
              pts: int, material: str):
    """Returns (series_list, xticks_or_None)."""
    if sweep is Sweep.idvg:
        return _idvg(p, mode, bias, pts), None
    if sweep is Sweep.idvd:
        return _idvd(p, mode, bias, pts), None
    if sweep is Sweep.leakage:
        return _leakage(p, mode, bias, material)   # returns (series, xticks)
    if sweep is Sweep.tunneling:
        return _tunneling(p, mode, bias, pts), None
    raise ValueError(f"unhandled sweep {sweep}")


def _idvg(p, mode, bias, pts):
    vd = bias.vd if bias.vd is not None else p["Vdd"]
    vg = np.linspace(bias.vg_min if bias.vg_min is not None else 0.0,
                     bias.vg_max if bias.vg_max is not None else p["Vdd"],
                     pts)
    if mode is Mode.classical:
        r = idvg_classical(p, vg, vd)
        return [_series(r["vg"], r["id"], f"Id-Vg classical @Vd={vd:g}V", "A/um")]
    if mode is Mode.near_quantum:
        p_eff = dict(p, Vth0=vth_short_channel(p, vd))    # DIBL/SCE-shifted Vth
        r = idvg_classical(p_eff, vg, vd)
        return [_series(r["vg"], r["id"],
                        f"Id-Vg near-quantum (Vth_eff) @Vd={vd:g}V", "A/um")]
    idq = [ballistic_current(p, float(g), vd) for g in vg]
    return [_series(vg, idq, f"Id-Vg ballistic @Vd={vd:g}V", "A/um")]


def _idvd(p, mode, bias, pts):
    vg = bias.vg if bias.vg is not None else p["Vdd"]
    vd = np.linspace(bias.vd_min if bias.vd_min is not None else 0.0,
                     bias.vd_max if bias.vd_max is not None else p["Vdd"],
                     pts)
    if mode is Mode.quantum:
        idq = [ballistic_current(p, vg, float(d)) for d in vd]
        return [_series(vd, idq, f"Id-Vd ballistic @Vg={vg:g}V", "A/um", xunit="V")]
    r = idvd_classical(p, vd, vg)
    return [_series(r["vd"], r["id"], f"Id-Vd @Vg={vg:g}V", "A/um", xunit="V")]


def _leakage(p, mode, bias, material):
    """Leakage components across ALL nodes -> a 'leakage vs node' comparison."""
    nodes = list_nodes()
    xi = list(range(len(nodes)))
    i_sub, i_gate, i_total = [], [], []
    for n in nodes:
        lk = leakage_current(build_params(n, material))
        i_sub.append(lk["i_sub"]); i_gate.append(lk["i_gate"]); i_total.append(lk["i_total"])
    series = [
        _series(xi, i_sub,   "I_sub",   "A/um", xunit="node"),
        _series(xi, i_gate,  "I_gate",  "A/um", xunit="node"),
        _series(xi, i_total, "I_total", "A/um", xunit="node"),
    ]
    return series, nodes                          # xticks = node labels


def _tunneling(p, mode, bias, pts):
    """WKB transmission T vs BARRIER WIDTH (nm)  (fix #4). Material-aware m*."""
    m_eff = p.get("m_rel", 1.0) * 0.26 * 9.1093837015e-31
    phi = bias.barrier_phi if bias.barrier_phi is not None else 0.9   # eV (S-D)
    E   = bias.barrier_e   if bias.barrier_e   is not None else 0.1   # eV
    wmin = bias.width_min if bias.width_min is not None else 0.3      # nm
    wmax = bias.width_max if bias.width_max is not None else 3.0      # nm
    widths_nm = np.linspace(wmax, wmin, pts)                          # thick -> thin
    T = [rect_barrier_T(E, phi, float(w) * 1e-9, m_eff) for w in widths_nm]
    return [_series(widths_nm, T,
                    f"WKB T(width) {p.get('material','Si')} phi={phi:g}eV", "prob", xunit="nm")]
