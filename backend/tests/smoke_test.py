"""End-to-end smoke test: drives every endpoint via FastAPI TestClient.
Run from backend/:  python tests/smoke_test.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app

c = TestClient(app)
ok = 0


def check(cond, msg):
    global ok
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    if cond:
        ok += 1
    else:
        raise SystemExit(f"SMOKE TEST FAILED: {msg}")


print("== /health ==")
r = c.get("/health").json()
check(r["status"] == "ok" and "45nm" in r["nodes"], "health lists nodes")

print("\n== /simulate Id-Vg across modes ==")
for node, mode in [("45nm", "classical"), ("7nm", "near_quantum"), ("1nm", "quantum")]:
    r = c.post("/simulate", json={"node": node, "mode": mode, "sweep": "idvg"})
    check(r.status_code == 200, f"{node}/{mode} idvg -> 200")
    j = r.json()
    s = j["series"][0]
    check(len(s["x"]) == len(s["y"]) > 8, f"{node} series x/y aligned ({len(s['x'])} pts)")
    check(s["y"][-1] > s["y"][0], f"{node} Id rises from off to on")
    m = j["metrics"]
    print(f"     {node:8} {mode:12} on/off={m['on_off']:.2e}  SS={m['ss']}  "
          f"Vth_eff={m['vth_eff']:.3f}  insight='{j['insight'][:60]}...'")

print("\n== on/off ratio must fall monotonically 45nm -> sub-1nm ==")
ratios = []
for node in ["45nm", "14nm", "7nm", "3nm", "1nm", "sub-1nm"]:
    m = c.post("/simulate", json={"node": node, "sweep": "idvg"}).json()["metrics"]
    ratios.append(m["on_off"])
print("     on/off:", [f"{x:.1e}" for x in ratios])
check(all(ratios[i] > ratios[i + 1] for i in range(len(ratios) - 1)),
      "on/off ratio strictly decreasing across nodes")

print("\n== /simulate leakage (vs node) ==")
j = c.post("/simulate", json={"node": "3nm", "sweep": "leakage"}).json()
check(len(j["series"]) == 3, "leakage returns 3 component series")
check(j["meta"]["xticks"] and j["meta"]["xticks"][0] == "45nm", "xticks are node labels")
itot = j["series"][2]["y"]
check(itot[-1] > itot[0], "I_total rises 45nm -> sub-1nm")

print("\n== /simulate tunneling (vs width) ==")
j = c.post("/simulate", json={"node": "1nm", "sweep": "tunneling"}).json()
s = j["series"][0]
check(s["xunit"] == "nm", "tunneling x-axis is width in nm (fix #4)")
check(s["x"][0] > s["x"][-1], "width sweeps thick -> thin")
check(s["y"][-1] > s["y"][0] and s["y"][-1] <= 1.0, "T rises as width thins, stays <= 1")
print(f"     T(width={s['x'][0]:.1f}nm)={s['y'][0]:.2e}  ->  T(width={s['x'][-1]:.1f}nm)={s['y'][-1]:.2e}")

print("\n== cache: repeat call is served from cache ==")
c.post("/simulate", json={"node": "7nm", "sweep": "idvg"})
j = c.post("/simulate", json={"node": "7nm", "sweep": "idvg"}).json()
check(j["meta"]["cached"] is True, "second identical /simulate is cached")

print("\n== /graph-data snapshot is sweep-aware (fix #1) ==")
c.post("/simulate", json={"node": "7nm", "mode": "near_quantum", "sweep": "leakage"})
g = c.get("/graph-data", params={"node": "7nm", "mode": "near_quantum", "sweep": "leakage"}).json()
check(g["meta"]["sweep"] == "leakage" and len(g["series"]) == 3,
      "graph-data returns the leakage snapshot, not idvg")

print("\n== /explain verdict gradient ==")
for node in ["45nm", "1nm", "sub-1nm"]:
    e = c.get("/explain", params={"node": node}).json()
    print(f"     {node:8} -> severity {e['verdict']['severity']} "
          f"({e['verdict']['label']})")
sev_45 = c.get("/explain", params={"node": "45nm"}).json()["verdict"]["severity"]
sev_sub = c.get("/explain", params={"node": "sub-1nm"}).json()["verdict"]["severity"]
check(sev_sub > sev_45, "sub-1nm is more severe than 45nm")

print("\n== /chat falls back to rule engine (no API key) ==")
r = c.post("/chat", json={"node": "1nm", "question": "why is it leaky?"}).json()
check(r["source"] in ("claude", "rule-based-fallback") and len(r["answer"]) > 10,
      f"chat answered via {r['source']}")

print("\n== Phase 7: materials (Si vs CNT vs Graphene) at 3nm ==")
mat_on_off = {}
for mat in ["Si", "CNT", "Graphene"]:
    j = c.post("/simulate", json={"node": "3nm", "material": mat, "sweep": "idvg"}).json()
    m = j["metrics"]
    mat_on_off[mat] = m["on_off"]
    print(f"     {mat:9} Ion={m['ion']:.2e}  Ioff={m['ioff']:.2e}  on/off={m['on_off']:.2e}")
check(mat_on_off["CNT"] > mat_on_off["Si"] > mat_on_off["Graphene"],
      "on/off ordering: CNT > Si > Graphene (higher mobility helps, no gap kills)")
check(mat_on_off["Graphene"] < 1e3,
      "graphene on/off collapses (gapless channel cannot switch off)")

gsev = c.get("/explain", params={"node": "3nm", "material": "Graphene"}).json()["verdict"]["severity"]
check(gsev >= 3, f"graphene at 3nm is severe (verdict severity {gsev})")

print("\n== Phase 7: accuracy toggle changes sweep resolution ==")
lo = c.post("/simulate", json={"node": "7nm", "sweep": "idvg", "accuracy": "low"}).json()
hi = c.post("/simulate", json={"node": "7nm", "sweep": "idvg", "accuracy": "high"}).json()
check(len(lo["series"][0]["x"]) == 60 and len(hi["series"][0]["x"]) == 300,
      f"low=60pts, high=300pts (got {len(lo['series'][0]['x'])}/{len(hi['series'][0]['x'])})")

print("\n== Phase 7: material tunneling (light mass tunnels more) ==")
tSi = c.post("/simulate", json={"node": "3nm", "sweep": "tunneling", "material": "Si"}).json()["series"][0]["y"]
tCNT = c.post("/simulate", json={"node": "3nm", "sweep": "tunneling", "material": "CNT"}).json()["series"][0]["y"]
check(tCNT[0] > tSi[0], "CNT (lighter m*) tunnels more than Si at the same width")

print("\n== error handling ==")
check(c.post("/simulate", json={"node": "999nm", "sweep": "idvg"}).status_code == 404,
      "unknown node -> 404")
check(c.post("/simulate", json={"node": "7nm", "material": "Unobtainium", "sweep": "idvg"}).status_code == 422,
      "unknown material -> 422")

print(f"\nALL {ok} CHECKS PASSED ✔")
