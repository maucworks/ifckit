# This file was generated with the assistance of an AI coding tool.
"""ifckit.geometry.biarc — re-export facade over geometrykit.

Biarc fitting lives in geometrykit, whose implementation is
byte-identical to the code this module carried (promotion heritage,
same copyright holder). Import through ``ifckit.geometry`` unchanged.
"""

from geometrykit.geometry.biarc import (
    _dist_to_line,  # noqa: F401  (re-exported for ifckit internals)
    _perp_in_plane,  # noqa: F401  (re-exported for ifckit internals)
    _signed_angle,  # noqa: F401  (re-exported for ifckit internals)
    build_arc_from_start_tangent,
    estimate_deviation,
    fit_biarcs,
    simplify_biarcs,
    solve_biarc,
)

__all__ = [
    "build_arc_from_start_tangent",
    "estimate_deviation",
    "fit_biarcs",
    "simplify_biarcs",
    "solve_biarc",
]
