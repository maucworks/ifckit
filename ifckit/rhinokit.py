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

from ifckit.geometry import Arc, Curve, Line, Path, Surface, Vec
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


def _expand_knots(knots: Any, multiplicities: Any) -> list:
    """Expand compact (knot, mult) pairs into a full knot vector."""
    out: list = []
    for k, m in zip(knots, multiplicities):
        out.extend([float(k)] * m)
    return out


def _compact_knots(full_knots: list) -> tuple:
    """Compress a full knot vector to (unique_knots, multiplicities)."""
    if not full_knots:
        return [], []
    unique = [full_knots[0]]
    mults = [1]
    for k in full_knots[1:]:
        if abs(k - unique[-1]) < 1e-12:
            mults[-1] += 1
        else:
            unique.append(float(k))
            mults.append(1)
    return unique, mults


def _is_rhino_nurbs(obj: Any) -> bool:
    """True if *obj* is a Rhino NurbsCurve (not LineCurve, ArcCurve, etc.)."""
    if not _RHINO_AVAILABLE:
        return False
    return isinstance(obj, Rhino.Geometry.NurbsCurve)


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
    Line and Arc segments are converted directly.  NurbsCurve segments are
    auto‑converted via bi‑arc fitting (``Curve.to_biarcs()``).
    """
    if curves is None:
        return Path()
    if not hasattr(curves, "__iter__") or isinstance(curves, (str, bytes)):
        curves = [curves]

    p = Path()
    for crv in curves:
        if crv is None:
            continue

        if _is_rhino_nurbs(crv):
            curve = rhino_nurbs_to_curve(crv)
            biarc_path = curve.to_biarcs()
            p._segments.extend(biarc_path._segments)
            continue

        segs = curve_to_segments(crv)
        for s in segs:
            if hasattr(s, "Radius") and getattr(s, "Radius", 0) > 0:
                arc = arc_to_arc(s)
                p.add_arc(arc.center, arc.normal, arc.start, arc.angle)
            elif _is_rhino_nurbs(s):
                curve = rhino_nurbs_to_curve(s)
                biarc_path = curve.to_biarcs()
                p._segments.extend(biarc_path._segments)
            else:
                line = line_to_line(s)
                p.add_line(line.start, line.end)

    return p


def rhino_plane_to_plane(rh_plane: Any) -> Any:
    """Convert a Rhino Plane to an ifckit Plane.

    Args:
        rh_plane: ``Rhino.Geometry.Plane``

    Returns:
        ``ifckit.geometry.Plane``
    """
    _require_rhino("rhino_plane_to_plane")
    from ifckit.geometry import Plane, Vec

    origin = Vec(rh_plane.Origin.X, rh_plane.Origin.Y, rh_plane.Origin.Z)
    x_axis = Vec(rh_plane.XAxis.X, rh_plane.XAxis.Y, rh_plane.XAxis.Z)
    y_axis = Vec(rh_plane.YAxis.X, rh_plane.YAxis.Y, rh_plane.YAxis.Z)
    return Plane(origin, x_axis, y_axis)


def rhino_nurbs_to_curve(rh_nurbs: Any) -> Curve:
    """Convert a Rhino NurbsCurve to an ifckit Curve.

    Handles the Rhino knot‑vector convention (``n + d − 1`` knots)
    by prepending / appending one superfluous knot at each clamped end
    to produce the standard ``n + d + 1`` knot vector expected by IFC.

    Args:
        rh_nurbs: ``Rhino.Geometry.NurbsCurve``

    Returns:
        ``ifckit.geometry.Curve``
    """
    _require_rhino("rhino_nurbs_to_curve")

    degree = rh_nurbs.Degree
    n = rh_nurbs.Points.Count
    rational = rh_nurbs.IsRational

    control_points = []
    weights: list = []
    for i in range(n):
        loc = rh_nurbs.Points[i].Location
        control_points.append(Vec(loc.X, loc.Y, loc.Z))
        if rational:
            weights.append(rh_nurbs.Points[i].Weight)

    rhino_knots = [rh_nurbs.Knots[i] for i in range(rh_nurbs.Knots.Count)]
    full_knots = [rhino_knots[0]] + rhino_knots + [rhino_knots[-1]]
    knots, mults = _compact_knots(full_knots)

    return Curve(
        control_points=control_points,
        knots=knots,
        multiplicities=mults,
        degree=degree,
        weights=weights if rational else None,
        closed=rh_nurbs.IsClosed,
    )


def curve_to_rhino_nurbs(curve: Curve) -> Any:
    """Convert an ifckit Curve to a Rhino NurbsCurve.

    Strips one superfluous knot from each end of the full knot vector
    to produce the Rhino ``n + d − 1`` convention.

    Args:
        curve: ``ifckit.geometry.Curve``

    Returns:
        ``Rhino.Geometry.NurbsCurve``
    """
    _require_rhino("curve_to_rhino_nurbs")

    n = len(curve.points)
    d = curve.degree
    full_uknots = _expand_knots(curve.knots, curve.multiplicities)
    rhino_knots = full_uknots[1:-1]

    nc = Rhino.Geometry.NurbsCurve(3, curve.rational, d + 1, n)

    if curve.rational:
        w = curve._weights
        for i in range(n):
            p = curve.points[i]
            nc.Points.SetPoint(i, p.x * w[i], p.y * w[i], p.z * w[i], w[i])
    else:
        for i in range(n):
            p = curve.points[i]
            nc.Points.SetPoint(i, p.x, p.y, p.z)

    for i, k in enumerate(rhino_knots):
        nc.Knots[i] = k

    return nc


def rhino_brep_to_surface(rh_brep: Any) -> Surface:
    """Convert a Rhino Brep to an ifckit Surface.

    Extracts the underlying untrimmed NurbsSurface from the first face.
    Non‑NURBS surfaces are auto‑converted via ``ToNurbsSurface()``.

    Args:
        rh_brep: ``Rhino.Geometry.Brep``

    Returns:
        ``ifckit.geometry.Surface``

    Raises:
        ValueError: if the Brep has no faces or no extractable NURBS surface.
    """
    _require_rhino("rhino_brep_to_surface")

    import Rhino.Geometry as rg

    if rh_brep is None:
        raise ValueError("rh_brep is None")
    faces = rh_brep.Faces
    if faces is None or faces.Count == 0:
        raise ValueError("Brep has no faces")

    for fi in range(faces.Count):
        face = faces[fi]
        underlying = face.UnderlyingSurface()
        if underlying is None:
            continue

        ns = underlying
        if not isinstance(ns, rg.NurbsSurface):
            if hasattr(underlying, "ToNurbsSurface"):
                converted = underlying.ToNurbsSurface()
                if isinstance(converted, rg.NurbsSurface):
                    ns = converted
                else:
                    continue
            else:
                continue

        ud = ns.Degree(0)
        vd = ns.Degree(1)
        nu_pts = ns.Points.CountU
        nv_pts = ns.Points.CountV
        rational = ns.IsRational

        control_points = []
        weights = None
        if rational:
            weights = []
        for ui in range(nu_pts):
            row = []
            if rational:
                wrow = []
            for vi in range(nv_pts):
                cp = ns.Points.GetControlPoint(ui, vi)
                loc = cp.Location
                row.append(Vec(loc.X, loc.Y, loc.Z))
                if rational:
                    wrow.append(cp.Weight)
            control_points.append(row)
            if rational:
                weights.append(wrow)

        rhino_uk = [ns.KnotsU[i] for i in range(ns.KnotsU.Count)]
        rhino_vk = [ns.KnotsV[i] for i in range(ns.KnotsV.Count)]
        full_uk = [rhino_uk[0]] + rhino_uk + [rhino_uk[-1]]
        full_vk = [rhino_vk[0]] + rhino_vk + [rhino_vk[-1]]
        uknots, umults = _compact_knots(full_uk)
        vknots, vmults = _compact_knots(full_vk)

        return Surface(
            control_points=control_points,
            uknots=uknots,
            vknots=vknots,
            umults=umults,
            vmults=vmults,
            udegree=ud,
            vdegree=vd,
            weights=weights,
            uclosed=ns.IsClosed(0),
            vclosed=ns.IsClosed(1),
        )

    raise ValueError("Brep has no extractable NurbsSurface face")


def surface_to_rhino(surface: Surface) -> Any:
    """Convert an ifckit Surface to a Rhino NurbsSurface for preview.

    Strips one superfluous knot from each end of each knot direction
    to match the Rhino ``n + d − 1`` convention.

    Args:
        surface: ``ifckit.geometry.Surface``

    Returns:
        ``Rhino.Geometry.NurbsSurface``
    """
    _require_rhino("surface_to_rhino")

    nu = surface.nu
    nv = surface.nv
    ud = surface.udegree
    vd = surface.vdegree

    full_uknots = _expand_knots(surface.uknots, surface.umults)
    full_vknots = _expand_knots(surface.vknots, surface.vmults)
    rhino_uk = full_uknots[1:-1]
    rhino_vk = full_vknots[1:-1]

    ns = Rhino.Geometry.NurbsSurface.Create(3, surface.rational, ud + 1, vd + 1, nu, nv)

    if surface.rational:
        w = surface._weights
        for i in range(nu):
            for j in range(nv):
                p = surface.control_points[i][j]
                ns.Points.SetPoint(i, j, p.x * w[i][j], p.y * w[i][j], p.z * w[i][j], w[i][j])
    else:
        for i in range(nu):
            for j in range(nv):
                p = surface.control_points[i][j]
                ns.Points.SetPoint(i, j, p.x, p.y, p.z)

    for i, k in enumerate(rhino_uk):
        ns.KnotsU[i] = k
    for j, k in enumerate(rhino_vk):
        ns.KnotsV[j] = k

    return ns


def path_to_rhino_curve(geom: Any) -> Any:
    """Convert a Line, Arc, Curve, Path, or Profile to a Rhino PolyCurve.

    Accepts any of:
    - ``ifckit.geometry.Line``    — single straight segment
    - ``ifckit.geometry.Arc``     — single circular arc
    - ``ifckit.geometry.Curve``   — single NURBS curve
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
        segments: list = [geom]
    elif isinstance(geom, Arc):
        segments = [geom]
    elif isinstance(geom, Curve):
        segments = [geom]
    elif isinstance(geom, Path):
        segments = geom.segments
    else:
        raise TypeError(
            f"path_to_rhino_curve() expects Line, Arc, Curve or Path, got {type(geom).__name__}"
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

        elif isinstance(seg, Curve):
            polycurve.Append(curve_to_rhino_nurbs(seg))

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
# Dev reload helper — re-exported from ifckit.reload for backward compat
# ---------------------------------------------------------------------------

from ifckit.reload import reload_all as _reload_all  # noqa: E402

reload_all = _reload_all


# ---------------------------------------------------------------------------
# GH node helpers — pure Python, no Rhino dependency
# ---------------------------------------------------------------------------


def parse_user_properties(s: Any) -> dict:
    """Parse a JSON string into a properties dict.

    Used in GH nodes for the ``properties`` input.  Returns ``{}`` on any
    error so the node degrades gracefully rather than crashing.

    Example::

        props = rk.parse_user_properties(properties)
    """
    import json

    if not s:
        return {}
    try:
        result = json.loads(str(s))
        if isinstance(result, dict):
            return result
    except (ValueError, TypeError):
        pass
    return {}


def parse_clips(clips: Any) -> list:
    """Convert a GH clips input (plane or list of planes) to ifckit Planes.

    Accepts a single Rhino plane or an iterable of planes.
    Silently skips ``None`` entries.

    Example::

        clip_planes = rk.parse_clips(clips)
    """
    _require_rhino("parse_clips")
    if not clips:
        return []
    clip_list = clips if hasattr(clips, "__iter__") else [clips]
    return [rhino_plane_to_plane(p) for p in clip_list if p is not None]


def extract_first_id(envelope_json: Any, key: str) -> Optional[str]:
    """Extract the ``id`` field from the first item in an envelope list.

    Args:
        envelope_json: JSON string of a keyed envelope e.g.
                       ``{"elements": [{"id": "...", ...}]}``.
        key:           The envelope key to look in, e.g. ``"elements"``,
                       ``"openings"``.

    Returns:
        The ``id`` string, or ``None`` if not found / parse error.

    Example::

        host_id = rk.extract_first_id(host_json, "elements")
        opening_id = rk.extract_first_id(opening_json, "openings")
    """
    import json

    if not envelope_json:
        return None
    try:
        d = json.loads(str(envelope_json))
        items = d.get(key, [])
        if items:
            first = items[0]
            if isinstance(first, str):
                first = json.loads(first)
            return first.get("id")
    except (ValueError, TypeError, AttributeError):
        pass
    return None


def parse_json_list(lst: Any) -> list:
    """Ensure each item in a list is a dict, parsing JSON strings as needed.

    Useful when an envelope list may contain either pre-parsed dicts or
    JSON strings (both are valid in the storey bundle format).

    Example::

        elements = rk.parse_json_list(bundle.get("elements", []))
    """
    import json

    result = []
    for e in lst or []:
        if isinstance(e, str):
            result.append(json.loads(e))
        else:
            result.append(e)
    return result


def merge_envelopes(inputs: Any) -> dict:
    """Merge any number of keyed envelope JSON strings into one dict.

    Lists under the same key are extended (no deduplication), **except**
    for ``elements``: if two element dicts share the same ``id``, their
    ``openings`` lists are merged into the first occurrence rather than
    creating a duplicate element entry.  This is the normal Grasshopper
    pattern where one wall envelope is reused for N opening components.

    Non-list values: last write wins.

    Supported keys: ``elements``, ``openings``, ``doors``, ``windows``,
    ``door_types``, ``window_types``.

    Args:
        inputs: A single envelope JSON string or a list of them.

    Returns:
        Merged dict, e.g. ``{"elements": [...], "openings": [...]}``.

    Example::

        merged = rk.merge_envelopes(envelopes)
    """
    import json

    merged: dict = {}
    # Index of already-seen element ids → position in merged["elements"]
    elem_id_index: dict = {}

    items = inputs if hasattr(inputs, "__iter__") and not isinstance(inputs, str) else [inputs]
    for raw in items:
        if raw is None:
            continue
        s = str(raw).strip()
        if not s:
            continue
        d = json.loads(s)
        for key, value in d.items():
            if key == "elements" and isinstance(value, list):
                merged.setdefault("elements", [])
                for elem in value:
                    eid = elem.get("id") if isinstance(elem, dict) else None
                    if eid and eid in elem_id_index:
                        # Merge openings into the existing element entry.
                        existing = merged["elements"][elem_id_index[eid]]
                        existing.setdefault("openings", [])
                        for op in elem.get("openings", []):
                            existing["openings"].append(op)
                    else:
                        if eid:
                            elem_id_index[eid] = len(merged["elements"])
                        merged["elements"].append(elem)
            elif isinstance(value, list):
                merged.setdefault(key, []).extend(value)
            else:
                merged[key] = value
    return merged
