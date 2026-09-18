# This file was generated with the assistance of an AI coding tool.
"""ifckit.render — headless snapshots van een model.

``snapshot(model, stage, views)`` levert een :class:`Snapshot` met SVG's per
view. De camera is deterministisch: de planview snijdt het model op de
hoogte-midden van zijn bounding box, gecentreerd in XY.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ifckit.draw import generate_svg

_VIEWS = ("plan",)
_DRAWING_NAME = "__ifckit_plan__"


@dataclass
class Snapshot:
    """Set van headless views van een model.

    Attributes:
        svgs: view-naam → SVG-bytes.
        pngs: view-naam → PNG-bytes (leeg; rasterisatie is een doorgroei).
    """

    svgs: dict[str, bytes] = field(default_factory=dict)
    pngs: dict[str, bytes] = field(default_factory=dict)


def _unit_scale(model) -> float:
    """Length-unit scale: vermenigvuldig document-eenheden om SI-meters te krijgen."""
    import ifcopenshell.util.unit

    return ifcopenshell.util.unit.calculate_unit_scale(model.ifc_file)


def _model_bbox(model) -> tuple[float, float, float, float, float, float] | None:
    """3D bounding box (xmin, ymin, zmin, xmax, ymax, zmax) in SI-meters."""
    import ifcopenshell.geom

    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for ifc_class in ("IfcSpace", "IfcWall", "IfcSlab"):
        for entity in model.ifc_file.by_type(ifc_class):
            try:
                shape = ifcopenshell.geom.create_shape(settings, entity)
                verts = shape.geometry.verts  # type: ignore[union-attr]
                xs += verts[0::3]
                ys += verts[1::3]
                zs += verts[2::3]
            except Exception:
                continue
    if not xs:
        return None
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def _plan_origin(model) -> tuple[float, float, float]:
    """Deterministische planview-oorsprong (bestandseenheden): bbox-centrum."""
    bbox = _model_bbox(model)
    if bbox is None:
        return (0.0, 0.0, 0.0)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    cz = (zmin + zmax) / 2.0
    scale = _unit_scale(model)
    return (cx / scale, cy / scale, cz / scale)


def _ensure_plan_drawing(model):
    """Gebruik een bestaande planview-annotation, of maak er een deterministische aan."""
    for ann in model.ifc_file.by_type("IfcAnnotation"):
        if (
            getattr(ann, "ObjectType", None) == "DRAWING"
            and getattr(ann, "Name", None) == _DRAWING_NAME
        ):
            return ann
    cx, cy, cz = _plan_origin(model)
    return model.add_drawing(_DRAWING_NAME, position=(cx, cy, cz))


def _plan_svg(model, stage: str) -> bytes:
    ann = _ensure_plan_drawing(model)
    return generate_svg(model, drawing_guid=ann.GlobalId)


def snapshot(model, stage: str = "S0", views: tuple[str, ...] = ("plan",)) -> Snapshot:
    """Maak headless SVG-snapshots van *model*.

    Args:
        model: Een ``IfcModel``.
        stage: Ontwerpfase (``"S0"``/``"S1"``/``"S2"``); gereserveerd voor
            per-fase views.
        views: Te produceren views; nu alleen ``"plan"``.
    """
    result = Snapshot()
    for view in views:
        if view == "plan":
            result.svgs["plan"] = _plan_svg(model, stage)
        else:
            raise ValueError(f"onbekende view {view!r}; verwacht een van {_VIEWS}")
    return result
