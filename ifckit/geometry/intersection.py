"""
ifckit.geometry.intersection
=============================

Intersection — auto‑dispatch for geometric intersections.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List

from ifckit.geometry.primitives import Plane, Vec

if TYPE_CHECKING:
    from ifckit.geometry.curve import Curve
    from ifckit.geometry.surface import Surface


@dataclass
class Intersection:
    """Result of intersecting two geometric objects.

    Attributes:
        curves:  Intersection curves (lines, section curves).
        points:  Intersection points.
    """

    curves: List["Curve"] = field(default_factory=list)
    points: List[Vec] = field(default_factory=list)

    # ── Auto‑dispatch ─────────────────────────────────────────────

    @classmethod
    def of(cls, a: object, b: object) -> "Intersection":
        """Intersect two geometry objects.

        Supported type combinations:

        ==========  ==========  ==========
        A \\ B      Plane       Surface       Curve
        ==========  ==========  ==========
        Plane       **Line** (analytic)   Curve(s) (OCC)  Point(s) (OCC)
        Surface     Curve(s) (OCC)      Curve(s) (OCC)  Point(s) (OCC)
        Curve       Point(s) (OCC)     Point(s) (OCC)  Point(s) (OCC)
        ==========  ==========  ==========
        """
        if isinstance(a, Plane) and isinstance(b, Plane):
            return cls.plane_plane(a, b)

        # All remaining cases require pythonocc-core
        return cls._occ_intersect(a, b)

    # ── Plane‑Plane (analytic, no OCC) ────────────────────────────

    @classmethod
    def plane_plane(cls, p1: Plane, p2: Plane) -> "Intersection":
        """Intersect two planes → a straight line."""
        n1 = p1.z_axis
        n2 = p2.z_axis
        d1 = p1.origin @ n1
        d2 = p2.origin @ n2

        direction = n1**n2
        dir_len = direction.length()
        if dir_len < 1e-12:
            return cls(curves=[], points=[])

        direction = direction / dir_len
        # Find a point on both planes using linear algebra:
        #   n1 · p = d1
        #   n2 · p = d2
        # Pick p = u × n2 + v × n1 + w × direction
        # For coplanarity: direction · n1 = 0, direction · n2 = 0
        # Solve using a vector perpendicular to direction (e.g., an arbitrary one)
        # Find a vector in both planes — we can pick the one closest to origin
        # along the direction perpendicular common to both

        # Find a point on both planes:
        # The line is p = p0 + t * direction
        # We need p0 such that n1·p0 = d1 and n2·p0 = d2
        # p0 lies in a plane perpendicular to direction
        # Choose the point closest to origin: minimize |p0|²
        # Using Lagrange multipliers

        # Solve [n1, n2]² p0 = [d1, d2]
        # In the subspace perpendicular to direction
        # p0 = a * perp1 + b * perp2 where perp1, perp2 span the plane ⟂ direction

        # Simpler: compute using cross products
        # p0 = (d1 * n2 × direction - d2 * n1 × direction + (n1 × n2) * 0) / |direction|²
        # The formula: p0 = ((d1 * n2 - d2 * n1) × direction) / |direction|²
        perp = n1 * d2 - n2 * d1
        cross = perp**direction
        p0 = cross / (dir_len * dir_len)

        from ifckit.geometry.curve import Curve

        ext = direction * 1e6
        return cls(
            curves=[
                Curve.from_tangents(
                    p0 - ext,
                    direction,
                    p0 + ext,
                    direction,
                    scale=1.0,
                )
            ]
        )

    # ── OCC path ──────────────────────────────────────────────────

    @classmethod
    def _occ_intersect(cls, a: object, b: object) -> "Intersection":
        """Dispatch to the correct OCC intersection routine."""
        try:
            from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
            from OCC.Core.GeomAPI import GeomAPI_ExtremaCurveCurve
            from OCC.Core.gp import gp_Pnt
        except ImportError:
            raise ImportError("Intersection requires pythonocc-core for non-plane types.")

        from ifckit.geometry.curve import Curve
        from ifckit.geometry.surface import Surface

        # Surface‑Plane / Surface‑Surface via BRepAlgoAPI_Section
        if isinstance(a, Surface) and isinstance(b, (Plane, Surface)):
            return cls._occ_section(a, b)
        if isinstance(b, Surface) and isinstance(a, (Plane, Surface)):
            return cls._occ_section(b, a)

        # Curve‑Curve via GeomAPI_ExtremaCurveCurve
        if isinstance(a, Curve) and isinstance(b, Curve):
            from ifckit.geometry.surface import _build_occ_edge

            e1 = _build_occ_edge(a)
            e2 = _build_occ_edge(b)
            adapt1 = BRepAdaptor_Curve(e1)
            adapt2 = BRepAdaptor_Curve(e2)

            ext = GeomAPI_ExtremaCurveCurve(
                adapt1.Curve().Curve(),
                adapt2.Curve().Curve(),
            )
            pts: list[Vec] = []
            for i in range(ext.NbExtrema()):
                p1, p2 = gp_Pnt(), gp_Pnt()
                ext.Points(i + 1, p1, p2)
                mid = Vec(
                    (p1.X() + p2.X()) * 0.5,
                    (p1.Y() + p2.Y()) * 0.5,
                    (p1.Z() + p2.Z()) * 0.5,
                )
                pts.append(mid)
            return cls(points=pts)

        raise TypeError(f"Unsupported intersection: {type(a).__name__} × {type(b).__name__}")

    # ── OCC section (BRepAlgoAPI_Section) ─────────────────────────

    @classmethod
    def _occ_section(cls, surf: "Surface", other: object) -> "Intersection":
        """Surface‑Plane or Surface‑Surface intersection."""
        from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
        from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Section
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
        from OCC.Core.GeomAbs import GeomAbs_BSplineCurve
        from OCC.Core.gp import gp_Dir, gp_Pln, gp_Pnt
        from OCC.Core.TopAbs import TopAbs_EDGE
        from OCC.Core.TopExp import TopExp_Explorer

        from ifckit.geometry.surface import Surface as _Surf
        from ifckit.geometry.surface import _build_occ_surface

        # Use cached trimmed face (from patch) to avoid intersecting
        # outside the patch boundary.
        occ_face = getattr(surf, "_occ_face", None)
        if occ_face is None:
            occ_surf = _build_occ_surface(surf)
            occ_face = BRepBuilderAPI_MakeFace(occ_surf, 1e-6).Face()

        if isinstance(other, Plane):
            pl = other
            # Create a bounded plane face that covers the surface's
            # approximate extent — an infinite gp_Pln makes the
            # section algorithm slow and unbounded.
            bbox = _surface_bbox(occ_face)
            margin = max(bbox[2] - bbox[0], bbox[3] - bbox[1]) * 0.5 + 100
            occ_other = BRepBuilderAPI_MakeFace(
                gp_Pln(
                    gp_Pnt(pl.origin.x, pl.origin.y, pl.origin.z),
                    gp_Dir(pl.z_axis.x, pl.z_axis.y, pl.z_axis.z),
                ),
                bbox[0] - margin,
                bbox[2] + margin,
                bbox[1] - margin,
                bbox[3] + margin,
            ).Face()
        elif isinstance(other, _Surf):
            occ_s2 = _build_occ_surface(other)
            occ_other = BRepBuilderAPI_MakeFace(occ_s2, 1e-6).Face()
        else:
            raise TypeError(f"Unsupported section type: {type(other).__name__}")

        section = BRepAlgoAPI_Section(occ_face, occ_other)
        section.Build()

        curves: list = []
        exp = TopExp_Explorer(section.Shape(), TopAbs_EDGE)
        while exp.More():
            edge = exp.Current()
            adaptor = BRepAdaptor_Curve(edge)
            if adaptor.GetType() == GeomAbs_BSplineCurve:
                from ifckit.geometry.curve import Curve as _Crv

                curves.append(_Crv.from_occ_edge(edge))
            exp.Next()

        return cls(curves=curves)


def _surface_bbox(face: object, n: int = 10) -> tuple[float, float, float, float]:
    """Compute 2D bounding box ``(umin, vmin, umax, vmax)`` of a face's surface."""
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface

    adaptor = BRepAdaptor_Surface(face)
    s = adaptor.Surface().Surface()
    umin = adaptor.FirstUParameter()
    umax = adaptor.LastUParameter()
    vmin = adaptor.FirstVParameter()
    vmax = adaptor.LastVParameter()
    xs, ys = [], []
    for i in range(n):
        for j in range(n):
            u = umin + (umax - umin) * i / (n - 1)
            v = vmin + (vmax - vmin) * j / (n - 1)
            p = s.Value(u, v)
            xs.append(p.X())
            ys.append(p.Y())
    return min(xs), min(ys), max(xs), max(ys)
