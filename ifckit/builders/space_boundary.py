# This file was generated with the assistance of an AI coding tool.
"""2e-niveau space boundaries bij deuren: maakt ``door``-kanten realiseerbaar.

Bepaalt via de deurpositie welke ruimten (zelfde bouwlaag) de deuropening
delen en legt dat vast als ``IfcRelSpaceBoundary2ndLevel``-paar (VIRTUAL,
INTERNAL, onderling gekoppeld). Zo ziet ``space_adjacency`` de doorgang als
``kind="door"`` en werkt de access-graaf op gebouwde modellen.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.guid
import ifcopenshell.util.placement as placement_util
import ifcopenshell.util.unit as unit_util

try:
    from shapely.geometry import Point, Polygon

    _SHAPELY_AVAILABLE = True
except ImportError:
    _SHAPELY_AVAILABLE = False

from ifckit.spatial.derive import space_footprint_points


def _door_center(door_entity) -> tuple[float, float] | None:
    """Wereld-XY midden van de deur (oorsprong + halve breedte langs X-as)."""
    placement = getattr(door_entity, "ObjectPlacement", None)
    if placement is None:
        return None
    try:
        m = placement_util.get_local_placement(placement)
    except Exception:
        return None
    w = float(getattr(door_entity, "OverallWidth", 0.0) or 0.0)
    xx, xy = float(m[0, 0]), float(m[1, 0])
    norm = (xx * xx + xy * xy) ** 0.5
    if norm <= 0:
        return None
    cx = float(m[0, 3]) + xx / norm * w / 2.0
    cy = float(m[1, 3]) + xy / norm * w / 2.0
    return (cx, cy)


def _storey_spaces(storey_entity) -> list:
    """Alle ``IfcSpace``-entiteiten geaggregeerd onder een bouwlaag."""
    out = []
    for rel in getattr(storey_entity, "IsDecomposedBy", None) or []:
        for obj in getattr(rel, "RelatedObjects", None) or []:
            if obj.is_a("IfcSpace"):
                out.append(obj)
    return out


def _make_boundary(ifc_file, space, door_entity, internal, counterpart=None):
    """Maak één ``IfcRelSpaceBoundary2ndLevel`` (VIRTUAL) voor een deurpassage."""
    kwargs = dict(
        GlobalId=ifcopenshell.guid.new(),
        Name="IfcKit door passage",
        RelatingSpace=space,
        RelatedBuildingElement=door_entity,
        PhysicalOrVirtualBoundary="VIRTUAL",
        InternalOrExternalBoundary="INTERNAL" if internal else "EXTERNAL",
    )
    if counterpart is not None:
        kwargs["CorrespondingBoundary"] = counterpart
    return ifc_file.create_entity("IfcRelSpaceBoundary2ndLevel", **kwargs)


def add_door_space_boundaries(ifc_file, door_entity, storey_entity, tol=0.25):
    """Genereer 2e-niveau VIRTUAL space boundaries voor een deur.

    Args:
        ifc_file:     Open ifcopenshell file.
        door_entity:  De geplaatste ``IfcDoor``.
        storey_entity: De ``IfcBuildingStorey`` met de aanliggende ruimten.
        tol:          Match-tolerantie in SI-meters (deur-midden tot ruimte-grens).

    Returns:
        Lijst met aangemaakte boundaries: twee gekoppelde (INTERNAL) bij een
        binnendeur, één (EXTERNAL) bij een buitendeur, leeg bij geen match
        of zonder shapely.
    """
    if not _SHAPELY_AVAILABLE:
        return []
    center = _door_center(door_entity)
    if center is None or storey_entity is None:
        return []
    scale = unit_util.calculate_unit_scale(ifc_file)
    tol_p = tol / scale if scale else tol
    pt = Point(center)
    matches = []
    for space in _storey_spaces(storey_entity):
        pts = space_footprint_points(space)
        if not pts or len(pts) < 3:
            continue
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        d = poly.boundary.distance(pt)
        if d <= tol_p:
            matches.append((d, space))
    matches.sort(key=lambda t: (t[0], t[1].GlobalId))
    if len(matches) >= 2:
        (_, a), (_, b) = matches[:2]
        first, second = (a, b) if a.GlobalId <= b.GlobalId else (b, a)
        sb1 = _make_boundary(ifc_file, first, door_entity, internal=True)
        sb2 = _make_boundary(ifc_file, second, door_entity, internal=True, counterpart=sb1)
        sb1.CorrespondingBoundary = sb2
        return [sb1, sb2]
    if len(matches) == 1:
        return [_make_boundary(ifc_file, matches[0][1], door_entity, internal=False)]
    return []
