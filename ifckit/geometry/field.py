# This file was generated with the assistance of an AI coding tool.
"""ifckit.geometry.field — re-export facade over geometrykit.

Fields live in geometrykit, whose implementation matches the code
this module carried except for deliberate OCC exits: point projection
uses the kernel (``Surface.project``), normals are analytic
(``Surface.normal_at``), and 2D segment intersection is a pure
deterministic solve — no OCC requirement on those paths. Trim-loop
sampling still uses the OCC-gated ``occ_trim_loops`` in both copies.
Import through ``ifckit.geometry`` unchanged.
"""

from geometrykit.geometry.field import (
    Field,
    FieldPoint,
    crossing_grid,
    divide_trim_edge,
    orient_division,
    trim_grid,
)

__all__ = [
    "Field",
    "FieldPoint",
    "crossing_grid",
    "divide_trim_edge",
    "orient_division",
    "trim_grid",
]
