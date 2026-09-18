# This file was generated with the assistance of an AI coding tool.
"""Leid ruimtelijke grafen af uit een IFC-model.

``space_adjacency`` bouwt de duale graaf (knopen = ruimten, kanten = gedeelde
grens), ``wall_graph`` de wand-connectiviteit. Beide werken op 2D-footprints in
SI-meters; ``shapely`` is optioneel voor de geometrische bewerkingen.
"""

from __future__ import annotations

try:
    from shapely.geometry import MultiPoint, Polygon
    from shapely.ops import unary_union

    _SHAPELY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SHAPELY_AVAILABLE = False

from ifckit.spatial.graph import Graph

_SHARED_BOUNDARY_TOL = 1e-6


def _require_shapely() -> None:
    if not _SHAPELY_AVAILABLE:
        raise ImportError(
            "ifckit.spatial geometry derivation requires shapely. "
            "Install it with: pip install shapely"
        )


def _unit_scale(model) -> float:
    """Length-unit scale: vermenigvuldig document-eenheden om SI-meters te krijgen."""
    import ifcopenshell.util.unit

    return ifcopenshell.util.unit.calculate_unit_scale(model.ifc_file)


def _space_id(space) -> str:
    return space.GlobalId


def _space_attrs(space) -> dict:
    return {
        "name": getattr(space, "Name", None) or "",
        "long_name": getattr(space, "LongName", None) or "",
        "global_id": space.GlobalId,
    }


def _space_footprint_points(space) -> list[tuple[float, float]] | None:
    """2D-footprintpunten van *space* uit zijn FootPrint-representatie."""
    rep = getattr(space, "Representation", None)
    if rep is None:
        return None
    for r in rep.Representations or []:
        if getattr(r, "RepresentationIdentifier", None) == "FootPrint":
            for item in r.Items:
                if item.is_a("IfcPolyline"):
                    return [(float(p.Coordinates[0]), float(p.Coordinates[1])) for p in item.Points]
    return None


def space_footprints(model) -> dict[str, "Polygon"]:
    """Breng elke ``IfcSpace`` in kaart op zijn 2D-footprintpolygoon (SI-meters).

    Nodes zijn gesleuteld op ``IfcSpace.GlobalId``. Ruimten zonder FootPrint-
    representatie worden overgeslagen. Gaat uit van footprints in een gedeeld
    2D-frame (zoals ifckit die zelf produceert).
    """
    _require_shapely()
    scale = _unit_scale(model)
    result: dict[str, "Polygon"] = {}
    for space in model.ifc_file.by_type("IfcSpace"):
        pts = _space_footprint_points(space)
        if not pts or len(pts) < 3:
            continue
        poly = Polygon([(x * scale, y * scale) for x, y in pts])
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty or poly.area <= 0:
            continue
        result[_space_id(space)] = poly
    return result


def _door_pairs(ifc_file) -> set[tuple[str, str]]:
    """Paar van ruimte-``GlobalId``s verbonden door een VIRTUELE 2e-niveau space boundary.

    Een virtuele boundary markeert een opening/passage (deur) tussen twee
    ruimten; een fysieke boundary is een gedeelde wand.
    """
    pairs: set[tuple[str, str]] = set()
    for sb in ifc_file.by_type("IfcRelSpaceBoundary2ndLevel"):
        rel = getattr(sb, "RelatingSpace", None)
        if rel is None or getattr(sb, "PhysicalOrVirtualBoundary", None) != "VIRTUAL":
            continue
        corr = getattr(sb, "CorrespondingBoundary", None)
        other = getattr(corr, "RelatingSpace", None) if corr is not None else None
        if other is None:
            continue
        a, b = sorted([rel.GlobalId, other.GlobalId])
        pairs.add((a, b))
    return pairs


def space_adjacency(model) -> Graph:
    """Bouw de duale graaf van ruimten uit een IFC-model.

    Twee ruimten zijn verbonden als hun footprints een grenssegment delen (lengte
    groter dan de tolerantie; alleen hoekcontact telt niet). De kant krijgt
    ``kind="wall"``, of ``kind="door"`` als een virtuele space boundary de twee
    ruimten als doorgang verbindt.
    """
    _require_shapely()
    footprints = space_footprints(model)
    graph = Graph()
    for space in model.ifc_file.by_type("IfcSpace"):
        gid = _space_id(space)
        if gid in footprints:
            graph.add_node(gid, **_space_attrs(space))

    doors = _door_pairs(model.ifc_file)
    ids = list(footprints.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            shared = footprints[a].boundary.intersection(footprints[b].boundary)
            if shared.length > _SHARED_BOUNDARY_TOL:
                key = tuple(sorted([a, b]))
                kind = "door" if key in doors else "wall"
                graph.add_edge(a, b, kind=kind)
    return graph


def perimeter_spaces(footprints: dict[str, "Polygon"]) -> set[str]:
    """Return de set ruimte-ids met een buitengevel (grens aan de envelop).

    Een ruimte heeft een buitengevel als een deel van zijn footprint op de
    buitenrand van de unie van alle footprints ligt.
    """
    _require_shapely()
    if not footprints:
        return set()
    union = unary_union(list(footprints.values()))
    exterior = union.exterior
    result: set[str] = set()
    for gid, poly in footprints.items():
        inter = poly.exterior.intersection(exterior)
        if inter.length > _SHARED_BOUNDARY_TOL:
            result.add(gid)
    return result


def _wall_footprint(model, settings) -> dict[str, "Polygon"]:
    """2D-footprint per ``IfcWall`` (convex hull van zijn driehoeksvertices in XY)."""
    import ifcopenshell.geom

    result: dict[str, "Polygon"] = {}
    for wall in model.ifc_file.by_type("IfcWall"):
        try:
            shape = ifcopenshell.geom.create_shape(settings, wall)
            verts = shape.geometry.verts  # type: ignore[union-attr]
            pts = [(verts[i], verts[i + 1]) for i in range(0, len(verts), 3)]
            if len(pts) < 3:
                continue
            result[wall.GlobalId] = MultiPoint(pts).convex_hull
        except Exception:
            continue
    return result


def wall_graph(model) -> Graph:
    """Bouw de wand-connectiviteitsgraaf uit een IFC-model.

    Twee wanden zijn verbonden als hun 2D-footprints elkaar raken of overlappen.
    De footprint is de convex hull van de (wereldcoördinaten) driehoeksvertices
    van elke wand.
    """
    _require_shapely()
    import ifcopenshell.geom

    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    footprints = _wall_footprint(model, settings)

    graph = Graph()
    for wall in model.ifc_file.by_type("IfcWall"):
        gid = wall.GlobalId
        if gid in footprints:
            graph.add_node(gid, name=getattr(wall, "Name", None) or "", global_id=gid)

    ids = list(footprints.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            if footprints[a].intersects(footprints[b]):
                graph.add_edge(a, b)
    return graph
