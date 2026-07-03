"""Single source of truth for the pedagogical node table.

Canonical unit convention for the `p` params dict consumed by every physics
function (classical_model / quantum_correction / tunneling_model):

    Lg     : gate length          [nm]
    EOT    : equiv. oxide thick.   [nm]
    Vdd    : supply voltage        [V]
    Vth0   : nominal threshold     [V]
    SS     : subthreshold swing    [mV/dec]
    DIBL   : drain-induced BL      [mV/V]
    mu_rel : mobility, rel. 45nm   [-]
    W      : channel width         [um]   (currents reported per micron)

Illustrative values -- physics-INSPIRED, not TCAD-calibrated.
"""

# node -> device parameters (Lg, EOT in nm; see module docstring)
NODE_TABLE = {
    "45nm":    {"arch": "Planar bulk",   "Lg": 40, "Vdd": 1.00, "Vth0": 0.40,
                "EOT": 1.2, "SS": 70,  "DIBL": 50,  "mu_rel": 1.00},
    "14nm":    {"arch": "FinFET",        "Lg": 20, "Vdd": 0.80, "Vth0": 0.32,
                "EOT": 0.9, "SS": 75,  "DIBL": 70,  "mu_rel": 0.90},
    "7nm":     {"arch": "FinFET",        "Lg": 16, "Vdd": 0.70, "Vth0": 0.28,
                "EOT": 0.8, "SS": 80,  "DIBL": 95,  "mu_rel": 0.82},
    "3nm":     {"arch": "GAA nanosheet", "Lg": 12, "Vdd": 0.65, "Vth0": 0.24,
                "EOT": 0.7, "SS": 85,  "DIBL": 120, "mu_rel": 0.75},
    "1nm":     {"arch": "GAA / CFET",    "Lg": 8,  "Vdd": 0.60, "Vth0": 0.20,
                "EOT": 0.6, "SS": 95,  "DIBL": 160, "mu_rel": 0.65},
    "sub-1nm": {"arch": "2D-FET / CNT",  "Lg": 5,  "Vdd": 0.50, "Vth0": 0.15,
                "EOT": 0.5, "SS": 115, "DIBL": 220, "mu_rel": 0.55},
}

# Default physics mode per node (all modes selectable at any node).
DEFAULT_MODE = {
    "45nm": "classical", "14nm": "classical",
    "7nm":  "near_quantum", "3nm": "near_quantum",
    "1nm":  "quantum", "sub-1nm": "quantum",
}

DEFAULT_WIDTH_UM = 1.0   # currents reported per micron of width (A/um)

# ---------------------------------------------------------------------------
# Phase 7: channel MATERIAL presets (pedagogical proxies, relative to Si).
#   m_rel      : effective mass / (0.26 m0)  -> lighter = MORE tunneling
#   mu_mat     : mobility multiplier         -> higher = more drive (Ion)
#   eg         : bandgap (eV)                -> smaller = worse off-state / BTBT
#   dispersion : 'parabolic' | 'linear'      -> graphene is gapless & linear
# The story: CNT = light mass + high mobility (fast, but tunnels sooner);
# graphene = huge mobility but ~zero gap (great conductor, cannot switch off).
# ---------------------------------------------------------------------------
MATERIALS = {
    "Si":       {"m_rel": 1.00, "mu_mat": 1.0,  "eg": 1.12, "dispersion": "parabolic"},
    "CNT":      {"m_rel": 0.06, "mu_mat": 4.0,  "eg": 0.60, "dispersion": "parabolic"},
    "Graphene": {"m_rel": 0.02, "mu_mat": 10.0, "eg": 0.02, "dispersion": "linear"},
}

# Phase 7: ACCURACY toggle -> grid resolution + solver tolerance.
ACCURACY = {
    "low":    {"points": 60,  "poisson_nx": 101, "tol": 1e-4},
    "medium": {"points": 120, "poisson_nx": 201, "tol": 1e-6},
    "high":   {"points": 300, "poisson_nx": 401, "tol": 1e-8},
}


def list_nodes() -> list:
    return list(NODE_TABLE.keys())


def list_materials() -> list:
    return list(MATERIALS.keys())


def build_params(node: str, material: str = "Si",
                 width_um: float = DEFAULT_WIDTH_UM) -> dict:
    """Assemble the `p` dict consumed by every physics function.

    Keys: node, arch, Lg, Vdd, Vth0, EOT, SS, DIBL, mu_rel, W,
          material, m_rel, eg, dispersion   (Lg/EOT in nm, W in um).
    `mu_rel` already folds in the material mobility multiplier so the classical
    compact model picks it up for free.
    """
    if node not in NODE_TABLE:
        raise KeyError(f"unknown node '{node}'. valid: {list_nodes()}")
    if material not in MATERIALS:
        raise KeyError(f"unknown material '{material}'. valid: {list_materials()}")
    row = NODE_TABLE[node]
    mat = MATERIALS[material]
    return {
        "node":       node,
        "arch":       row["arch"],
        "Lg":         row["Lg"],       # nm
        "Vdd":        row["Vdd"],
        "Vth0":       row["Vth0"],
        "EOT":        row["EOT"],      # nm
        "SS":         row["SS"],       # mV/dec
        "DIBL":       row["DIBL"],     # mV/V
        "mu_rel":     row["mu_rel"] * mat["mu_mat"],   # node * material mobility
        "W":          width_um,        # um
        "material":   material,
        "m_rel":      mat["m_rel"],
        "eg":         mat["eg"],       # eV
        "dispersion": mat["dispersion"],
    }
