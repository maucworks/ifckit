# This file was generated with the assistance of an AI coding tool.
"""ifckit.geometry.curve — re-export facade over geometrykit.

Curves live in geometrykit. Deliberate behavior deltas, all covered
by the suite:

- Interpolation (``from_points``) and joining (``assemble``) run on
  the kernel (NURBS Book A9.1/A9.2, chord parameters) instead of OCC
  (``GeomAPI_Interpolate``, ``CompCurveToBSplineCurve``). Curves pass
  through the same points; knot vectors and poles follow the kernel
  convention. The OCC oracle path lives in the test suite.
- New API on top: ``plane_roots`` (bisect plane crossings, no OCC).
- Basis derivatives follow the one-sided clamped-edge convention.

``divide`` (arc-length), IFC serialisation and the ``occ_*`` helpers
keep their behavior. Import through ``ifckit.geometry`` unchanged.
"""

from geometrykit.geometry.curve import (
    Curve,
    CurveReport,
)

__all__ = [
    "Curve",
    "CurveReport",
]
