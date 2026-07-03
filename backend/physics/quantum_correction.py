"""
physics/quantum_correction.py
NanoScale Lab -- Physics Mode 2: Near-Quantum (7nm - 3nm)

Physics-INSPIRED (not TCAD) models for short-channel electrostatics and
leakage as the technology node shrinks. Runs on a normal laptop with
numpy only.

Conventions (shared project context):
  SI internally; T = 300 K  ->  V_T = kT/q = 0.0259 V
  params dict `p`: Lg, EOT in nm; W in um; currents per micron (A/um)
  m* = 0.26 * m0 for the Si channel

Public API (shared project signatures):
    vth_short_channel(p, vds)            -> vth_eff
    subthreshold_swing(p)                -> ss_mv_dec
    leakage_current(p)                   -> dict{ i_sub, i_gate, i_total }
    density_gradient_correction(psi, ..) -> psi_qm
"""

import numpy as np

# ---------------------------------------------------------------------------
# Physical constants (SI)
# ---------------------------------------------------------------------------
Q       = 1.602176634e-19     # C
EPS0    = 8.8541878128e-12    # F/m
EPS_OX  = 3.9 * EPS0          # SiO2 permittivity
HBAR    = 1.054571817e-34     # J*s
M0      = 9.1093837015e-31    # kg
M_EFF   = 0.26 * M0           # Si channel effective mass
V_T     = 0.0259              # thermal voltage at 300 K (V)

# ---------------------------------------------------------------------------
# Empirical / calibrated model constants (ILLUSTRATIVE, not measured)
# ---------------------------------------------------------------------------
ALPHA_CS = 0.20   # V     charge-sharing roll-off amplitude
L0_CS    = 5.0    # nm    characteristic short-channel length scale
I0_SUB   = 1.0e-7 # A     subthreshold reference (technology) current
A_GATE   = 1.0e4  # A/cm^2 direct-tunnel prefactor
B_GATE   = 6.0    # 1/(nm*sqrt(eV)) tunnel decay constant
PHI_B    = 3.1    # eV    Si/SiO2 conduction-band offset (tunnel barrier)
I0_ON    = 1.0e-4 # A     on-current reference (square-law prefactor)
A_GAP    = 1.0e-3 # A/um  band-to-band (Eg) leakage-floor prefactor  (Phase 7)
EG_REF   = 0.06   # eV    bandgap decay scale: I_gap ~ A_GAP*exp(-Eg/EG_REF)


# ---------------------------------------------------------------------------
# 1. Short-channel threshold voltage: DIBL + charge-sharing roll-off
# ---------------------------------------------------------------------------
def vth_short_channel(p, vds):
    """Effective threshold voltage including DIBL and charge-sharing SCE.

        Vth_eff = Vth0 - (DIBL/1000)*Vds - ALPHA_CS*exp(-Lg/L0_CS)

    DIBL is stored in mV/V (hence /1000). The roll-off term grows as Lg
    shrinks -> the gate loses electrostatic control and Vth falls.
    """
    dibl_V_per_V = p['DIBL'] / 1000.0
    rolloff = ALPHA_CS * np.exp(-p['Lg'] / L0_CS)
    return p['Vth0'] - dibl_V_per_V * vds - rolloff


# ---------------------------------------------------------------------------
# 2. Subthreshold swing degradation
# ---------------------------------------------------------------------------
def subthreshold_swing(p, cdep_over_cox=None):
    """Subthreshold swing SS = n * 60 mV/dec, n = 1 + Cdep/Cox.

    Default: return the canonical node-table SS (authoritative). If
    `cdep_over_cox` is supplied, compute SS = (1 + Cdep/Cox) * 60 mV/dec.
    """
    if cdep_over_cox is None:
        return p['SS']                       # mV/dec, from node table
    n = 1.0 + cdep_over_cox
    return n * 60.0


def body_factor(p):
    """Ideality / body factor n implied by the node-table SS."""
    return p['SS'] / 60.0


# ---------------------------------------------------------------------------
# 3. Leakage models  (subthreshold + gate tunneling; GIDL/junction noted)
# ---------------------------------------------------------------------------
def leakage_current(p):
    """Off-state leakage decomposition.

    Returns dict{ i_sub, i_gate, i_total } in A/um.

    (i)  Subthreshold: I_sub = I0*(W/L)*exp(-Vth_eff/(n*V_T)) at Vds=Vdd.
    (ii) Direct gate tunneling (WKB/Fowler-Nordheim flavor):
           J_gate = A*(Vox/EOT)^2 * exp(-B*EOT*sqrt(phi_b)) ; I_gate = J*(W*Lg).
         Both the (Vox/EOT)^2 field term and the exponential rise as EOT thins.
    (iii) GIDL and junction leakage: noted, not modelled numerically here.
    """
    W_um  = p['W']                   # width in um (default 1 um)
    Lg_um = p['Lg'] * 1e-3           # gate length nm -> um
    aspect = W_um / Lg_um            # W/L (dimensionless)

    # --- (i) subthreshold leakage --------------------------------------
    n       = body_factor(p)
    vth_eff = vth_short_channel(p, p['Vdd'])
    i_sub   = I0_SUB * aspect * np.exp(-vth_eff / (n * V_T))

    # --- (ii) gate direct tunneling ------------------------------------
    vox   = p['Vdd']                                 # oxide voltage ~ Vdd
    eot   = p['EOT']                                 # nm
    field = vox / eot                                # V/nm
    j_gate = A_GATE * field**2 * np.exp(-B_GATE * eot * np.sqrt(PHI_B))  # A/cm^2
    area_cm2 = (W_um * 1e-4) * (p['Lg'] * 1e-7)      # um->cm, nm->cm
    i_gate = j_gate * area_cm2                        # A

    # --- (iii) band-to-band / bandgap-limited off floor (Phase 7, material) --
    # Small-gap channels (graphene ~0 eV) leak catastrophically; Si (1.12 eV)
    # is negligible. Folded into i_total so on/off collapses for gapless
    # materials in every mode. Defaults to Si when no material set.
    eg = p.get('eg', 1.12)                            # eV
    i_gap = A_GAP * W_um * np.exp(-eg / EG_REF)        # A/um

    i_total = i_sub + i_gate + i_gap
    return {'i_sub': float(i_sub), 'i_gate': float(i_gate),
            'i_total': float(i_total)}


def on_current(p):
    """Rough square-law on-current for on/off ratio illustration (A/um).

        I_on ~ I0_ON * mu_rel * (W/L) * max(Vdd - Vth_eff, 0)^2
    """
    Lg_um  = p['Lg'] * 1e-3
    aspect = p['W'] / Lg_um
    vov    = max(p['Vdd'] - vth_short_channel(p, p['Vdd']), 0.0)
    return float(I0_ON * p['mu_rel'] * aspect * vov**2)


# ---------------------------------------------------------------------------
# 4. Quantum correction: density-gradient (Bohm) potential
# ---------------------------------------------------------------------------
def density_gradient_correction(psi, n=None, dx=1e-9, m_eff=M_EFF):
    """Simplified density-gradient quantum correction to the potential.

        psi_qm = psi + (hbar^2 / (6 m* q)) * ( lap(sqrt(n)) / sqrt(n) )

    Penalizes sharp density curvature -> pushes the charge centroid off the
    oxide interface into the channel ("dark space"), giving a Vth up-shift and
    a reduced effective gate capacitance. Single-parameter model, far cheaper
    than a self-consistent Schrodinger-Poisson solve; captures the set-back
    trend only (no discrete subbands -- use tunneling_model.py for those).

    The sqrt(n) denominator diverges in near-empty tails, so evaluate this only
    where carriers actually exist (inside the inversion layer).
    """
    psi = np.asarray(psi, dtype=float)
    if n is None:
        n = np.exp(psi / V_T)
    n = np.asarray(n, dtype=float)

    sqrt_n = np.sqrt(np.clip(n, 1e-300, None))

    lap = np.empty_like(sqrt_n)
    lap[1:-1] = (sqrt_n[2:] - 2.0 * sqrt_n[1:-1] + sqrt_n[:-2]) / dx**2
    lap[0]  = lap[1]
    lap[-1] = lap[-2]

    prefactor = HBAR**2 / (6.0 * m_eff * Q)     # V * m^2
    quantum_potential = prefactor * lap / sqrt_n
    return psi + quantum_potential


# ---------------------------------------------------------------------------
# Convenience: build params from the shared node table (standalone use)
# ---------------------------------------------------------------------------
_NODE_TABLE = {
    #  node      Lg  Vdd   Vth0  EOT  SS   DIBL  mu_rel   (Lg, EOT in nm)
    '45nm':    (40, 1.00, 0.40, 1.2, 70,  50,  1.00),
    '14nm':    (20, 0.80, 0.32, 0.9, 75,  70,  0.90),
    '7nm':     (16, 0.70, 0.28, 0.8, 80,  95,  0.82),
    '3nm':     (12, 0.65, 0.24, 0.7, 85,  120, 0.75),
    '1nm':     (8,  0.60, 0.20, 0.6, 95,  160, 0.65),
    'sub-1nm': (5,  0.50, 0.15, 0.5, 115, 220, 0.55),
}


def make_params(node, W=1.0):
    """Build the shared `p` params dict for a node (W in um)."""
    Lg, Vdd, Vth0, EOT, SS, DIBL, mu_rel = _NODE_TABLE[node]
    return dict(node=node, Lg=Lg, Vdd=Vdd, Vth0=Vth0, EOT=EOT,
                SS=SS, DIBL=DIBL, mu_rel=mu_rel, W=W)


# ---------------------------------------------------------------------------
# Demo: sweep Mode-2 nodes 7nm -> 3nm (with neighbours) and show leakage rise
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    print("NanoScale Lab -- Mode 2 Near-Quantum: leakage vs node\n")
    header = (f"{'node':>8} {'Vth_eff':>8} {'n':>5} {'SS':>4} "
              f"{'i_sub':>10} {'i_gate':>10} {'i_total':>10} {'Ion/Ioff':>10}")
    print(header)
    print("-" * len(header))

    for node in ['45nm', '14nm', '7nm', '3nm', '1nm', 'sub-1nm']:
        p   = make_params(node)
        vte = vth_short_channel(p, p['Vdd'])
        n   = body_factor(p)
        ss  = subthreshold_swing(p)
        lk  = leakage_current(p)
        ion = on_current(p)
        ratio = ion / lk['i_total']
        mark = "  <- Mode 2" if node in ('7nm', '3nm') else ""
        print(f"{node:>8} {vte:8.3f} {n:5.2f} {ss:4.0f} "
              f"{lk['i_sub']:10.2e} {lk['i_gate']:10.2e} "
              f"{lk['i_total']:10.2e} {ratio:10.2e}{mark}")

    i7 = leakage_current(make_params('7nm'))['i_total']
    i3 = leakage_current(make_params('3nm'))['i_total']
    print(f"\nLeakage RISES {i3/i7:.1f}x going 7nm -> 3nm "
          f"({i7*1e9:.1f} nA/um -> {i3*1e9:.1f} nA/um).")

    # Quantum correction demo: a classical inversion layer that peaks ~1 nm
    # from the oxide interface (x=0). Report the density-gradient shift AT THE
    # CHARGE PEAK -- that is the physically meaningful set-back (a *negative*
    # dPsi there depletes the interface -> Vth up-shift). (A positive lobe
    # exists only in the far, near-empty tail and is a windowing artifact.)
    x   = np.linspace(0, 8e-9, 201)                  # 8 nm into the channel
    dx  = x[1] - x[0]
    psi = np.zeros_like(x)                            # flat baseline potential
    n_cl = np.exp(-((x - 1.0e-9) / 1.2e-9)**2)       # classical inversion charge
    psi_qm = density_gradient_correction(psi, n=n_cl, dx=dx)
    shift_meV = 1e3 * (psi_qm - psi)
    i_peak = int(np.argmax(n_cl))
    print(f"\nDensity-gradient correction (flat psi): dPsi_qm at the charge "
          f"peak (x={x[i_peak]*1e9:.1f} nm) = {shift_meV[i_peak]:+.1f} meV")
    print("  -> negative shift = interface charge set-back (dark space): the")
    print("     inversion centroid moves deeper, lowering Cox_eff and raising Vth.")
