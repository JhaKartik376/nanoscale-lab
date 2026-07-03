"""
physics/tunneling_model.py
==========================
NanoScale Lab -- Physics Mode 3 (Quantum-Dominated, 1nm / sub-1nm).

Conceptual, physics-INSPIRED models of the effects that break a transistor
once the channel/oxide reach the ~1 nm scale:

    * WKB tunneling through source-drain and gate-oxide barriers
    * Discrete confinement levels of a quantum-well channel
    * Landauer (ballistic) transport with quantized conductance

NOT TCAD accurate. Pure numpy + scipy, runs on a normal laptop.

Note on WKB: the transmission is a probability, so it is bounded T <= 1. As a
barrier thins, T *rises steeply and then saturates at the ballistic ceiling 1*
-- it does not diverge.

Shared signatures (do not rename -- backend / frontend / AI depend on them):
    wkb_transmission(E, barrier_fn, x_grid, m_eff) -> T
    rect_barrier_T(E, phi, width, m_eff)           -> T
    well_energy_levels(L, m_eff, n_levels)         -> [E_n ...]   (eV)
    ballistic_current(p, vg, vd)                   -> id          (A/um)

Unit convention at the API boundary:
    * Energies / potentials passed in electron-volts (eV).
    * Lengths passed in meters.
    * Effective mass passed in kilograms (e.g. 0.26 * m_e).
Everything is converted to SI (Joules) internally before hitting hbar.

Note: `p` uses the shared table convention (Lg in nm); ballistic_current
converts Lg -> meters internally.
"""

from __future__ import annotations

import numpy as np
from scipy import constants as sc

try:                                    # scipy >= 1.6 exposes simpson
    from scipy.integrate import simpson
except ImportError:                     # very old scipy fallback
    from scipy.integrate import simps as simpson


# --------------------------------------------------------------------------
# Fundamental constants (scipy, SI)
# --------------------------------------------------------------------------
HBAR = sc.hbar                 # reduced Planck constant  [J s]
H    = sc.h                    # Planck constant          [J s]
M0   = sc.m_e                  # free electron mass       [kg]
Q    = sc.e                    # elementary charge        [C]
KB   = sc.k                    # Boltzmann constant       [J/K]
EV   = sc.e                    # 1 eV in Joules           [J/eV]

G0   = 2.0 * Q**2 / H          # conductance quantum ~ 7.748e-5 S  (12.9 kOhm)

T_ROOM = 300.0                 # K
VT     = KB * T_ROOM / Q       # thermal voltage ~ 0.02585 V
M_SI   = 0.26 * M0             # default Si channel effective mass


# --------------------------------------------------------------------------
# 1. General WKB transmission through an arbitrary 1D barrier
# --------------------------------------------------------------------------
def wkb_transmission(E, barrier_fn, x_grid, m_eff=M_SI):
    """WKB transmission through an arbitrary barrier V(x):

        T ~ exp( -2 * integral kappa(x) dx )         over V(x) > E
        kappa(x) = sqrt( 2 m* ( V(x) - E ) ) / hbar

    E: carrier energy [eV]; barrier_fn: callable V(x) in eV (x in m, vectorized);
    x_grid: positions [m]; m_eff: effective mass [kg]. Returns T in [0,1].

    Pure exponential (no prefactor); valid for opaque barriers (T << 1). T
    saturates at 1 (never diverges) as the barrier vanishes.
    """
    x = np.asarray(x_grid, dtype=float)
    V = np.asarray(barrier_fn(x), dtype=float)          # eV
    dV = (V - E) * EV                                   # J, forbidden if > 0
    kappa = np.where(dV > 0.0,
                     np.sqrt(2.0 * m_eff * np.maximum(dV, 0.0)) / HBAR,
                     0.0)                                # 1/m
    integral = simpson(kappa, x=x)                      # dimensionless
    return float(min(np.exp(-2.0 * integral), 1.0))


# --------------------------------------------------------------------------
# 2. Closed-form rectangular barrier
# --------------------------------------------------------------------------
def rect_barrier_T(E, phi, width, m_eff=M_SI):
    """Closed-form WKB for a rectangular barrier of height `phi` (eV) and
    thickness `width` (m):

        T ~ exp( -2 * width * sqrt( 2 m* ( phi - E ) ) / hbar )

    For E >= phi (over-barrier) we clamp T = 1.
    """
    barrier = (phi - E) * EV                            # J
    if barrier <= 0.0:                                  # over the barrier
        return 1.0
    kappa = np.sqrt(2.0 * m_eff * barrier) / HBAR       # 1/m
    return float(np.exp(-2.0 * kappa * width))


# --------------------------------------------------------------------------
# 3. Quantum-well discrete energy levels (infinite well)
# --------------------------------------------------------------------------
def well_energy_levels(L, m_eff=M_SI, n_levels=5):
    """Bound-state energies of an infinite square well of width `L` (m):

        E_n = n^2 h^2 / (8 m* L^2)  =  n^2 pi^2 hbar^2 / (2 m* L^2)

    Returns [E_1, E_2, ...] in eV. Level spacing grows as 1/L^2. A real
    (finite) well is transcendental with fewer, slightly lower levels plus
    wavefunction leakage into the barrier; the 1/L^2 scaling is identical.
    """
    n = np.arange(1, int(n_levels) + 1)
    E_joule = (n**2) * H**2 / (8.0 * m_eff * L**2)      # J
    return (E_joule / EV).tolist()                      # eV


# --------------------------------------------------------------------------
# 4. Landauer / ballistic drain current  (top-of-the-barrier model)
# --------------------------------------------------------------------------
def _fermi(E_ev, mu_ev, temp=T_ROOM):
    """Fermi-Dirac occupancy; E and mu in eV."""
    x = (E_ev - mu_ev) / (KB * temp / Q)
    return 1.0 / (1.0 + np.exp(np.clip(x, -500.0, 500.0)))


def ballistic_current(p, vg, vd, n_energy=4000):
    """Landauer ballistic drain current per micron of width (A/um):

        I = (2e/h) * integral M(E) T(E) [ f_S(E) - f_D(E) ] dE

    Top-of-the-barrier (Natori) picture: the gate sets a single barrier height;
    overdrive (vg - vth) and DIBL lower it. Carriers fly OVER (T=1) or TUNNEL
    through the ~Lg-wide barrier (source-drain leakage floor). M(E) counts 2D
    transverse modes. The f_S - f_D window saturates the current with drain
    bias (ballistic plateau). Single subband, one rectangular barrier.
    """
    # material-aware effective mass (Phase 7): lighter channel -> more tunneling
    m_eff = p.get("m_eff", p.get("m_rel", 1.0) * M_SI)
    vth   = p.get("Vth0", 0.20)
    dibl  = p.get("DIBL", 0.0) * 1e-3                   # mV/V -> V/V
    Lg    = p.get("Lg", 8.0) * 1e-9                     # nm -> tunneling width [m]
    W     = p.get("W", 1.0) * 1e-6                      # um -> channel width [m]
    eg    = p.get("eg", 1.12)                           # bandgap [eV]
    linear = p.get("dispersion", "parabolic") == "linear"

    # the gate can never raise the barrier above ~half the bandgap: a gapless
    # channel (graphene) has almost no barrier, so it cannot be switched off.
    phi0  = min(p.get("phi0", 0.45), 0.5 * eg + 0.03)   # barrier at vg = vth [eV]

    Ec  = 0.0                                           # source band edge  [eV]
    muS = 0.05                                          # source Fermi level [eV]
    muD = muS - vd                                      # drain Fermi level  [eV]

    Etop = Ec + max(phi0 - (vg - vth) - dibl * vd, -0.15)

    Emin = Ec - 5.0 * VT
    Emax = max(muS, Etop) + 0.6
    E = np.linspace(Emin, Emax, int(n_energy))          # eV

    # mode density: parabolic band ~ sqrt(E-Ec); linear (graphene) ~ (E-Ec)
    de = np.maximum((E - Ec) * EV, 0.0)                 # J
    if linear:
        vF = 1.0e6                                      # graphene Fermi velocity [m/s]
        M = W * (E - Ec).clip(min=0.0) * EV / (np.pi * HBAR * vF)
    else:
        M = W * np.sqrt(2.0 * m_eff * de) / (np.pi * HBAR)

    barrier = (Etop - E) * EV                           # J
    kappa = np.sqrt(2.0 * m_eff * np.maximum(barrier, 0.0)) / HBAR
    T = np.where(barrier > 0.0, np.exp(-2.0 * kappa * Lg), 1.0)

    window = _fermi(E, muS) - _fermi(E, muD)            # dimensionless
    integrand = M * T * window

    integral_J = simpson(integrand, x=E * EV)           # J
    id_amp = (2.0 * Q / H) * integral_J                 # A  (for width W = 1 um)
    return float(id_amp)                                # already per micron


# --------------------------------------------------------------------------
# Demo
# --------------------------------------------------------------------------
def _demo():
    print("=" * 68)
    print(" NanoScale Lab -- Mode 3 Quantum-Dominated : tunneling_model demo")
    print("=" * 68)
    print(f"  G0 (conductance quantum) = {G0*1e6:8.3f} uS   "
          f"(R0 = {1.0/G0/1e3:6.3f} kOhm)")
    print(f"  V_T = kT/q               = {VT*1e3:8.3f} mV")
    print(f"  m* (Si)                  = {M_SI/M0:8.3f} m0")

    print("\n[a] Source-drain barrier tunneling  (E = 0.10 eV, phi = 0.90 eV)")
    print("     width(nm)     T           relative-to-3nm")
    E, phi = 0.10, 0.90
    widths_nm = [3.0, 2.0, 1.5, 1.0, 0.7, 0.5]
    T3 = rect_barrier_T(E, phi, 3.0e-9)
    for w in widths_nm:
        T = rect_barrier_T(E, phi, w * 1e-9)
        print(f"       {w:5.2f}     {T:10.3e}     x{T/T3:11.3e}")

    xg = np.linspace(0.0, 1.0e-9, 400)
    T_general = wkb_transmission(E, lambda x: np.full_like(x, phi), xg)
    T_closed  = rect_barrier_T(E, phi, 1.0e-9)
    print(f"     WKB check @1nm : general={T_general:.3e}  closed={T_closed:.3e}")

    print("\n[b] Infinite-well levels  E_n = n^2 h^2 / (8 m* L^2)")
    for L_nm in [3.0, 1.0, 0.5]:
        lv = well_energy_levels(L_nm * 1e-9, n_levels=4)
        dE = lv[1] - lv[0]
        print(f"     L = {L_nm:4.1f} nm : "
              f"E1..E4 = [{', '.join(f'{e:6.3f}' for e in lv)}] eV   "
              f"dE(2-1)={dE:6.3f} eV = {dE/VT:6.0f} kT")

    print("\n[c] Ballistic Landauer Id-Vg : on/off ratio vs gate length")
    for node, Lg, Vdd, Vth0, dibl in [
        ("7nm  ", 16.0, 0.70, 0.28,  95.0),
        ("1nm  ",  8.0, 0.60, 0.20, 160.0),
        ("sub1 ",  5.0, 0.50, 0.15, 220.0),
    ]:
        p = dict(node=node.strip(), Lg=Lg, Vdd=Vdd, Vth0=Vth0,
                 DIBL=dibl, mu_rel=1.0, W=1.0)
        i_off = ballistic_current(p, vg=0.0,  vd=Vdd)
        i_on  = ballistic_current(p, vg=Vdd,  vd=Vdd)
        ratio = i_on / max(i_off, 1e-30)
        print(f"     {node}: Ion={i_on*1e3:7.3f} mA/um   "
              f"Ioff={i_off:9.2e} A/um   Ion/Ioff={ratio:9.2e}")

    print("\n  --> as Lg shrinks the source-drain tunneling floor lifts Ioff,")
    print("      Ion/Ioff collapses toward ~1: the switch stops switching.")
    print("=" * 68)


if __name__ == "__main__":
    _demo()
