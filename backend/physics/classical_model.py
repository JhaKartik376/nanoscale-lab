"""
NanoScale Lab - Physics Mode 1: Classical drift-diffusion / compact MOSFET.

Scope: 45nm and 14nm nodes. Continuous-material, Boltzmann-statistics,
"gate has strong control" regime. Physics-inspired, laptop-cheap. NOT TCAD.

Public API (shared project signatures):
    solve_poisson_1d(doping, eps, dx, tol) -> psi
    idvg_classical(p, vg_array, vd)        -> dict{ vg, id }
    idvd_classical(p, vd_array, vg)        -> dict{ vd, id }
"""

import numpy as np
from scipy.linalg import solve_banded

# --------------------------------------------------------------------------
# Physical constants (SI) and material parameters
# --------------------------------------------------------------------------
Q       = 1.602176634e-19     # elementary charge [C]
KB      = 1.380649e-23        # Boltzmann constant [J/K]
T       = 300.0               # temperature [K]
VT      = KB * T / Q          # thermal voltage kT/q ~ 0.02585 V
EPS0    = 8.8541878128e-12    # vacuum permittivity [F/m]
EPS_OX  = 3.9 * EPS0          # SiO2-equivalent gate dielectric [F/m]
NI      = 1.0e16              # Si intrinsic carrier density [m^-3] (~1e10 cm^-3)
MU0     = 0.04                # reference electron mobility [m^2/(V*s)] (~400 cm^2/Vs)

LN10    = np.log(10.0)


# ==========================================================================
# 1) NONLINEAR 1D POISSON  (equilibrium, Boltzmann closure)
# ==========================================================================
def solve_poisson_1d(doping, eps, dx, tol=1e-6):
    """
    Solve the equilibrium nonlinear 1D Poisson equation

        d2(psi)/dx2 = -rho/eps ,   rho = q (p - n + N),
        n = ni exp(+psi/VT),  p = ni exp(-psi/VT),   N = Nd - Na (net doping)

    on a uniform grid using a three-point stencil and a damped Newton solve.

    Parameters
    ----------
    doping : array_like [m^-3]   net doping N_i = Nd - Na at each node
    eps    : float [F/m]         semiconductor permittivity
    dx     : float [m]           uniform grid spacing
    tol    : float [V]           convergence tol on max|delta psi|

    Returns
    -------
    psi : ndarray [V]            electrostatic potential at each node
    """
    N  = np.asarray(doping, dtype=float)
    nx = N.size

    # --- initial guess & Dirichlet BCs: local charge-neutral bulk potential
    #     p - n + N = 0  ->  -2 ni sinh(psi/VT) + N = 0  ->  psi = VT asinh(N/2ni)
    psi = VT * np.arcsinh(N / (2.0 * NI))
    psi_lo, psi_hi = psi[0], psi[-1]        # freeze contacts (ohmic Dirichlet)

    inv_dx2 = 1.0 / dx**2
    ab = np.zeros((3, nx - 2))              # banded Jacobian for interior nodes

    for _ in range(200):
        a = np.clip(psi / VT, -100.0, 100.0)
        n = NI * np.exp(a)
        p = NI * np.exp(-a)

        # residual F_i = laplacian(psi)_i + q/eps (p - n + N)_i   (interior)
        lap = (psi[:-2] - 2.0 * psi[1:-1] + psi[2:]) * inv_dx2
        F   = lap + (Q / eps) * (p[1:-1] - n[1:-1] + N[1:-1])

        # Jacobian (tridiagonal): dF/dpsi_i = -2/dx2 - q/eps (p+n)/VT ; off-diag 1/dx2
        diag  = -2.0 * inv_dx2 - (Q / eps) * (p[1:-1] + n[1:-1]) / VT
        ab[0, 1:]  = inv_dx2                 # super-diagonal
        ab[1, :]   = diag                    # main diagonal
        ab[2, :-1] = inv_dx2                 # sub-diagonal

        dpsi = solve_banded((1, 1), ab, -F)
        psi[1:-1] += 0.7 * dpsi             # damping = 0.7 for robustness
        psi[0], psi[-1] = psi_lo, psi_hi

        if np.max(np.abs(dpsi)) < tol:
            break

    return psi


# ==========================================================================
# 2) COMPACT MOSFET CORE  (subthreshold + triode/saturation)
# ==========================================================================
def _model_params(p):
    """Derive SI device parameters from a node params dict `p`.

    `p['Lg']` and `p['EOT']` are accepted either in nm/nm (pedagogical table
    convention) or already in metres; we normalise to metres here so the
    module works whether called from the demo or the backend node table.
    """
    Lg_nm = p['Lg'] * 1e9 if p['Lg'] < 1e-6 else p['Lg']    # -> nm
    eot_nm = p['EOT'] * 1e9 if p['EOT'] < 1e-6 else p['EOT']  # -> nm

    L    = Lg_nm * 1e-9                         # gate length [m]
    W    = p.get('W', 1e-6)                     # width [m] (default 1 um)
    if W < 1e-3:                               # allow W given in um
        W = W
    eot  = eot_nm * 1e-9                        # equiv. oxide thickness [m]
    cox  = EPS_OX / eot                         # oxide cap/area [F/m^2]
    mu   = MU0 * p['mu_rel']                    # channel mobility [m^2/Vs]
    n_id = (p['SS'] * 1e-3) / (LN10 * VT)       # ideality n from SS = n ln10 VT
    lam  = 0.05 * (20.0 / Lg_nm)               # channel-length modulation [1/V]
    dibl = p['DIBL'] * 1e-3                     # DIBL [V/V]
    I0   = mu * cox * (n_id - 1.0) * VT**2      # subthreshold prefactor [A]
    return dict(L=L, W=1e-6, cox=cox, mu=mu, n_id=n_id, lam=lam,
                dibl=dibl, I0=I0, Vth0=p['Vth0'])


def _id_core(mp, vgs, vds):
    """
    Vectorized drain current [A] for scalar/array vgs, vds using params `mp`.
    Continuous strong-inversion (triode->saturation via Vds_eff) plus an
    additive subthreshold branch clamped at threshold.
    """
    vgs = np.asarray(vgs, dtype=float)
    vds = np.asarray(vds, dtype=float)

    vth = mp['Vth0'] - mp['dibl'] * vds          # DIBL lowers Vth with Vds
    vov = vgs - vth
    wl  = mp['W'] / mp['L']
    k   = mp['mu'] * mp['cox'] * wl

    # strong inversion: Vds_eff = min(Vds, Vdsat=Vov); off below threshold
    vdse = np.minimum(vds, np.maximum(vov, 0.0))
    id_si = np.where(vov > 0.0,
                     k * (vov * vdse - 0.5 * vdse**2) * (1.0 + mp['lam'] * vds),
                     0.0)

    # subthreshold: exp clamped so it saturates (does not blow up) above Vth
    exp_arg = np.clip(np.minimum(vov, 0.0) / (mp['n_id'] * VT), -60.0, 0.0)
    id_sub  = mp['I0'] * wl * np.exp(exp_arg) * (1.0 - np.exp(-vds / VT))

    return id_si + id_sub


def _per_um(id_amp, mp):
    """Normalize current to A per micron of gate width."""
    return id_amp / (mp['W'] / 1e-6)


# ==========================================================================
# 3) PUBLIC SWEEPS
# ==========================================================================
def idvg_classical(p, vg_array, vd):
    """Id-Vg transfer sweep at fixed Vds. Returns dict{vg, id[A/um]}."""
    mp = _model_params(p)
    vg = np.asarray(vg_array, dtype=float)
    idc = _per_um(_id_core(mp, vg, float(vd)), mp)
    return {'vg': vg, 'id': idc}


def idvd_classical(p, vd_array, vg):
    """Id-Vd output sweep at fixed Vgs. Returns dict{vd, id[A/um]}."""
    mp = _model_params(p)
    vd = np.asarray(vd_array, dtype=float)
    idc = _per_um(_id_core(mp, float(vg), vd), mp)
    return {'vd': vd, 'id': idc}


# ==========================================================================
# 4) TINY DEMO
# ==========================================================================
if __name__ == '__main__':
    # ---- (a) Poisson: abrupt n-p junction, 200 nm, +/-1e23 m^-3 -----------
    nx, dx = 201, 1e-9
    N = np.where(np.arange(nx) < nx // 2, +1e23, -1e23)   # [m^-3]
    psi = solve_poisson_1d(N, eps=11.7 * EPS0, dx=dx, tol=1e-8)
    print("Poisson 1D  built-in potential Vbi = %.4f V (expect ~%.4f V)"
          % (psi[0] - psi[-1], 2 * VT * np.arcsinh(1e23 / (2 * NI))))

    # ---- (b) node params from the canonical table (Lg/EOT in nm) ----------
    p45 = dict(node='45nm', Lg=40, Vdd=1.00, Vth0=0.40, EOT=1.2,
               SS=70, DIBL=50, mu_rel=1.00, W=1e-6)
    p14 = dict(node='14nm', Lg=20, Vdd=0.80, Vth0=0.32, EOT=0.9,
               SS=75, DIBL=70, mu_rel=0.90, W=1e-6)

    for p in (p45, p14):
        vg = np.linspace(0.0, p['Vdd'], 6)
        g = idvg_classical(p, vg, vd=0.05)
        d = idvd_classical(p, np.linspace(0.0, p['Vdd'], 6), vg=p['Vdd'])
        mp = _model_params(p)
        print("\n[%s]  Cox=%.4f F/m^2  n=%.3f  SS=%.1f mV/dec  Ion=%.3e A/um"
              % (p['node'], mp['cox'], mp['n_id'],
                 mp['n_id'] * LN10 * VT * 1e3, d['id'][-1]))
        print("  Id-Vg @Vd=0.05:", np.array2string(g['id'], precision=2))
