"""services/explanation_engine.py

Rule-based, physics-grounded explanation engine for NanoScale Lab.
Pure-Python, no network, no ML, deterministic.

Maps a `results` dict (from physics_bridge.run_sim) + node + mode into:
  - a list of per-metric plain-English insights (each citing the actual number)
  - an overall severity score and a verdict label

Severity scale (0 = ideal, 4 = broken):
  0 healthy   1 watch   2 marginal   3 degraded   4 quantum breakdown
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional

SEVERITY_LABELS = {
    0: "healthy scaling",
    1: "watch",
    2: "marginal",
    3: "degraded",
    4: "quantum breakdown",
}

V_T_MV = 25.9            # thermal voltage in mV
SS_IDEAL_MV_DEC = 60.0   # kT/q * ln(10) at 300 K -> Boltzmann floor


@dataclass
class Band:
    test: Callable[[float], bool]
    severity: int
    template: str


@dataclass
class Metric:
    key: str
    label: str
    bands: list
    weight: float = 1.0

    def evaluate(self, value: float, ctx: dict):
        for band in self.bands:
            if band.test(value):
                ctx = {**ctx, "value": value, "metric": self.label}
                return band.severity, band.template.format(**ctx)
        return 0, f"{self.label}: {value:.3g} (no rule matched)."


METRICS = [
    Metric(
        key="on_off_ratio", label="On/off ratio", weight=1.0,
        bands=[
            Band(lambda v: v >= 1e6, 0,
                 "On/off ratio is ~{value:,.0f}x: the transistor switches "
                 "cleanly, like a good digital switch."),
            Band(lambda v: v >= 1e4, 1,
                 "On/off ratio is ~{value:,.0f}x: still usable for logic, but "
                 "the off-state is no longer negligible at {node}."),
            Band(lambda v: v >= 1e2, 2,
                 "On/off ratio has collapsed to ~{value:,.0f}x at {node}: the "
                 "off current is only a couple of decades below on, so static "
                 "power starts to dominate."),
            Band(lambda v: v < 1e2, 4,
                 "On/off ratio is only ~{value:,.1f}x at {node}: on and off are "
                 "nearly indistinguishable -- the device barely behaves as a "
                 "switch anymore."),
        ],
    ),
    Metric(
        key="ss_mv_dec", label="Subthreshold swing", weight=1.3,
        bands=[
            Band(lambda v: v <= 65, 0,
                 "Subthreshold swing is {value:.0f} mV/dec, essentially at the "
                 "60 mV/dec Boltzmann limit -- the gate turns the channel off "
                 "efficiently."),
            Band(lambda v: v <= 85, 1,
                 "Subthreshold swing is {value:.0f} mV/dec vs the 60 mV/dec "
                 "ideal: it now takes ~{ss_decades:.1f}x more gate swing to cut "
                 "the current by 10x."),
            Band(lambda v: v <= 110, 2,
                 "Subthreshold swing has degraded to {value:.0f} mV/dec at "
                 "{node}: short-channel effects are eroding gate control."),
            Band(lambda v: v > 110, 3,
                 "Subthreshold swing is {value:.0f} mV/dec at {node} -- far "
                 "above the 60 mV/dec floor; sub-threshold leakage is baked in."),
        ],
    ),
    Metric(
        key="leakage_frac", label="Leakage fraction", weight=1.4,
        bands=[
            Band(lambda v: v < 0.01, 0,
                 "Off-state leakage is ~{leak_pct:.2f}% of the on-current: "
                 "negligible, the switch turns fully off."),
            Band(lambda v: v < 0.10, 1,
                 "Leakage is ~{leak_pct:.1f}% of on-current at {node}: small but "
                 "no longer free -- it sets a static-power floor."),
            Band(lambda v: v < 0.30, 2,
                 "Leakage is ~{leak_pct:.0f}% of on-current: a meaningful "
                 "fraction still flows when the device is supposed to be off."),
            Band(lambda v: v >= 0.30, 4,
                 "At {node}, electrons tunnel through the thinned barrier: "
                 "leakage is ~{leak_pct:.0f}% of on-current, so the switch "
                 "barely turns off."),
        ],
    ),
    Metric(
        key="tunnel_prob", label="Tunneling probability", weight=1.1,
        bands=[
            Band(lambda v: v < 1e-3, 0,
                 "Barrier tunneling probability is ~{value:.1e}: the classical "
                 "barrier still blocks carriers, quantum leakage is negligible."),
            Band(lambda v: v < 1e-2, 1,
                 "Tunneling probability is ~{value:.1e} at {node}: quantum "
                 "leakage is emerging but not yet dominant."),
            Band(lambda v: v < 0.1, 2,
                 "Tunneling probability is ~{value:.2f}: roughly 1 in "
                 "{tunnel_one_in:.0f} carriers now tunnels straight through the "
                 "barrier instead of being blocked."),
            Band(lambda v: v >= 0.1, 4,
                 "Tunneling probability is ~{value:.2f} at {node}: the barrier "
                 "is thin enough that carriers pass through it quantum-"
                 "mechanically -- direct source-to-drain tunneling."),
        ],
    ),
    Metric(
        key="gate_control", label="Gate control", weight=1.2,
        bands=[
            Band(lambda v: v >= 0.9, 0,
                 "Gate control metric is {value:.2f} (1.0 = ideal): the gate, "
                 "not the drain, sets the channel potential."),
            Band(lambda v: v >= 0.7, 1,
                 "Gate control is {value:.2f}: the drain is starting to steal "
                 "influence from the gate (DIBL) at {node}."),
            Band(lambda v: v >= 0.5, 2,
                 "Gate control has dropped to {value:.2f}: the drain bias now "
                 "significantly co-controls the barrier, shifting Vth with Vds."),
            Band(lambda v: v < 0.5, 3,
                 "Gate control is only {value:.2f} at {node}: the channel is "
                 "more drain-controlled than gate-controlled."),
        ],
    ),
]


def _build_context(results: dict, node: str, mode: str) -> dict:
    leak = float(results.get("leakage_frac", 0.0))
    ss = float(results.get("ss_mv_dec", SS_IDEAL_MV_DEC))
    tp = float(results.get("tunnel_prob", 0.0))
    return {
        "node": node, "mode": mode,
        "leak_pct": leak * 100.0,
        "ss_decades": ss / SS_IDEAL_MV_DEC,
        "tunnel_one_in": (1.0 / tp) if tp > 0 else float("inf"),
        "v_t_mv": V_T_MV,
    }


def explain(results: dict, node: str, mode: str) -> dict:
    """Map physics outputs to grounded plain-English insights + a verdict."""
    ctx = _build_context(results, node, mode)
    insights = []
    weighted_sum = 0.0
    weight_total = 0.0
    worst = (0, None)

    for metric in METRICS:
        if metric.key not in results:
            continue
        value = float(results[metric.key])
        sev, text = metric.evaluate(value, ctx)
        insights.append({"metric": metric.label, "severity": sev, "text": text})
        weighted_sum += sev * metric.weight
        weight_total += metric.weight
        if sev > worst[0]:
            worst = (sev, metric.label)

    avg = (weighted_sum / weight_total) if weight_total else 0.0
    overall = int(min(max(round(avg), worst[0]), 4))
    # insights: worst first (most useful at a glance)
    insights.sort(key=lambda i: -i["severity"])

    return {
        "node": node, "mode": mode,
        "verdict": {"severity": overall, "label": SEVERITY_LABELS[overall]},
        "headline": _headline(overall, node, worst[1], ctx),
        "insights": insights,
    }


def _headline(severity: int, node: str, worst_metric: Optional[str], ctx: dict) -> str:
    wm = (worst_metric or "a key metric").lower()
    if severity <= 0:
        return (f"At {node}, the transistor still behaves like a clean switch: "
                f"good gate control and negligible leakage.")
    if severity == 1:
        return (f"At {node}, scaling is holding up -- {wm} is the first metric "
                f"starting to slip.")
    if severity == 2:
        return (f"At {node}, the device is marginal: {wm} has degraded enough "
                f"to hurt static power.")
    if severity == 3:
        return (f"At {node}, electrostatic control is breaking down -- {wm} is "
                f"the dominant failure.")
    return (f"At {node}, the switch has entered quantum breakdown: {wm} shows "
            f"carriers bypassing the barrier outright.")
