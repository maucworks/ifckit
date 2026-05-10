"""
ifckit.profiles.shapes
======================

Concrete profile types:

  PolygonProfile          — arbitrary closed polygon (straight edges)
  RoundedPolygonProfile   — polygon with per-corner arc fillets
  RectangleProfile        — parametric rectangle  → IfcRectangleProfileDef
  CircleProfile           — parametric circle     → IfcCircleProfileDef
  HollowCircleProfile     — hollow circle (tube)  → IfcCircleHollowProfileDef

All emit the appropriate IFC native type where one exists; arbitrary profiles
use IfcArbitraryClosedProfileDef with an IfcCompositeCurve for arc segments.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple, Union

from ifckit.profiles.base import Profile

if TYPE_CHECKING:
    import ifcopenshell


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _signed_area_2d(pts: List[Tuple[float, float]]) -> float:
    """Shoelace signed area. Positive = CCW."""
    n = len(pts)
    a = 0.0
    for i in range(n):
        j = (i + 1) % n
        a += pts[i][0] * pts[j][1]
        a -= pts[j][0] * pts[i][1]
    return a / 2.0


def _ensure_ccw(pts: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Return pts in CCW order (without closing duplicate)."""
    if _signed_area_2d(pts) < 0:
        return list(reversed(pts))
    return pts


def _pt2(f: "ifcopenshell.file", x: float, y: float) -> "ifcopenshell.entity_instance":
    from ifckit.builders._geom import pt2

    return pt2(f, x, y)


def _build_polyline_profile(
    f: "ifcopenshell.file",
    points: List[Tuple[float, float]],
    name: Optional[str],
) -> "ifcopenshell.entity_instance":
    """IfcArbitraryClosedProfileDef backed by an IfcPolyline."""
    pts = _ensure_ccw(list(points))
    # close
    if not (abs(pts[0][0] - pts[-1][0]) < 1e-9 and abs(pts[0][1] - pts[-1][1]) < 1e-9):
        pts.append(pts[0])
    ifc_pts = [_pt2(f, x, y) for x, y in pts]
    polyline = f.create_entity("IfcPolyline", Points=ifc_pts)
    return f.create_entity(
        "IfcArbitraryClosedProfileDef",
        ProfileType="AREA",
        ProfileName=name,
        OuterCurve=polyline,
    )


def _arc_fillet(
    cx: float,
    cy: float,
    r: float,
    start_angle: float,
    sweep_angle: float,
    n_pts: int = 8,
) -> List[Tuple[float, float]]:
    """Sample an arc fillet as (x, y) points, NOT including the first point."""
    pts = []
    for i in range(1, n_pts + 1):
        a = start_angle + sweep_angle * i / n_pts
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


# ---------------------------------------------------------------------------
# PolygonProfile
# ---------------------------------------------------------------------------


class PolygonProfile(Profile):
    """
    Closed polygon profile from explicit 2D or 3D points.

    Emits ``IfcArbitraryClosedProfileDef`` with ``IfcPolyline``.

    This replaces the standalone ``profile_from_points()`` function in
    ``builders/_geom.py`` (which now delegates here).

    Args:
        points:   Sequence of (x, y) or (x, y, z) tuples, or Vec objects.
                  Z is ignored.
        name:     Optional profile name.
        rotation: CCW rotation around local origin (radians, default 0).
        offset_x: Additional X translation (m, default 0).
        offset_y: Additional Y translation (m, default 0).
    """

    profile_type = "polygon"

    def __init__(
        self,
        points: Sequence[Union[Tuple[float, float], Tuple[float, float, float], Any]],
        name: Optional[str] = None,
        rotation: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        self.name = name
        self.points: List[Tuple[float, float]] = []
        for p in points:
            if hasattr(p, "x") and hasattr(p, "y"):
                self.points.append((float(p.x), float(p.y)))
            elif len(p) >= 2:
                self.points.append((float(p[0]), float(p[1])))
            else:
                raise ValueError(f"Cannot interpret point {p!r} as (x, y)")
        if len(self.points) < 3:
            raise ValueError("PolygonProfile requires at least 3 points")
        super().__init__()
        self._init_transform(rotation, offset_x, offset_y)

    def _bbox(self) -> Tuple[float, float]:
        """Bounding box width × height of the raw polygon points."""
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (max(xs) - min(xs), max(ys) - min(ys))

    def _bbox_sw(self) -> Tuple[float, float]:
        """SW corner (min x, min y) of the raw polygon points."""
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return (min(xs), min(ys))

    def get_profile_points(self) -> List[Tuple[float, float]]:
        return self._apply_transform(list(self.points), bbox=self._bbox(), bbox_sw=self._bbox_sw())

    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        return _build_polyline_profile(ifc_file, self.get_profile_points(), self.name)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "profile_type": self.profile_type,
            "points": list(self.points),
            **self._transform_dict(),
        }
        if self.name is not None:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PolygonProfile":
        r, ox, oy, anch = cls._transform_from_dict(d, default_anchor="c")
        return cls(points=d["points"], name=d.get("name"), rotation=r, offset_x=ox, offset_y=oy)


# ---------------------------------------------------------------------------
# RoundedPolygonProfile
# ---------------------------------------------------------------------------


class RoundedPolygonProfile(Profile):
    """
    Closed polygon with circular arc fillets at each corner.

    Emits ``IfcArbitraryClosedProfileDef`` with ``IfcPolyline`` (sampled arcs).
    The fillet arcs are approximated by ``arc_segments`` straight segments each,
    giving a clean tessellation suitable for all IFC viewers.

    Args:
        points:       Sequence of (x, y) corner points (not closed).
        radius:       Fillet radius — either a single float applied to all corners,
                      or a list with one value per corner (0 = sharp corner).
        name:         Optional profile name.
        arc_segments: Number of line segments per fillet arc (default 8).
    """

    profile_type = "rounded_polygon"

    def __init__(
        self,
        points: Sequence[Union[Tuple[float, float], Any]],
        radius: Union[float, Sequence[float]] = 0.0,
        name: Optional[str] = None,
        arc_segments: int = 8,
        rotation: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        raw: List[Tuple[float, float]] = []
        for p in points:
            if hasattr(p, "x") and hasattr(p, "y"):
                raw.append((float(p.x), float(p.y)))
            else:
                raw.append((float(p[0]), float(p[1])))
        if len(raw) < 3:
            raise ValueError("RoundedPolygonProfile requires at least 3 points")

        n = len(raw)
        if isinstance(radius, (int, float)):
            radii: List[float] = [float(radius)] * n
        else:
            radii = [float(r) for r in radius]
            if len(radii) != n:
                raise ValueError(f"radius list length {len(radii)} != points length {n}")

        self.points = raw
        self.radii = radii
        self.name = name
        self.arc_segments = int(arc_segments)
        super().__init__()
        self._init_transform(rotation, offset_x, offset_y)

    def _build_outline(self) -> List[Tuple[float, float]]:
        """Build the tessellated outline including fillet arcs."""
        pts = self.points
        n = len(pts)
        outline: List[Tuple[float, float]] = []

        for i in range(n):
            r = self.radii[i]
            prev = pts[(i - 1) % n]
            curr = pts[i]
            nxt = pts[(i + 1) % n]

            if r <= 0.0:
                outline.append(curr)
                continue

            # Vectors from corner toward neighbours
            dx0 = prev[0] - curr[0]
            dy0 = prev[1] - curr[1]  # noqa: E702
            dx1 = nxt[0] - curr[0]
            dy1 = nxt[1] - curr[1]  # noqa: E702
            d0 = math.hypot(dx0, dy0)
            d1 = math.hypot(dx1, dy1)
            if d0 < 1e-12 or d1 < 1e-12:
                outline.append(curr)
                continue

            # Unit vectors
            ux0, uy0 = dx0 / d0, dy0 / d0
            ux1, uy1 = dx1 / d1, dy1 / d1

            # Half-angle between incoming/outgoing edge
            cos_half = ux0 * ux1 + uy0 * uy1
            cos_half = max(-1.0, min(1.0, cos_half))
            half_angle = math.acos(cos_half) / 2.0
            if half_angle < 1e-9 or abs(math.pi / 2 - half_angle) < 1e-9:
                outline.append(curr)
                continue

            # Tangent length from corner to tangent point
            t_len = r / math.tan(half_angle)
            if t_len > d0 - 1e-9 or t_len > d1 - 1e-9:
                # Radius too large — skip fillet
                outline.append(curr)
                continue

            # Tangent points
            tx0 = curr[0] + ux0 * t_len
            ty0 = curr[1] + uy0 * t_len
            tx1 = curr[0] + ux1 * t_len
            ty1 = curr[1] + uy1 * t_len

            # Arc centre: offset inward perpendicular to each tangent by r
            # Inward normal to edge 0 (left-perpendicular of ux0,uy0)
            # We pick the normal that points toward the bisector
            bx = ux0 + ux1
            by = uy0 + uy1  # noqa: E702
            b_len = math.hypot(bx, by)
            if b_len < 1e-12:
                outline.append(curr)
                continue
            bx /= b_len
            by /= b_len  # noqa: E702

            # Distance from corner to centre along bisector
            dist_centre = r / math.sin(half_angle)
            cx = curr[0] + bx * dist_centre
            cy = curr[1] + by * dist_centre

            # Arc angles
            angle_start = math.atan2(ty0 - cy, tx0 - cx)
            angle_end = math.atan2(ty1 - cy, tx1 - cx)

            # Determine sweep direction (CCW or CW) matching the polygon winding
            # We build the sweep so the arc goes from tx0 to tx1 curving away from
            # the corner. Cross-product of (ux0) × (ux1) gives winding.
            cross = ux0 * uy1 - uy0 * ux1
            if cross >= 0:
                # CCW polygon corner → CW arc (concave fillet)
                sweep = angle_end - angle_start
                if sweep > 0:
                    sweep -= 2 * math.pi
            else:
                # CW polygon corner → CCW arc
                sweep = angle_end - angle_start
                if sweep < 0:
                    sweep += 2 * math.pi

            # Emit tangent point, then arc samples (not including start)
            outline.append((tx0, ty0))
            for k in range(1, self.arc_segments + 1):
                a = angle_start + sweep * k / self.arc_segments
                outline.append((cx + r * math.cos(a), cy + r * math.sin(a)))

        return outline

    def get_profile_points(self) -> List[Tuple[float, float]]:
        return self._apply_transform(self._build_outline())

    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        return _build_polyline_profile(ifc_file, self.get_profile_points(), self.name)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "profile_type": self.profile_type,
            "points": list(self.points),
            "radius": self.radii,
            "arc_segments": self.arc_segments,
            **self._transform_dict(),
        }
        if self.name is not None:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoundedPolygonProfile":
        r, ox, oy, anch = cls._transform_from_dict(d, default_anchor="c")
        return cls(
            points=d["points"],
            radius=d.get("radius", 0.0),
            name=d.get("name"),
            arc_segments=d.get("arc_segments", 8),
            rotation=r,
            offset_x=ox,
            offset_y=oy,
        )


# ---------------------------------------------------------------------------
# RectangleProfile
# ---------------------------------------------------------------------------


class RectangleProfile(Profile):
    """
    Parametric rectangle profile.

    Emits ``IfcRectangleProfileDef`` (native IFC parametric type).

    Args:
        x_dim:    Width (m).
        y_dim:    Height (m).
        name:     Optional profile name.
        anchor:   Origin anchor (default 'c' = centre).
        rotation: CCW rotation around anchor (radians, default 0).
        offset_x: Additional X translation (m, default 0).
        offset_y: Additional Y translation (m, default 0).
    """

    profile_type = "rectangle"

    def __init__(
        self,
        x_dim: float,
        y_dim: float,
        name: Optional[str] = None,
        anchor: str = "c",
        rotation: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        if x_dim <= 0:
            raise ValueError("x_dim must be positive")
        if y_dim <= 0:
            raise ValueError("y_dim must be positive")
        self.x_dim = float(x_dim)
        self.y_dim = float(y_dim)
        self.name = name
        super().__init__()
        self._init_transform(rotation, offset_x, offset_y, anchor)

    @property
    def area(self) -> float:
        return self.x_dim * self.y_dim

    def get_profile_points(self) -> List[Tuple[float, float]]:
        hx = self.x_dim / 2
        hy = self.y_dim / 2
        pts = [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]
        bbox_sw = (-hx, -hy)
        return self._apply_transform(pts, bbox=(self.x_dim, self.y_dim), bbox_sw=bbox_sw)

    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        hx = self.x_dim / 2
        hy = self.y_dim / 2
        bbox_sw = (-hx, -hy)
        pos = self._ifc_placement_2d(ifc_file, bbox=(self.x_dim, self.y_dim), bbox_sw=bbox_sw)
        return ifc_file.create_entity(
            "IfcRectangleProfileDef",
            ProfileType="AREA",
            ProfileName=self.name,
            Position=pos,
            XDim=self.x_dim,
            YDim=self.y_dim,
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "profile_type": self.profile_type,
            "x_dim": self.x_dim,
            "y_dim": self.y_dim,
            **self._transform_dict(),
        }
        if self.name is not None:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RectangleProfile":
        r, ox, oy, anch = cls._transform_from_dict(d, default_anchor="c")
        return cls(
            x_dim=d["x_dim"],
            y_dim=d["y_dim"],
            name=d.get("name"),
            anchor=anch,
            rotation=r,
            offset_x=ox,
            offset_y=oy,
        )


# ---------------------------------------------------------------------------
# CircleProfile
# ---------------------------------------------------------------------------


class CircleProfile(Profile):
    """
    Parametric solid circle profile.

    Emits ``IfcCircleProfileDef`` (native IFC parametric type).

    Args:
        radius:   Circle radius (m).
        name:     Optional profile name.
        anchor:   Origin anchor (default 'c' = centre).
        offset_x: Additional X translation (m, default 0).
        offset_y: Additional Y translation (m, default 0).

    Note: ``rotation`` has no effect on a circle but is accepted for API
    consistency and is round-tripped through to_dict/from_dict.
    """

    profile_type = "circle"

    def __init__(
        self,
        radius: float,
        name: Optional[str] = None,
        anchor: str = "c",
        rotation: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        if radius <= 0:
            raise ValueError("radius must be positive")
        self.radius = float(radius)
        self.name = name
        super().__init__()
        self._init_transform(rotation, offset_x, offset_y, anchor)

    @property
    def area(self) -> float:
        return math.pi * self.radius**2

    def _bbox(self) -> Tuple[float, float]:
        d = self.radius * 2
        return d, d

    def _bbox_sw(self) -> Tuple[float, float]:
        return -self.radius, -self.radius

    def get_profile_points(self) -> List[Tuple[float, float]]:
        """Approximate circle as 32-segment polygon."""
        n = 32
        pts = [
            (
                self.radius * math.cos(2 * math.pi * i / n),
                self.radius * math.sin(2 * math.pi * i / n),
            )
            for i in range(n)
        ]
        return self._apply_transform(pts, bbox=self._bbox(), bbox_sw=self._bbox_sw())

    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        pos = self._ifc_placement_2d(ifc_file, bbox=self._bbox(), bbox_sw=self._bbox_sw())
        return ifc_file.create_entity(
            "IfcCircleProfileDef",
            ProfileType="AREA",
            ProfileName=self.name,
            Position=pos,
            Radius=self.radius,
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "profile_type": self.profile_type,
            "radius": self.radius,
            **self._transform_dict(),
        }
        if self.name is not None:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CircleProfile":
        r, ox, oy, anch = cls._transform_from_dict(d, default_anchor="c")
        return cls(
            radius=d["radius"],
            name=d.get("name"),
            anchor=anch,
            rotation=r,
            offset_x=ox,
            offset_y=oy,
        )


# ---------------------------------------------------------------------------
# HollowCircleProfile  (tube / CHS)
# ---------------------------------------------------------------------------


class HollowCircleProfile(Profile):
    """
    Parametric hollow circle (circular hollow section / tube) profile.

    Emits ``IfcCircleHollowProfileDef`` (native IFC parametric type).

    Args:
        radius:         Outer radius (m).
        wall_thickness: Wall thickness (m).
        name:           Optional profile name.
        anchor:         Origin anchor (default 'c' = centre).
        offset_x:       Additional X translation (m, default 0).
        offset_y:       Additional Y translation (m, default 0).

    Note: ``rotation`` has no effect on a circular section but is accepted
    for API consistency.
    """

    profile_type = "hollow_circle"

    def __init__(
        self,
        radius: float,
        wall_thickness: float,
        name: Optional[str] = None,
        anchor: str = "c",
        rotation: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        if radius <= 0:
            raise ValueError("radius must be positive")
        if wall_thickness <= 0 or wall_thickness >= radius:
            raise ValueError("wall_thickness must be > 0 and < radius")
        self.radius = float(radius)
        self.wall_thickness = float(wall_thickness)
        self.name = name
        super().__init__()
        self._init_transform(rotation, offset_x, offset_y, anchor)

    @property
    def inner_radius(self) -> float:
        return self.radius - self.wall_thickness

    @property
    def area(self) -> float:
        return math.pi * (self.radius**2 - self.inner_radius**2)

    def _bbox(self) -> Tuple[float, float]:
        d = self.radius * 2
        return d, d

    def _bbox_sw(self) -> Tuple[float, float]:
        return -self.radius, -self.radius

    def get_profile_points(self) -> List[Tuple[float, float]]:
        """Outer circle approximated as 32-segment polygon (inner ring ignored)."""
        n = 32
        pts = [
            (
                self.radius * math.cos(2 * math.pi * i / n),
                self.radius * math.sin(2 * math.pi * i / n),
            )
            for i in range(n)
        ]
        return self._apply_transform(pts, bbox=self._bbox(), bbox_sw=self._bbox_sw())

    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        pos = self._ifc_placement_2d(ifc_file, bbox=self._bbox(), bbox_sw=self._bbox_sw())
        return ifc_file.create_entity(
            "IfcCircleHollowProfileDef",
            ProfileType="AREA",
            ProfileName=self.name,
            Position=pos,
            Radius=self.radius,
            WallThickness=self.wall_thickness,
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "profile_type": self.profile_type,
            "radius": self.radius,
            "wall_thickness": self.wall_thickness,
            **self._transform_dict(),
        }
        if self.name is not None:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "HollowCircleProfile":
        r, ox, oy, anch = cls._transform_from_dict(d, default_anchor="c")
        return cls(
            radius=d["radius"],
            wall_thickness=d["wall_thickness"],
            name=d.get("name"),
            anchor=anch,
            rotation=r,
            offset_x=ox,
            offset_y=oy,
        )
