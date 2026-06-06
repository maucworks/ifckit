"""
ifckit.builders._profile
========================

Profile manipulation helpers: IFC profile creation, triangulation,
axis placement, and extraction from IfcProfileDef entities.
"""

from __future__ import annotations

import math as _math
from typing import TYPE_CHECKING, Any, Sequence

import ifcopenshell
import numpy as np

from ifckit.builders._precision import round_coord

if TYPE_CHECKING:
    pass


def pt2(f: ifcopenshell.file, x: float, y: float) -> ifcopenshell.entity_instance:
    return f.create_entity("IfcCartesianPoint", Coordinates=[round_coord(x), round_coord(y)])


def _signed_area_2d(points: Sequence[tuple[float, float]]) -> float:
    n = len(points)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += points[i][0] * points[j][1]
        area -= points[j][0] * points[i][1]
    return area / 2.0


def _pts_to_polyline(
    f: ifcopenshell.file,
    pts_2d: list,
    ensure_ccw: bool,
    reverse_for_hole: bool = False,
) -> ifcopenshell.entity_instance:
    _ROUND = 1000.0
    pts = [(round(p[0] * _ROUND) / _ROUND, round(p[1] * _ROUND) / _ROUND) for p in pts_2d]
    _EPS = 1e-9
    if not (abs(pts[0][0] - pts[-1][0]) < _EPS and abs(pts[0][1] - pts[-1][1]) < _EPS):
        pts.append(pts[0])
    area = _signed_area_2d(pts)
    if ensure_ccw and not reverse_for_hole and area < 0:
        pts = list(reversed(pts[:-1]))
        pts.append(pts[0])
    elif reverse_for_hole and area > 0:
        pts = list(reversed(pts[:-1]))
        pts.append(pts[0])
    ifc_pts = [pt2(f, x, y) for x, y in pts]
    return f.create_entity("IfcPolyline", Points=ifc_pts)


def profile_from_points(
    f: ifcopenshell.file,
    points_2d_or_path: Any,
    profile_name: str | None = None,
    ensure_ccw: bool = True,
) -> ifcopenshell.entity_instance:
    from ifckit.geometry import Path

    holes: list = []
    if isinstance(points_2d_or_path, Path):
        holes = points_2d_or_path.holes
        points_2d_or_path = points_2d_or_path.to_profile_points()
    elif hasattr(points_2d_or_path, "to_profile_points"):
        points_2d_or_path = points_2d_or_path.to_profile_points()

    outer_polyline = _pts_to_polyline(f, list(points_2d_or_path), ensure_ccw=ensure_ccw)

    if not holes:
        return f.create_entity(
            "IfcArbitraryClosedProfileDef",
            ProfileType="AREA",
            ProfileName=profile_name,
            OuterCurve=outer_polyline,
        )

    inner_polylines = []
    for hole in holes:
        if isinstance(hole, Path):
            hole_pts = hole.to_profile_points()
        elif hasattr(hole, "to_profile_points"):
            hole_pts = hole.to_profile_points()
        else:
            hole_pts = list(hole)
        inner_polylines.append(
            _pts_to_polyline(f, hole_pts, ensure_ccw=False, reverse_for_hole=True)
        )

    return f.create_entity(
        "IfcArbitraryProfileDefWithVoids",
        ProfileType="AREA",
        ProfileName=profile_name,
        OuterCurve=outer_polyline,
        InnerCurves=inner_polylines,
    )


def profile_to_ifc(
    f: ifcopenshell.file,
    profile_source: Any,
    profile_name: str | None = None,
    ensure_ccw: bool = True,
) -> ifcopenshell.entity_instance:
    if hasattr(profile_source, "to_ifc"):
        return profile_source.to_ifc(f)
    if hasattr(profile_source, "get_profile_points"):
        pts = profile_source.get_profile_points()
        return profile_from_points(f, pts, profile_name=profile_name, ensure_ccw=ensure_ccw)
    return profile_from_points(f, profile_source, profile_name=profile_name, ensure_ccw=ensure_ccw)


def _triangulate_polygon(
    pts: list[tuple[float, float]],
) -> list[tuple[int, int, int]]:
    n = len(pts)
    if n < 3:
        return []
    if n == 3:
        return [(0, 1, 2)]

    def _area(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def _point_in_triangle(a, b, c, p):
        return (
            (c[0] - p[0]) * (a[1] - p[1]) - (a[0] - p[0]) * (c[1] - p[1]) >= 0
            and (a[0] - p[0]) * (b[1] - p[1]) - (b[0] - p[0]) * (a[1] - p[1]) >= 0
            and (b[0] - p[0]) * (c[1] - p[1]) - (c[0] - p[0]) * (b[1] - p[1]) >= 0
        )

    class Node:
        __slots__ = ("i", "x", "y", "prev", "next")

        def __init__(self, i, x, y):
            self.i = i
            self.x = x
            self.y = y
            self.prev = None
            self.next = None

    first = None
    prev_node = None
    for i, (x, y) in enumerate(pts):
        node = Node(i, x, y)
        if prev_node is None:
            first = node
        else:
            prev_node.next = node
            node.prev = prev_node
        prev_node = node
    first.prev = prev_node
    prev_node.next = first

    triangles = []
    ear = first
    while ear is not None:
        a, b, c = ear.prev, ear, ear.next
        if a is c:
            break

        if _area((a.x, a.y), (b.x, b.y), (c.x, c.y)) < 0:
            ear = ear.next
            if ear is first:
                break
            continue

        bad = False
        p = c.next
        while p is not a:
            if not _point_in_triangle((a.x, a.y), (b.x, b.y), (c.x, c.y), (p.x, p.y)):
                p = p.next
                continue
            if _area((p.prev.x, p.prev.y), (p.x, p.y), (p.next.x, p.next.y)) < 0:
                bad = True
                break
            p = p.next

        if bad:
            ear = ear.next
            if ear is first:
                break
            continue

        triangles.append((a.i, b.i, c.i))
        a.next = c
        c.prev = a
        ear = c
        if ear is first:
            break

    return triangles


def _apply_axis2placement2d(
    pts: list[tuple[float, float]],
    position: ifcopenshell.entity_instance | None,
) -> list[tuple[float, float]]:
    if position is None:
        return pts

    loc = position.Location
    tx = loc.Coordinates[0] if loc else 0.0
    ty = loc.Coordinates[1] if loc else 0.0

    ref = position.RefDirection
    if ref:
        rx, ry = ref.DirectionRatios[0], ref.DirectionRatios[1]
    else:
        rx, ry = 1.0, 0.0

    result = []
    for u, v in pts:
        x = tx + rx * u - ry * v
        y = ty + ry * u + rx * v
        result.append((x, y))
    return result


def _profile_def_to_pts(
    prof_def: ifcopenshell.entity_instance,
    segments: int = 8,
) -> list[tuple[float, float]]:
    ifc_class = prof_def.is_a()

    if ifc_class == "IfcRectangleProfileDef":
        hw = prof_def.XDim / 2
        hh = prof_def.YDim / 2
        pts = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        return _apply_axis2placement2d(pts, getattr(prof_def, "Position", None))

    if ifc_class in ("IfcCircleProfileDef", "IfcCircleHollowProfileDef"):
        r = prof_def.Radius
        pts = [
            (r * np.cos(2 * np.pi * i / segments), r * np.sin(2 * np.pi * i / segments))
            for i in range(segments)
        ]
        return _apply_axis2placement2d(pts, getattr(prof_def, "Position", None))

    if ifc_class == "IfcIShapeProfileDef":
        hw = prof_def.OverallWidth / 2
        hh = prof_def.OverallDepth / 2
        htw = prof_def.WebThickness / 2
        tf = prof_def.FlangeThickness
        pts = [
            (-hw, -hh),
            (hw, -hh),
            (hw, -hh + tf),
            (htw, -hh + tf),
            (htw, hh - tf),
            (hw, hh - tf),
            (hw, hh),
            (-hw, hh),
            (-hw, hh - tf),
            (-htw, hh - tf),
            (-htw, -hh + tf),
            (-hw, -hh + tf),
        ]
        return _apply_axis2placement2d(pts, getattr(prof_def, "Position", None))

    if ifc_class == "IfcDerivedProfileDef":
        pts = _profile_def_to_pts(prof_def.ParentProfile, segments=segments)

        op = prof_def.Operator
        if op and op.is_a() in (
            "IfcCartesianTransformationOperator2D",
            "IfcCartesianTransformationOperator2DnonUniform",
        ):
            origin = op.LocalOrigin.Coordinates if op.LocalOrigin else (0.0, 0.0)
            a1 = op.Axis1.DirectionRatios if op.Axis1 else (1.0, 0.0)
            a2 = op.Axis2.DirectionRatios if op.Axis2 else (0.0, 1.0)
            sx = getattr(op, "Scale", None) or 1.0
            sy = getattr(op, "Scale2", None)
            if sy is None:
                sy = sx
            transformed = []
            for u, v in pts:
                x = origin[0] + sx * a1[0] * u + sy * a2[0] * v
                y = origin[1] + sx * a1[1] * u + sy * a2[1] * v
                transformed.append((x, y))
            pts = transformed

        return pts

    if ifc_class in ("IfcArbitraryClosedProfileDef", "IfcArbitraryProfileDefWithVoids"):
        outer = prof_def.OuterCurve
        if outer.is_a() == "IfcPolyline":
            pts = [(pt.Coordinates[0], pt.Coordinates[1]) for pt in outer.Points]
            if (
                len(pts) > 1
                and abs(pts[0][0] - pts[-1][0]) < 1e-6
                and abs(pts[0][1] - pts[-1][1]) < 1e-6
            ):
                pts = pts[:-1]
            return pts
        if outer.is_a() == "IfcCompositeCurve":
            pts = []
            for seg in outer.Segments:
                curve = seg.ParentCurve
                if curve.is_a() == "IfcPolyline":
                    for pt in curve.Points:
                        p = (pt.Coordinates[0], pt.Coordinates[1])
                        if (
                            not pts
                            or abs(pts[-1][0] - p[0]) > 1e-6
                            or abs(pts[-1][1] - p[1]) > 1e-6
                        ):
                            pts.append(p)
                elif curve.is_a() == "IfcTrimmedCurve":
                    basis = curve.BasisCurve
                    if basis.is_a() == "IfcCircle":
                        r = basis.Radius
                        c = basis.Position
                        cx = c.Location.Coordinates[0] if c and c.Location else 0.0
                        cy = c.Location.Coordinates[1] if c and c.Location else 0.0
                        # IfcParameterValue for IfcCircle is in degrees; convert to radians.
                        t1_deg = curve.Trim1[0] if curve.Trim1 else 0.0
                        t2_deg = curve.Trim2[0] if curve.Trim2 else 360.0
                        t1 = _math.radians(t1_deg)
                        t2 = _math.radians(t2_deg)
                        n = max(4, segments)
                        for k in range(n + 1):
                            angle = t1 + (t2 - t1) * k / n
                            p = (cx + r * _math.cos(angle), cy + r * _math.sin(angle))
                            if (
                                not pts
                                or abs(pts[-1][0] - p[0]) > 1e-6
                                or abs(pts[-1][1] - p[1]) > 1e-6
                            ):
                                pts.append(p)
            if (
                len(pts) > 1
                and abs(pts[0][0] - pts[-1][0]) < 1e-6
                and abs(pts[0][1] - pts[-1][1]) < 1e-6
            ):
                pts = pts[:-1]
            if pts:
                return pts
        raise ValueError(
            f"Unsupported outer curve type {outer.is_a()!r} in {ifc_class}. "
            "Only IfcPolyline and IfcCompositeCurve are supported."
        )

    if ifc_class == "IfcLShapeProfileDef":
        d = prof_def.Depth
        w = prof_def.Width
        t = prof_def.Thickness
        pts = [
            (0.0, 0.0),
            (w, 0.0),
            (w, t),
            (t, t),
            (t, d),
            (0.0, d),
        ]
        return _apply_axis2placement2d(pts, getattr(prof_def, "Position", None))

    if ifc_class == "IfcTShapeProfileDef":
        d = prof_def.Depth
        fw = prof_def.FlangeWidth
        tw = prof_def.WebThickness
        tf = prof_def.FlangeThickness
        hw = fw / 2
        htw = tw / 2
        pts = [
            (-htw, 0.0),
            (htw, 0.0),
            (htw, d - tf),
            (hw, d - tf),
            (hw, d),
            (-hw, d),
            (-hw, d - tf),
            (-htw, d - tf),
        ]
        return _apply_axis2placement2d(pts, getattr(prof_def, "Position", None))

    if ifc_class == "IfcZShapeProfileDef":
        d = prof_def.Depth
        fw = prof_def.FlangeWidth
        tw = prof_def.WebThickness
        tf = prof_def.FlangeThickness
        htw = tw / 2
        hd = d / 2
        pts = [
            (-htw, -hd),
            (fw - htw, -hd),
            (fw - htw, -hd + tf),
            (htw, -hd + tf),
            (htw, hd - tf),
            (htw - fw, hd - tf),
            (htw - fw, hd),
            (-htw, hd),
        ]
        return _apply_axis2placement2d(pts, getattr(prof_def, "Position", None))

    if ifc_class == "IfcCShapeProfileDef":
        d = prof_def.Depth
        w = prof_def.Width
        t = prof_def.WallThickness
        g = prof_def.Girth or 0.0
        hd = d / 2
        if g > 0:
            pts = [
                (0.0, -hd),
                (w, -hd),
                (w, -hd + g),
                (w - t, -hd + g),
                (w - t, -hd + t),
                (t, -hd + t),
                (t, hd - t),
                (w - t, hd - t),
                (w - t, hd - g),
                (w, hd - g),
                (w, hd),
                (0.0, hd),
            ]
        else:
            pts = [
                (0.0, -hd),
                (w, -hd),
                (w, -hd + t),
                (t, -hd + t),
                (t, hd - t),
                (w, hd - t),
                (w, hd),
                (0.0, hd),
            ]
        return _apply_axis2placement2d(pts, getattr(prof_def, "Position", None))

    if ifc_class == "IfcTrapeziumProfileDef":
        hb = prof_def.BottomXDim / 2
        ht = prof_def.TopXDim / 2
        y = prof_def.YDim
        ox = prof_def.TopXOffset
        pts = [
            (-hb, 0.0),
            (hb, 0.0),
            (ox + ht, y),
            (ox - ht, y),
        ]
        return _apply_axis2placement2d(pts, getattr(prof_def, "Position", None))

    if ifc_class == "IfcCompositeProfileDef":
        pts = []
        for child in prof_def.Profiles:
            pts.extend(_profile_def_to_pts(child, segments=segments))
        return pts

    raise ValueError(
        f"Unsupported IfcProfileDef type {ifc_class!r}. "
        "Supported: IfcRectangleProfileDef, IfcCircleProfileDef, IfcCircleHollowProfileDef, "
        "IfcIShapeProfileDef, IfcDerivedProfileDef, IfcArbitraryClosedProfileDef, "
        "IfcArbitraryProfileDefWithVoids, IfcTShapeProfileDef, IfcZShapeProfileDef, "
        "IfcCShapeProfileDef, IfcTrapeziumProfileDef, IfcLShapeProfileDef, "
        "IfcCompositeProfileDef."
    )


def _profile_def_to_rings(
    prof_def: ifcopenshell.entity_instance,
    segments: int = 32,
) -> tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]:
    ifc_class = prof_def.is_a()

    if ifc_class == "IfcCircleHollowProfileDef":
        r_outer = prof_def.Radius
        r_inner = r_outer - prof_def.WallThickness
        pos = getattr(prof_def, "Position", None)

        outer_pts = [
            (r_outer * np.cos(2 * np.pi * i / segments), r_outer * np.sin(2 * np.pi * i / segments))
            for i in range(segments)
        ]
        inner_pts = [
            (r_inner * np.cos(2 * np.pi * i / segments), r_inner * np.sin(2 * np.pi * i / segments))
            for i in range(segments - 1, -1, -1)
        ]
        outer_pts = _apply_axis2placement2d(outer_pts, pos)
        inner_pts = _apply_axis2placement2d(inner_pts, pos)
        return outer_pts, [inner_pts]

    if ifc_class == "IfcArbitraryProfileDefWithVoids":
        outer_pts = _profile_def_to_pts(prof_def, segments=segments)

        inner_rings: list[list[tuple[float, float]]] = []
        for void_curve in prof_def.InnerCurves:
            void_pts: list[tuple[float, float]] = []
            if void_curve.is_a() == "IfcPolyline":
                void_pts = [(pt.Coordinates[0], pt.Coordinates[1]) for pt in void_curve.Points]
                if (
                    len(void_pts) > 1
                    and abs(void_pts[0][0] - void_pts[-1][0]) < 1e-6
                    and abs(void_pts[0][1] - void_pts[-1][1]) < 1e-6
                ):
                    void_pts = void_pts[:-1]
            elif void_curve.is_a() == "IfcCircle":
                r = void_curve.Radius
                c = void_curve.Position
                cx = c.Location.Coordinates[0] if c and c.Location else 0.0
                cy = c.Location.Coordinates[1] if c and c.Location else 0.0
                void_pts = [
                    (
                        cx + r * _math.cos(2 * _math.pi * i / segments),
                        cy + r * _math.sin(2 * _math.pi * i / segments),
                    )
                    for i in range(segments)
                ]

            if not void_pts:
                continue

            area = (
                sum(
                    void_pts[i][0] * void_pts[(i + 1) % len(void_pts)][1]
                    - void_pts[(i + 1) % len(void_pts)][0] * void_pts[i][1]
                    for i in range(len(void_pts))
                )
                / 2.0
            )
            if area > 0:
                void_pts = list(reversed(void_pts))
            inner_rings.append(void_pts)

        return outer_pts, inner_rings

    outer_pts = _profile_def_to_pts(prof_def, segments=segments)
    return outer_pts, []


def _stitch_annulus(
    outer: list[tuple[float, float]],
    inner: list[tuple[float, float]],
) -> tuple[list[tuple[float, float]], list[tuple[float, float]], list[tuple[int, int, int, int]]]:
    n_o = len(outer)
    n_i = len(inner)
    if n_o < 2 or n_i < 2:
        return outer, inner, []

    n_stitch = (n_o * n_i) // _math.gcd(n_o, n_i)
    outer_r = _resample_ring(outer, n_stitch)
    inner_r = _resample_ring(inner, n_stitch)

    quads = []
    for i in range(n_stitch):
        i_next = (i + 1) % n_stitch
        quads.append((i, i_next, n_stitch + i_next, n_stitch + i))

    return outer_r, inner_r, quads


def _resample_ring(ring: list[tuple[float, float]], n: int) -> list[tuple[float, float]]:
    if len(ring) == n:
        return ring

    cum = [0.0]
    for i in range(len(ring)):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % len(ring)]
        seg_len = _math.hypot(x1 - x0, y1 - y0)
        cum.append(cum[-1] + seg_len)
    total = cum[-1]
    if total < 1e-12:
        return ring[:n] if len(ring) >= n else ring + [ring[-1]] * (n - len(ring))

    resampled = []
    seg_i = 0
    for k in range(n):
        target = total * k / n
        while seg_i < len(ring) - 1 and cum[seg_i + 1] < target - 1e-12:
            seg_i += 1
        t = 0.0
        seg_len = cum[seg_i + 1] - cum[seg_i]
        if seg_len > 1e-12:
            t = (target - cum[seg_i]) / seg_len
        x0, y0 = ring[seg_i % len(ring)]
        x1, y1 = ring[(seg_i + 1) % len(ring)]
        resampled.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))

    return resampled


def shapely_polygon_to_ifc_profile(
    f: ifcopenshell.file,
    polygon: Any,
    profile_name: str | None = None,
) -> ifcopenshell.entity_instance:
    ext_coords = list(polygon.exterior.coords)
    if (
        len(ext_coords) > 1
        and abs(ext_coords[0][0] - ext_coords[-1][0]) < 1e-9
        and abs(ext_coords[0][1] - ext_coords[-1][1]) < 1e-9
    ):
        ext_coords = ext_coords[:-1]
    outer_polyline = _pts_to_polyline(f, ext_coords, ensure_ccw=True)

    interior_rings = list(polygon.interiors)
    if not interior_rings:
        return f.create_entity(
            "IfcArbitraryClosedProfileDef",
            ProfileType="AREA",
            ProfileName=profile_name,
            OuterCurve=outer_polyline,
        )

    inner_polylines = []
    for ring in interior_rings:
        hole_coords = list(ring.coords)
        if (
            len(hole_coords) > 1
            and abs(hole_coords[0][0] - hole_coords[-1][0]) < 1e-9
            and abs(hole_coords[0][1] - hole_coords[-1][1]) < 1e-9
        ):
            hole_coords = hole_coords[:-1]
        inner_polylines.append(
            _pts_to_polyline(f, hole_coords, ensure_ccw=False, reverse_for_hole=True)
        )

    return f.create_entity(
        "IfcArbitraryProfileDefWithVoids",
        ProfileType="AREA",
        ProfileName=profile_name,
        OuterCurve=outer_polyline,
        InnerCurves=inner_polylines,
    )
