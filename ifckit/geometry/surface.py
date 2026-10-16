# This file was generated with the assistance of an AI coding tool.
"""ifckit.geometry.surface — re-export facade over geometrykit.

Surfaces live in geometrykit. Two deliberate behavior deltas come
with the move (both measured, both covered by the suite):

- Evaluation (``point_at``) and the new first-order methods
  (``tangents_at``, ``normal_at``, ``project``) run on the kernel
  (mirror or the ``_rust`` accelerator, bit-identical by harness)
  instead of OCC. The ``occ_*`` oracle functions stay available
  unchanged for tests and OCC-backed paths.
- ``Surface.patch`` with ``fill=None`` (the default): the C0
  four-curve case now takes the position-only P-0 Coons blend
  instead of OCC MakeFilling; G1 edges keep the OCCT twin. The
  ``fill="coons"|"energy"`` kernel routes are new API on top.

``to_mesh_dict``/``preview`` (OCC tessellation), IFC serialisation
and the ``occ_*`` builders are unchanged. Import through
``ifckit.geometry`` unchanged.
"""

from geometrykit.geometry.surface import (
    Surface,
    SurfaceReport,
    _build_occ_curve,  # noqa: F401  (re-exported for ifckit internals)
    _build_occ_edge,  # noqa: F401  (re-exported for ifckit internals)
    _build_occ_surface,  # noqa: F401  (re-exported for ifckit internals)
    _curve_from_occ_bspline,  # noqa: F401  (re-exported for ifckit internals)
    occ_eval_point,  # noqa: F401  (re-exported for ifckit internals)
    occ_eval_tangents,  # noqa: F401  (re-exported for ifckit internals)
    occ_face_bounds,  # noqa: F401  (re-exported for ifckit internals)
    occ_intersect_plane,  # noqa: F401  (re-exported for ifckit internals)
    occ_normal_at,  # noqa: F401  (re-exported for ifckit internals)
    occ_project_point,  # noqa: F401  (re-exported for ifckit internals)
    occ_tessellate,  # noqa: F401  (re-exported for ifckit internals)
    occ_tessellate_to_ifc,  # noqa: F401  (re-exported for ifckit internals)
    occ_trim_loops,  # noqa: F401  (re-exported for ifckit internals)
    require_occ,  # noqa: F401  (re-exported for ifckit internals)
)

__all__ = [
    "Surface",
    "SurfaceReport",
]
