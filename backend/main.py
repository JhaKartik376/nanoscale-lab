"""NanoScale Lab -- FastAPI entrypoint (single app, single router).

Run:  uvicorn main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
import numpy as np
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from api.simulation_routes import router as sim_router
from node_params import list_nodes

app = FastAPI(
    title="NanoScale Lab API",
    version="0.1.0",
    description="Conceptual MOSFET scaling simulator (45nm -> sub-1nm).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000",
                   "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def _value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": f"value error: {exc}"})


@app.get("/health")
def health():
    return {"status": "ok", "nodes": list_nodes(), "numpy": np.__version__}


app.include_router(sim_router)
