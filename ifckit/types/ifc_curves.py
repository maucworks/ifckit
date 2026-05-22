"""
ifckit.types.ifc_curves — Convert footprint geometry curves to IFC entities.

Each function takes an ``ifcopenshell.file`` and returns ready-to-use
IFC entity instances (``IfcPolyline``, ``IfcCompositeCurve``).  The
results are intended to be wrapped in an ``IfcGeometricCurveSet`` and
placed into an ``IfcShapeRepresentation`` with
``RepresentationIdentifier="FootPrint"`` and
``RepresentationType="GeometricCurveSet"`` (per IFC4 spec template
`FootPrint GeomSet Geometry`).
"""

from __future__ import annotations

from typing import List, Union

import ifcopenshell

from ifckit.builders._geom import pt3
from ifckit.geometry import Arc, Line

_CURVE = Union[Line, Arc]


def curve_to_ifc(
    ifc_file: ifcopenshell.file,
    curve: _CURVE,
    arc_samples: int = 8,
) -> ifcopenshell.entity_instance:
    """Convert a single ``Line`` or ``Arc`` to an IFC curve entity.

    Args:
        ifc_file:     Open IFC file.
        curve:        A ``Line`` or ``Arc`` instance.
        arc_samples:  Only used for ``Arc`` — number of segments to
                      sample the arc into when creating an ``IfcPolyline``.

    Returns:
        ``IfcPolyline`` for both types.  Arcs are tessellated into
        polylines (sufficient for plan-view symbol rendering).
    """
    if isinstance(curve, Arc):
        pts = [pt3(ifc_file, p.x, p.y, p.z) for p in curve.sample(90.0 / (arc_samples - 1))]
    else:
        pts = [
            pt3(ifc_file, curve.start.x, curve.start.y, curve.start.z),
            pt3(ifc_file, curve.end.x, curve.end.y, curve.end.z),
        ]
    return ifc_file.create_entity("IfcPolyline", Points=pts)


def curves_to_ifc(
    ifc_file: ifcopenshell.file,
    curves: List[_CURVE],
    arc_samples: int = 8,
) -> List[ifcopenshell.entity_instance]:
    """Convert a list of ``Line`` / ``Arc`` to IFC curve entities."""
    return [curve_to_ifc(ifc_file, c, arc_samples) for c in curves]
