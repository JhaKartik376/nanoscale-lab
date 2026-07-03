"""Pydantic request/response models. One canonical contract for the whole app.

Mode vocabulary is UNIFIED here: classical | near_quantum | quantum
(the frontend maps its UI labels Classical / Quantum / Experimental to these).
"""
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class Mode(str, Enum):
    classical    = "classical"
    near_quantum = "near_quantum"
    quantum      = "quantum"


class Sweep(str, Enum):
    idvg      = "idvg"        # Id vs Vg   @ fixed Vd
    idvd      = "idvd"        # Id vs Vd   @ fixed Vg
    leakage   = "leakage"     # I_sub / I_gate / I_total vs node
    tunneling = "tunneling"   # WKB T vs barrier width


class BiasParams(BaseModel):
    """All optional; sensible per-node defaults filled server-side."""
    vg:      Optional[float] = None
    vd:      Optional[float] = None
    vg_min:  Optional[float] = None
    vg_max:  Optional[float] = None
    vd_min:  Optional[float] = None
    vd_max:  Optional[float] = None
    points:  int = Field(120, ge=8, le=1000)
    # tunneling-only knobs (barrier width sweep, widths in nm)
    barrier_phi: Optional[float] = Field(None, description="barrier height (eV)")
    barrier_e:   Optional[float] = Field(None, description="carrier energy (eV)")
    width_min:   Optional[float] = Field(None, description="min barrier width (nm)")
    width_max:   Optional[float] = Field(None, description="max barrier width (nm)")


class Material(str, Enum):
    Si       = "Si"
    CNT      = "CNT"
    Graphene = "Graphene"


class Accuracy(str, Enum):
    low    = "low"
    medium = "medium"
    high   = "high"


class SimulateRequest(BaseModel):
    node:     str
    mode:     Optional[Mode] = Field(None, description="defaults to node's default mode")
    sweep:    Sweep = Sweep.idvg
    material: Material = Material.Si
    accuracy: Accuracy = Accuracy.medium
    bias:     BiasParams = BiasParams()


class Series(BaseModel):
    x:     List[float]
    y:     List[float]
    label: str
    unit:  str                 # y unit, e.g. "A/um", "prob"
    xunit: str = "V"           # x unit, e.g. "V", "nm", "node", "component"


class Metrics(BaseModel):
    vth_eff: float             # V
    ss:      float             # mV/dec
    dibl:    float             # mV/V
    ion:     float             # A/um
    ioff:    float             # A/um
    on_off:  float             # dimensionless


class Meta(BaseModel):
    node:     str
    arch:     str
    mode:     Mode
    sweep:    Sweep
    material: str = "Si"
    accuracy: str = "medium"
    Lg_nm:    float
    cached:   bool = False
    xticks:   Optional[List[str]] = None   # categorical x labels (leakage sweep)


class SimulateResponse(BaseModel):
    series:  List[Series]
    metrics: Metrics
    meta:    Meta
    insight: str               # one-sentence grounded takeaway


class Insight(BaseModel):
    metric:   str
    severity: int
    text:     str


class Verdict(BaseModel):
    severity: int
    label:    str


class ExplainResponse(BaseModel):
    node:     str
    mode:     Mode
    verdict:  Verdict
    headline: str
    insights: List[Insight]


class ChatRequest(BaseModel):
    node:     str
    mode:     Optional[Mode] = None
    material: Optional[Material] = Material.Si
    question: str


class ChatResponse(BaseModel):
    source: str                # "claude" | "rule-based-fallback"
    answer: str
