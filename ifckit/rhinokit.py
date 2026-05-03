"""
ifckit.rhino_kit
================

Convert Rhino geometry to ifckit geometry types.

Used in Grasshopper scripts to convert Rhino curves to ifckit pending elements.

Usage::

    from ifckit import rhinnokit as rk

    # Polyline → list of Vec
    vecs = rk.polyline_to_vecs(rhino_curve)

    # Rhino Line → ifckit Line
    line = rk.line_to_line(rhino_line)

    # Rhino Arc → ifckit Arc
    arc = rk.arc_to_arc(rhino_arc)
"""

from __future__ import annotations

from typing import Any, List, Optional

from ifckit.geometry import Arc, Line, Path, Vec
from ifckit.paper import iso_a_size_mm

try:
    import Rhino
    import Rhino.DocObjects
    import Rhino.Geometry

    _RHINO_AVAILABLE = True
except ImportError:
    _RHINO_AVAILABLE = False


def _require_rhino(fn_name: str) -> None:
    if not _RHINO_AVAILABLE:
        raise ImportError(
            f"ifckit.rhinokit.{fn_name}() requires Rhino — run inside Rhino 8 / Grasshopper."
        )


def pt_to_vec(pt: Any) -> Vec:
    """Rhino Point3d → Vec."""
    return Vec(pt.X, pt.Y, pt.Z)


def vec_to_pt3d(vec: Vec) -> Any:
    """Vec → Rhino Point3d."""
    _require_rhino("vec_to_pt3d")
    return Rhino.Geometry.Point3d(vec.x, vec.y, vec.z)


def pts_to_vecs(pts: Any) -> List[Vec]:
    """List of Rhino Point3d objects → list of Vec.

    Handles both open and closed point lists. If the last point equals
    the first (within tolerance), it's treated as closed and the
    duplicate endpoint is removed.
    """
    vecs = [pt_to_vec(p) for p in pts]
    if len(vecs) > 1:
        first, last = vecs[0], vecs[-1]
        if abs(first.x - last.x) < 1e-6 and abs(first.y - last.y) < 1e-6:
            vecs = vecs[:-1]
    return vecs


def polyline_to_footprint(crv: Any) -> List[Vec]:
    """Alias for polyline_to_vecs."""
    return polyline_to_vecs(crv)


def polyline_to_vecs(crv: Any) -> List[Vec]:
    """Rhino curve (Polyline/PolylineCurve) → list of Vec.

    Handles both open and closed polylines. If the polyline's last point
    equals the first (within tolerance), it's treated as closed and the
    duplicate endpoint is removed.
    """
    pl = crv.ToPolyline() if hasattr(crv, "ToPolyline") else crv
    pts = [pt_to_vec(p) for p in pl]

    if len(pts) > 1:
        first, last = pts[0], pts[-1]
        if abs(first.x - last.x) < 1e-6 and abs(first.y - last.y) < 1e-6:
            pts = pts[:-1]

    return pts


def line_to_line(rhino_line: Any) -> Line:
    """Rhino LineCurve or Line → ifckit Line."""
    if hasattr(rhino_line, "PointAtStart"):
        # LineCurve
        pt_a = rhino_line.PointAtStart
        pt_b = rhino_line.PointAtEnd
    else:
        # Rhino.Geometry.Line struct
        pt_a = rhino_line.From
        pt_b = rhino_line.To
    return Line(pt_to_vec(pt_a), pt_to_vec(pt_b))


def arc_to_arc(rhino_arc: Any) -> Arc:
    """Rhino Arc or ArcCurve → ifckit Arc.

    Handles both Rhino Arc (primitive) and ArcCurve (geometry with curve methods).
    Uses .Arc property if available (ArcCurve), otherwise assumes it's already an Arc.

    """
    try:
        arc = rhino_arc.Arc
    except AttributeError:
        arc = rhino_arc

    rh_center = arc.Center
    rh_start = arc.StartPoint
    rh_end = arc.EndPoint  # noqa: F841
    rh_plane = arc.Plane
    rh_normal = rh_plane.Normal
    angle_rad = arc.Angle  # Rhino Arc.Angle is already in radians

    normal = Vec(rh_normal.X, rh_normal.Y, rh_normal.Z)

    return Arc(
        center=pt_to_vec(rh_center),
        normal=normal,
        start=pt_to_vec(rh_start),
        angle=angle_rad,
    )


def curve_to_segments(crv: Any) -> List[Any]:
    """Rhino curve → list of curve segments.

    For polycurves, explodes into individual segments.
    For single curves, returns a list with one element.
    """
    if hasattr(crv, "Explode"):
        segments = crv.Explode()
        if segments and len(segments) > 1:
            return list(segments)

    return [crv]


def curves_to_path(curves: Any) -> Path:
    """Convert a Rhino curve or iterable of Rhino curves into an ifckit Path.

    Handles single curves, lists/tuples of curves, and polycurves (exploded).
    Each segment is converted to an ifckit Line or Arc and appended to a Path.
    """
    # Normalize to an iterable
    if curves is None:
        return Path()
    if not hasattr(curves, "__iter__") or isinstance(curves, (str, bytes)):
        curves = [curves]

    p = Path()
    for crv in curves:
        if crv is None:
            continue
        segs = curve_to_segments(crv)
        for s in segs:
            # Rhino ArcCurve has Radius attribute; LineCurve does not
            if hasattr(s, "Radius") and getattr(s, "Radius", 0) > 0:
                arc = arc_to_arc(s)
                p.add_arc(arc.center, arc.normal, arc.start, arc.angle)
            else:
                line = line_to_line(s)
                p.add_line(line.start, line.end)

    return p


def path_to_rhino_curve(geom: Any) -> Any:
    """Convert a Line, Arc, Path, or Profile to a Rhino PolyCurve.

    Accepts any of:
    - ``ifckit.geometry.Line``    — single straight segment
    - ``ifckit.geometry.Arc``     — single circular arc
    - ``ifckit.geometry.Path``    — ordered sequence of Line/Arc segments
    - ``ifckit.profiles.Profile`` — profile outline via ``to_path()``

    Returns a ``Rhino.Geometry.PolyCurve`` in all cases (even for a single
    segment).  All coordinates are taken as-is — no unit conversion.
    """
    _require_rhino("path_to_rhino_curve")

    from ifckit.geometry import Arc, Line, Path
    from ifckit.profiles.base import Profile

    if isinstance(geom, Profile):
        geom = geom.to_path()

    if isinstance(geom, Line):
        segments = [geom]
    elif isinstance(geom, Arc):
        segments = [geom]
    elif isinstance(geom, Path):
        segments = geom.segments
    else:
        raise TypeError(
            f"path_to_rhino_curve() expects Line, Arc or Path, got {type(geom).__name__}"
        )

    rg = Rhino.Geometry
    polycurve = rg.PolyCurve()

    for seg in segments:
        if isinstance(seg, Line):
            start = rg.Point3d(seg.start.x, seg.start.y, seg.start.z)
            end = rg.Point3d(seg.end.x, seg.end.y, seg.end.z)
            polycurve.Append(rg.LineCurve(start, end))

        elif isinstance(seg, Arc):
            center = rg.Point3d(seg.center.x, seg.center.y, seg.center.z)
            normal = rg.Vector3d(seg.normal.x, seg.normal.y, seg.normal.z)
            radial = seg.start - seg.center
            x_axis = rg.Vector3d(radial.x, radial.y, radial.z)
            plane = rg.Plane(center, x_axis, rg.Vector3d.CrossProduct(normal, x_axis))
            rhino_arc = rg.Arc(plane, seg.radius, seg.angle)
            polycurve.Append(rg.ArcCurve(rhino_arc))

    return polycurve


def profile_to_rhino_curve(profile: Any) -> Any:
    """Convert an ifckit Profile to a closed Rhino PolylineCurve in WorldXY.

    The profile cross-section points (2-D, in the profile's local plane) are
    placed at Z=0 around the world origin.  Rotation, offset and anchor
    transforms are already baked into ``get_profile_points()``.

    Args:
        profile: Any ifckit ``Profile`` subclass instance.

    Returns:
        ``Rhino.Geometry.PolylineCurve`` — a closed polygon in WorldXY.
    """
    _require_rhino("profile_to_rhino_curve")
    pts_2d = profile.get_profile_points()  # [(x, y), ...]
    pts_3d = [Rhino.Geometry.Point3d(x, y, 0.0) for x, y in pts_2d]
    pts_3d.append(pts_3d[0])  # close
    return Rhino.Geometry.PolylineCurve(pts_3d)


def ensure_layer(
    doc: Any,
    path: str,
    color: Optional[Any] = None,
    plot_weight: Optional[float] = None,
) -> int:
    """Ensure a layer exists in *doc*, creating it if necessary.

    Applies *color* and *plot_weight* on both create and update.

    Args:
        doc:         Rhino document (``RhinoDoc``).
        path:        Layer name or ``::``-separated hierarchy,
                     e.g. ``"Annotations::NoPlot"``.
        color:       ``System.Drawing.Color`` to set on the layer.
                     ``None`` leaves the colour unchanged on existing layers
                     and uses the Rhino default on new ones.
        plot_weight: Line width in mm for printing.  ``0.0`` = "No Print".
                     ``None`` leaves the value unchanged.

    Returns:
        Integer layer index of the (leaf) layer.

    Example::

        import System.Drawing
        from ifckit import rhinokit as rk
        import scriptcontext as sc

        idx = rk.ensure_layer(
            sc.doc,
            "Annotations::NoPlot",
            color=System.Drawing.Color.Magenta,
            plot_weight=0.0,
        )
    """
    import Rhino

    parts = path.split("::")
    for i, part in enumerate(parts):
        current_path = "::".join(parts[: i + 1])
        index = doc.Layers.FindByFullPath(current_path, -1)

        if index < 0:
            layer = Rhino.DocObjects.Layer()
            layer.Name = part
            if i > 0:
                parent_path = "::".join(parts[:i])
                parent_index = doc.Layers.FindByFullPath(parent_path, -1)
                if parent_index >= 0:
                    layer.ParentLayerId = doc.Layers[parent_index].Id
            if color is not None:
                layer.Color = color
            if plot_weight is not None:
                layer.PlotWeight = plot_weight
            index = doc.Layers.Add(layer)
            if index < 0:
                raise RuntimeError(f"Failed to create Rhino layer: {current_path!r}")
        else:
            layer = doc.Layers[index]
            changed = False
            if color is not None:
                layer.Color = color
                changed = True
            if plot_weight is not None:
                layer.PlotWeight = plot_weight
                changed = True
            if changed:
                layer.CommitChanges()

    return doc.Layers.FindByFullPath(path, -1)


def draw_paper_rectangle(
    doc: Any,
    plane: Any,
    layer: str,
    iso_a: int = 1,
    scale: float = 1.0,
    landscape: bool = False,
) -> Any:
    """Draw an ISO A-series paper rectangle on *plane* and add it to *doc*.

    The rectangle is centred on ``plane.Origin``.

    Args:
        doc:       Rhino document (``RhinoDoc``).
        plane:     Rhino ``Plane`` — defines position and orientation.
        layer:     Full layer path (``::``-separated).  Created if it does
                   not exist.
        iso_a:     ISO A paper size number (0–10).  Default ``1`` = A1.
        scale:     Scale factor applied to the paper size.  E.g. ``50`` for
                   a 1:50 drawing frame.  Default ``1.0``.
        landscape: If ``True``, swap width and height.  Default ``False``
                   (portrait).

    Returns:
        ``System.Guid`` of the added curve object.

    Example::

        import Rhino.Geometry as rg
        from ifckit import rhinokit as rk
        import scriptcontext as sc

        guid = rk.draw_paper_rectangle(
            sc.doc,
            plane=rg.Plane.WorldXY,
            layer="Annotations::NoPlot",
            iso_a=1,
            scale=50,
            landscape=True,
        )
    """
    import Rhino
    import Rhino.Geometry as rg

    if iso_a not in range(0, 11):
        raise ValueError(f"iso_a must be 0–10, got {iso_a!r}")

    w_mm, h_mm = iso_a_size_mm(iso_a, landscape=landscape)

    # Convert mm → Rhino document units then apply scale factor.
    uf = Rhino.RhinoMath.UnitScale(Rhino.UnitSystem.Millimeters, doc.ModelUnitSystem)
    w = w_mm * uf * scale
    h = h_mm * uf * scale

    # Build rectangle centred on plane.Origin.
    interval_x = rg.Interval(-w / 2.0, w / 2.0)
    interval_y = rg.Interval(-h / 2.0, h / 2.0)
    rect = rg.Rectangle3d(plane, interval_x, interval_y)
    curve = rect.ToNurbsCurve()

    layer_index = ensure_layer(doc, layer)

    attr = Rhino.DocObjects.ObjectAttributes()
    attr.LayerIndex = layer_index

    return doc.Objects.AddCurve(curve, attr)


# ---------------------------------------------------------------------------
# Dev reload helper
# ---------------------------------------------------------------------------


def reload_all(project_root: str | None = None) -> None:
    """
    Ensure *project_root* is on ``sys.path`` and reload all ifckit submodules
    in dependency order (leaves first, root last).

    Call this at the top of every Grasshopper Script node to pick up
    live code changes without restarting Rhino::

        import ifckit.rhinokit as rk
        rk.reload_all()          # or rk.reload_all(r'/path/to/ifckit')

    Parameters
    ----------
    project_root : str, optional
        Absolute path to the project root (the directory that contains the
        ``ifckit`` package).  Reads the ``IFCKIT_PATH`` environment variable
        first; falls back to ``/Users/Mauc/L140-py-ifckit`` if neither is set.
    """
    import importlib
    import os
    import sys

    _default = None
    root = project_root or os.environ.get("IFCKIT_PATH", _default)
    if root and root not in sys.path:
        sys.path.insert(0, root)

    _RELOAD_ORDER = [
        "ifckit.schema",
        "ifckit.geometry",
        "ifckit.elements",
        "ifckit.profiles.base",
        "ifckit.profiles.shapes",
        "ifckit.profiles.i_beam",
        "ifckit.profiles.l_beam",
        "ifckit.profiles.steel",
        "ifckit.profiles",
        "ifckit.builders._geom",
        "ifckit.builders.base",
        "ifckit.builders.extruded",
        "ifckit.builders.wall",
        "ifckit.builders.slab",
        "ifckit.builders.space",
        "ifckit.builders.beam_factory",
        "ifckit.builders.revolved_beam",
        "ifckit.builders.bridge",
        "ifckit.builders",
        "ifckit.rhinokit",
        "ifckit.preview",
        "ifckit.rhino_import",
        "ifckit.model",
        "ifckit.validator",
        "ifckit.json_build",
        "ifckit",
    ]

    for mod_name in _RELOAD_ORDER:
        mod = sys.modules.get(mod_name)
        if mod is not None:
            importlib.reload(mod)
        else:
            try:
                importlib.import_module(mod_name)
            except ImportError:
                pass  # optional submodule not installed
