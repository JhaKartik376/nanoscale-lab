"""api/simulation_routes.py

The single router mounted by main.py. Endpoints:
    POST /simulate     run a sweep -> series + metrics + insight
    GET  /graph-data   replay the last snapshot for (node, mode, sweep)
    GET  /explain      grounded rule-based explanation (verdict + insights)
    POST /chat         Claude tutor (falls back to the rule engine)
    GET  /nodes        list nodes + default modes
"""
from fastapi import APIRouter, HTTPException, Query

from schemas import (
    SimulateRequest, SimulateResponse, Series, Metrics, Meta,
    Mode, Sweep, Material, Accuracy, ExplainResponse, ChatRequest,
    ChatResponse, BiasParams,
)
from node_params import build_params, list_nodes, list_materials, DEFAULT_MODE
from services.computation_engine import run_sweep, last_series, resolve_mode
from services.physics_bridge import metrics_block, run_sim
from services.explanation_engine import explain
from services.chat import chat as chat_answer

router = APIRouter(tags=["simulation"])


def _require_node(node: str):
    if node not in list_nodes():
        raise HTTPException(404, f"unknown node '{node}'. valid: {list_nodes()}")


@router.get("/nodes")
def nodes():
    return {"nodes": list_nodes(), "materials": list_materials(),
            "default_mode": DEFAULT_MODE}


@router.post("/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest) -> SimulateResponse:
    _require_node(req.node)
    try:
        material = req.material.value
        p = build_params(req.node, material)
        mode = resolve_mode(req.node, req.mode)
        series, xticks, metrics, insight, cached = run_sweep(
            req.node, mode, req.sweep, req.bias, material, req.accuracy.value)
    except (KeyError, ValueError) as e:
        raise HTTPException(422, f"bad request: {e}")
    except Exception as e:
        raise HTTPException(500, f"computation failed: {e}")

    return SimulateResponse(
        series=[Series(**s) for s in series],
        metrics=Metrics(**metrics),
        meta=Meta(node=req.node, arch=p["arch"], mode=mode, sweep=req.sweep,
                  material=material, accuracy=req.accuracy.value,
                  Lg_nm=float(p["Lg"]), cached=cached, xticks=xticks),
        insight=insight,
    )


@router.get("/graph-data", response_model=SimulateResponse)
def graph_data(
    node: str = Query(...),
    mode: Mode = Query(None),
    sweep: Sweep = Query(Sweep.idvg),
    material: Material = Query(Material.Si),
) -> SimulateResponse:
    """Chart-ready snapshot. Falls back to computing defaults if nothing cached."""
    _require_node(node)
    m = resolve_mode(node, mode)
    mat = material.value
    p = build_params(node, mat)
    snap = last_series(node, m, sweep, mat)
    if snap is None:
        series, xticks, metrics, insight, _ = run_sweep(node, m, sweep, BiasParams(), mat)
    else:
        series, xticks = snap["series"], snap["xticks"]
        metrics = metrics_block(node, m.value, mat)
        insight = explain(run_sim(node, m.value, mat), node, m.value)["headline"]
    return SimulateResponse(
        series=[Series(**s) for s in series],
        metrics=Metrics(**metrics),
        meta=Meta(node=node, arch=p["arch"], mode=m, sweep=sweep, material=mat,
                  Lg_nm=float(p["Lg"]), cached=True, xticks=xticks),
        insight=insight,
    )


@router.get("/explain", response_model=ExplainResponse)
def explain_route(
    node: str = Query(...),
    mode: Mode = Query(None),
    material: Material = Query(Material.Si),
) -> ExplainResponse:
    _require_node(node)
    m = resolve_mode(node, mode)
    result = explain(run_sim(node, m.value, material.value), node, m.value)
    return ExplainResponse(
        node=node, mode=m,
        verdict=result["verdict"], headline=result["headline"],
        insights=result["insights"],
    )


@router.post("/chat", response_model=ChatResponse)
def chat_route(req: ChatRequest) -> ChatResponse:
    _require_node(req.node)
    m = resolve_mode(req.node, req.mode)
    mat = req.material.value if req.material else "Si"
    out = chat_answer(run_sim(req.node, m.value, mat), req.node, m.value, req.question)
    return ChatResponse(**out)
