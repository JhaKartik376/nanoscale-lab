"""services/physics_bridge.py

Single place that turns a (node, mode) into the scalar "device health" numbers
used by BOTH the metrics block (frontend) and the rule-based / chat explanation
layer. Keeping one source here guarantees the chart, the metric tiles and the
prose always agree.

Design choice (pedagogical coherence): the headline on/off, I_on and I_off use
the compact on-current + leakage models for ALL modes, so the on/off ratio
collapses *monotonically* 45nm -> sub-1nm. The ballistic model is still used for
the Id-Vg *curve shape* in quantum mode (see computation_engine), but not for
the single health number, which would otherwise be non-monotonic across modes.
"""
from node_params import build_params
from physics.quantum_correction import (
    subthreshold_swing, vth_short_channel, leakage_current, on_current,
)
from physics.tunneling_model import rect_barrier_T

M0 = 9.1093837015e-31
M_SI = 0.26 * M0


def device_metrics(p: dict, mode: str) -> dict:
    """Compute the full scalar metric set for a params dict `p`."""
    ss      = float(subthreshold_swing(p))
    dibl    = float(p["DIBL"])
    vth_eff = float(vth_short_channel(p, p["Vdd"]))

    # gate control proxy: 1.0 ideal, falls as DIBL grows (drain steals control)
    gate_control = max(0.0, min(1.0, 1.0 - p["DIBL"] / 300.0))

    # representative source-drain tunneling probability through the thin top of
    # the barrier (effective width ~ 0.15 * Lg). Material-aware: a lighter
    # effective mass (CNT/graphene) tunnels far more readily. Gapless materials
    # also drop the barrier height.
    m_eff = p.get("m_rel", 1.0) * M_SI
    phi = min(0.9, 0.5 * p.get("eg", 1.12) + 0.03)
    w_eff_m = max(0.15 * p["Lg"], 0.3) * 1e-9
    tunnel_prob = float(rect_barrier_T(0.1, phi, w_eff_m, m_eff))

    ion  = max(on_current(p), 1e-30)                       # A/um
    ioff = max(leakage_current(p)["i_total"], 1e-30)       # A/um
    on_off = ion / ioff
    leakage_frac = min(ioff / ion, 1.0)

    return {
        "ss": ss, "dibl": dibl, "vth_eff": vth_eff,
        "gate_control": gate_control, "tunnel_prob": tunnel_prob,
        "ion": ion, "ioff": ioff, "on_off": on_off,
        "leakage_frac": leakage_frac,
    }


def metrics_block(node: str, mode: str, material: str = "Si") -> dict:
    """Frontend-facing metrics: {vth_eff, ss, dibl, ion, ioff, on_off}."""
    p = build_params(node, material)
    m = device_metrics(p, mode)
    return {"vth_eff": m["vth_eff"], "ss": m["ss"], "dibl": m["dibl"],
            "ion": m["ion"], "ioff": m["ioff"], "on_off": m["on_off"]}


def run_sim(node: str, mode: str, material: str = "Si") -> dict:
    """AI-facing `results` dict consumed by the rule engine and chat tutor."""
    p = build_params(node, material)
    m = device_metrics(p, mode)
    return {
        "on_off_ratio": m["on_off"],
        "ss_mv_dec":    m["ss"],
        "leakage_frac": m["leakage_frac"],
        "tunnel_prob":  m["tunnel_prob"],
        "gate_control": m["gate_control"],
        "i_on_a_um":    m["ion"],
        "i_off_a_um":   m["ioff"],
    }
