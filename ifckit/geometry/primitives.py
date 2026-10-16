# This file was generated with the assistance of an AI coding tool.
"""ifckit.geometry.primitives — re-export facade over geometrykit.

The value types (Vec, Plane, Line, Arc, Polyline and reports) live in
geometrykit, whose implementation is byte-identical to the code this
module carried (promotion heritage, same copyright holder). Import
through ``ifckit.geometry`` unchanged; the objects are the same ones.
"""

from geometrykit.geometry.primitives import (
    Arc,
    ArcReport,
    Line,
    LineReport,
    Plane,
    PlaneReport,
    Polyline,
    Vec,
    VecReport,
    _copy_with_fresh_meta,  # noqa: F401  (re-exported for ifckit internals)
    _fmt_num,  # noqa: F401  (re-exported for ifckit internals)
    _new_id,  # noqa: F401  (re-exported for ifckit internals)
    _polygon_normal,  # noqa: F401  (re-exported for ifckit internals)
    _projected_area,  # noqa: F401  (re-exported for ifckit internals)
    _short_id,  # noqa: F401  (re-exported for ifckit internals)
    _signed_area,  # noqa: F401  (re-exported for ifckit internals)
)

__all__ = [
    "Arc",
    "ArcReport",
    "Line",
    "LineReport",
    "Plane",
    "PlaneReport",
    "Polyline",
    "Vec",
    "VecReport",
]
