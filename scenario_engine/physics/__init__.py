"""
scenario_engine.physics

First-principles physics utilities adopted (CC0) from
JinnZ2/Geometric-to-Binary-Computational-Bridge/fabrication/.

  pipe_modes   : distributed-element acoustic modes
                 (open/closed pipes, rectangular boxes, cylinders)
  eigenmodes   : lumped 1-D LC chain eigenvalue solver
                 (Jacobi rotation, stdlib-only)

These ground scenarios' resonant/modal frequencies in physics rather
than hard-coded constants. Pure stdlib; no numpy.
"""

from .pipe_modes import (
    C_AIR,
    J_PRIME_ZEROS,
    box_modes,
    cylinder_modes,
    ka_check,
    pipe_modes,
)
from .eigenmodes import (
    predict_eigenmodes,
    predict_eigenmodes_full,
)

__all__ = [
    "C_AIR",
    "J_PRIME_ZEROS",
    "box_modes",
    "cylinder_modes",
    "ka_check",
    "pipe_modes",
    "predict_eigenmodes",
    "predict_eigenmodes_full",
]
