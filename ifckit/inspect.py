# This file was generated with the assistance of an AI coding tool.
"""ifckit.inspect — gestructureerd rapport per ontwerpfase.

``report(model, stage)`` levert een JSON-serialiseerbaar :class:`ModelReport`.
Metingen zijn genormaliseerd naar SI-eenheden (oppervlak in m², inhoud in m³,
begrenzing in m), ongeacht de bestandseenheid van het model.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

try:
    from shapely.geometry import Point

    _SHAPELY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SHAPELY_AVAILABLE = False

_STAGES = ("S0", "S1", "S2")


@dataclass
class ModelReport:
    """Gestructureerd inspectierapport.

    Attributes:
        stage: Ontwerpfase (``"S0"``/``"S1"``/``"S2"``).
        model_unit: De bestandseenheid van het model (``METRE``/``MILLIMETRE``).
        spaces: Per-ruimte dicts (naam, oppervlak, inhoud, begrenzing, nabuurschap, ...).
        elements: Inventaris van elementen per type.
        warnings: Signalen gevonden in deze fase.
    """

    stage: str
    model_unit: str = "METRE"
    spaces: list[dict] = field(default_factory=list)
    elements: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict."""
        return asdict(self)

    def as_json(self, indent: int = 2) -> str:
        """Return a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


def _shape(entity):
    """Return the ifcopenshell geometry of *entity*, or ``None`` on failure."""
    import ifcopenshell.geom

    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    try:
        return ifcopenshell.geom.create_shape(settings, entity)
    except Exception:
        return None


def _measures(shape):
    """Return ``(area_m2, volume_m3, bounds_m)`` for a shape (SI-metres)."""
    import ifcopenshell.util.shape

    geometry = shape.geometry
    area = ifcopenshell.util.shape.get_footprint_area(geometry)
    volume = ifcopenshell.util.shape.get_volume(geometry)
    verts = geometry.verts
    xs = verts[0::3]
    ys = verts[1::3]
    zs = verts[2::3]
    bounds = {
        "x_min": min(xs),
        "x_max": max(xs),
        "y_min": min(ys),
        "y_max": max(ys),
        "z_min": min(zs),
        "z_max": max(zs),
    }
    return area, volume, bounds


def _centroids(model, ifc_class):
    """Return ``(cx, cy)`` 2D-centroids of all ``ifc_class`` entities (SI-metres)."""
    result = []
    for entity in model.ifc_file.by_type(ifc_class):
        shape = _shape(entity)
        if shape is None:
            continue
        verts = shape.geometry.verts
        xs = verts[0::3]
        ys = verts[1::3]
        result.append((sum(xs) / len(xs), sum(ys) / len(ys)))
    return result


def _hull(shape):
    """2D convex hull (shapely Polygon) of *shape*'s XY vertices, or ``None``."""
    if not _SHAPELY_AVAILABLE:
        return None
    from shapely.geometry import MultiPoint

    verts = shape.geometry.verts
    pts = [(verts[i], verts[i + 1]) for i in range(0, len(verts), 3)]
    if len(pts) < 3:
        return None
    return MultiPoint(pts).convex_hull


def _spaces(model):
    """Return ``(spaces, hulls)``: S0-info per ruimte plus parallelle footprints."""
    from ifckit.spatial.derive import space_adjacency

    adjacency = space_adjacency(model)
    gid_name = {gid: attrs["name"] for gid, attrs in adjacency.nodes().items()}

    door_centroids = _centroids(model, "IfcDoor")

    spaces, hulls = [], []
    for space in model.ifc_file.by_type("IfcSpace"):
        shape = _shape(space)
        if shape is None:
            area = volume = None
            bounds = None
            hull = None
        else:
            area, volume, bounds = _measures(shape)
            hull = _hull(shape)
        adjacent = sorted(
            n for n in (gid_name.get(nb) for nb in adjacency.neighbors(space.GlobalId)) if n
        )
        spaces.append(
            {
                "name": getattr(space, "Name", None) or "",
                "long_name": getattr(space, "LongName", None) or "",
                "global_id": space.GlobalId,
                "area": area,
                "volume": volume,
                "bounds": bounds,
                "adjacent": adjacent,
                "doors": 0,
            }
        )
        hulls.append(hull)

    if _SHAPELY_AVAILABLE:
        for i, hull in enumerate(hulls):
            if hull is None:
                continue
            spaces[i]["doors"] = sum(
                1 for (cx, cy) in door_centroids if hull.contains(Point(cx, cy))
            )
    return spaces, hulls


def _inventory(model):
    """Tel elementen per type."""
    counts = {}
    for ifc_class in ("IfcWall", "IfcSlab", "IfcDoor", "IfcWindow", "IfcOpeningElement"):
        counts[ifc_class[3:]] = len(model.ifc_file.by_type(ifc_class))
    return counts


def _wall_analysis(model, elements, warnings):
    """S1: wand-connectiviteit en gaten."""
    from ifckit.spatial.derive import wall_graph

    graph = wall_graph(model)
    isolated = [gid for gid in graph.nodes() if graph.degree(gid) == 0]
    elements["wall_components"] = len(graph.connected_components())
    elements["isolated_walls"] = len(isolated)
    if isolated:
        warnings.append(f"{len(isolated)} wand(en) zonder aansluiting (gat)")


def _opening_analysis(model, spaces, hulls, warnings):
    """S2: opening↔ruimte-koppeling."""
    opening_centroids = _centroids(model, "IfcOpeningElement")
    contained = 0
    for i, hull in enumerate(hulls):
        count = 0
        if hull is not None and _SHAPELY_AVAILABLE:
            count = sum(1 for (cx, cy) in opening_centroids if hull.contains(Point(cx, cy)))
        spaces[i]["openings"] = count
        contained += count
    if len(opening_centroids) > contained:
        warnings.append(
            f"{len(opening_centroids) - contained} opening(en) vallen buiten elke ruimte"
        )


def report(model, stage: str = "S0") -> ModelReport:
    """Bouw een gestructureerd rapport voor een ontwerpfase.

    Args:
        model: Een ``IfcModel``.
        stage: ``"S0"`` (ruimten), ``"S1"`` (structuur) of ``"S2"`` (openingen).
    """
    if stage not in _STAGES:
        raise ValueError(f"onbekende fase {stage!r}; verwacht een van {_STAGES}")

    spaces, hulls = _spaces(model)
    elements = _inventory(model)
    warnings: list[str] = []

    if stage == "S1":
        _wall_analysis(model, elements, warnings)
    elif stage == "S2":
        _opening_analysis(model, spaces, hulls, warnings)

    model_unit = getattr(getattr(model, "unit", None), "name", "UNKNOWN")
    return ModelReport(
        stage=stage,
        model_unit=model_unit,
        spaces=spaces,
        elements=elements,
        warnings=warnings,
    )
