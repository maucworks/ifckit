# This file was generated with the assistance of an AI coding tool.
"""ifckit.geometry.patterns — re-export facade over geometrykit.

Pattern cells live in geometrykit, whose implementation matches the
code this module carried except for one deliberate factoring: the
seam-transfer helper projects with the kernel (``Surface.project``)
instead of requiring OCC (``occ_project_point``). Same intent, no OCC
dependency. Import through ``ifckit.geometry`` unchanged.
"""

from geometrykit.geometry.patterns import (
    DiamondPattern,
    HexPattern,
    anglebox_cells,
    brick_cells,
    diamond_cells,
    hankin_cells,
    hex_cells,
    quad_cells,
    triangle_cells,
    truchet_cells,
    wave_cells,
)

__all__ = [
    "DiamondPattern",
    "HexPattern",
    "anglebox_cells",
    "brick_cells",
    "diamond_cells",
    "hankin_cells",
    "hex_cells",
    "quad_cells",
    "triangle_cells",
    "truchet_cells",
    "wave_cells",
]
