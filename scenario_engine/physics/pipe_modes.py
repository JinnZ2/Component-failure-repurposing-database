"""
pipe_modes.py  (fabrication/)

Distributed-element acoustic mode predictor. Pure first-principles;
no empirical fits.

Used when ka > ~0.3 -- the lumped-element chain in eigenmodes.py
treats cavities as point compliances and tubes as point inertances.
That model breaks once wavelength approaches cavity size, and
distributed standing-wave modes appear that the chain never
predicts. This file gives them back.

Geometries covered:
  open-open tube     : f_n = n · c / (2L)              n=1,2,3,...
  closed-closed tube : f_n = n · c / (2L)              n=1,2,3,...
  open-closed tube   : f_n = (2n-1) · c / (4L)         n=1,2,3,...
  rectangular box    : f_{lmn} = (c/2)·√((l/Lx)²+(m/Ly)²+(n/Lz)²)
  cylindrical cavity : axial + transverse (Bessel zeros of J'_m)

License: CC0. Stdlib only.

Adopted from
JinnZ2/Geometric-to-Binary-Computational-Bridge/fabrication/pipe_modes.py.
"""
import math


C_AIR = 343.0    # default speed of sound (m/s) at 15 °C


# Bessel function J'_m first zeros (m=0..3, n=1..3).
# Standard mathematical-table values. These give transverse modes
# of a rigid-wall cylinder.
J_PRIME_ZEROS = {
    0: [3.8317, 7.0156, 10.1735],
    1: [1.8412, 5.3314, 8.5363],
    2: [3.0542, 6.7061, 9.9695],
    3: [4.2012, 8.0152, 11.3459],
}


def pipe_modes(length_m, end_condition, n_max=4, c=C_AIR):
    """
    1-D pipe with two end conditions.
      end_condition ∈ {"open_open", "closed_closed", "open_closed"}
    """
    f = []
    for n in range(1, n_max+1):
        if end_condition in ("open_open", "closed_closed"):
            f.append(n * c / (2 * length_m))
        elif end_condition == "open_closed":
            f.append((2*n - 1) * c / (4 * length_m))
        else:
            raise ValueError(f"Unknown end_condition: {end_condition}")
    return [{"f": v, "mode_index": i, "kind": "pipe",
             "axial_n": i+1, "end": end_condition}
            for i, v in enumerate(f)]


def box_modes(Lx, Ly, Lz, n_max=2, c=C_AIR):
    """
    Rigid-wall rectangular box. Returns all unique (l,m,n) with at
    least one index > 0 and each index ≤ n_max, sorted by f.
    """
    modes = []
    for l in range(n_max+1):
        for m in range(n_max+1):
            for n in range(n_max+1):
                if l == 0 and m == 0 and n == 0:
                    continue
                f = (c/2) * math.sqrt((l/Lx)**2 + (m/Ly)**2 + (n/Lz)**2)
                modes.append({"f": f, "indices": (l, m, n), "kind": "box"})
    modes.sort(key=lambda d: d["f"])
    for i, m in enumerate(modes):
        m["mode_index"] = i
    return modes


def cylinder_modes(radius_m, length_m, n_axial=3, m_radial=2, c=C_AIR):
    """
    Combined axial + transverse modes of a rigid-wall cylinder.
      axial      : f_n = n·c/(2L)
      transverse : f_{m,k} = (c / (2π)) · (α_{m,k} / a)   α from J'_m
      combined (separable):  f² = f_axial² + f_transverse²
    """
    modes = []
    # axial-only modes (transverse index 0,0 -- uniform pressure)
    for n in range(1, n_axial+1):
        f_ax = n * c / (2 * length_m)
        modes.append({
            "f":       f_ax,
            "kind":    "cylinder",
            "axial_n": n,
            "radial":  (0, 0),
        })
    # combined modes
    for m_az in J_PRIME_ZEROS:
        zeros = J_PRIME_ZEROS[m_az][:m_radial]
        for k, alpha in enumerate(zeros, start=1):
            f_tr = (c / (2*math.pi)) * (alpha / radius_m)
            for n in range(0, n_axial+1):
                f_ax = n * c / (2 * length_m)
                f = math.sqrt(f_ax**2 + f_tr**2)
                modes.append({
                    "f":       f,
                    "kind":    "cylinder",
                    "axial_n": n,
                    "radial":  (m_az, k),
                })
    modes.sort(key=lambda d: d["f"])
    for i, m in enumerate(modes):
        m["mode_index"] = i
    return modes


def ka_check(geometry, c=C_AIR):
    """
    Returns ka_max for the lowest predicted lumped mode.
    Caller can decide: if ka > 0.3 -> distributed prediction needed.

    geometry: dict with at least 'characteristic_dim_m' and
              'lumped_f_lowest_Hz'.
    """
    a = geometry["characteristic_dim_m"]
    f = geometry["lumped_f_lowest_Hz"]
    k = 2 * math.pi * f / c
    return k * a
