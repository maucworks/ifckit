"""
ifckit.geometry.primitives
==========================

Core geometry primitives: Vec, Plane, Line, Arc, Polyline.

No external dependencies beyond the standard library.
"""

from __future__ import annotations

import math
import warnings
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Sequence, Tuple

if TYPE_CHECKING:
    from ifckit.geometry.transform import Transform


class Vec:
    """
    Lightweight 3D vector / point.

    Operators:
        a + b           addition
        a - b           subtraction
        a * scalar      scalar multiply
        scalar * a      (reflected)
        a / scalar      scalar divide
        -a              negate
        abs(a)          length
        a @ b           dot product
        a ** b          cross product
        x, y, z = a     unpacking
        a[i]            index access (0,1,2)
        a == b          exact equality
        a.equals(b, tol) fuzzy equality
    """

    __slots__ = ("x", "y", "z")

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    # --- constructors -------------------------------------------------------

    @classmethod
    def from_tuple(cls, t: Sequence[float]) -> "Vec":
        return cls(t[0], t[1], t[2])

    # --- arithmetic ---------------------------------------------------------

    def __add__(self, other: "Vec") -> "Vec":
        return Vec(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec") -> "Vec":
        return Vec(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vec":
        return Vec(self.x * scalar, self.y * scalar, self.z * scalar)

    def __rmul__(self, scalar: float) -> "Vec":
        return self.__mul__(scalar)

    def __truediv__(self, scalar: float) -> "Vec":
        return Vec(self.x / scalar, self.y / scalar, self.z / scalar)

    def __neg__(self) -> "Vec":
        return Vec(-self.x, -self.y, -self.z)

    def __abs__(self) -> float:
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)

    def __matmul__(self, other: "Vec") -> float:
        """Dot product: a @ b"""
        return self.x * other.x + self.y * other.y + self.z * other.z

    def __pow__(self, other: "Vec") -> "Vec":
        """Cross product: a ** b"""
        return Vec(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def __iter__(self) -> Iterator[float]:
        yield self.x
        yield self.y
        yield self.z

    def __getitem__(self, index: int) -> float:
        return (self.x, self.y, self.z)[index]

    def __len__(self) -> int:
        return 3

    def __bool__(self) -> bool:
        return self.x != 0.0 or self.y != 0.0 or self.z != 0.0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vec):
            return False
        return self.x == other.x and self.y == other.y and self.z == other.z

    def __hash__(self) -> int:
        return hash((self.x, self.y, self.z))

    def __repr__(self) -> str:
        return f"Vec({self.x}, {self.y}, {self.z})"

    # --- vector math --------------------------------------------------------

    def equals(self, other: "Vec", tol: float = 1e-6) -> bool:
        return abs(self - other) <= tol

    def dot(self, other: "Vec") -> float:
        return self @ other

    def cross(self, other: "Vec") -> "Vec":
        return self**other

    def length(self) -> float:
        return abs(self)

    def length_squared(self) -> float:
        return self @ self

    def normalized(self) -> "Vec":
        mag = abs(self)
        if mag < 1e-12:
            raise ValueError("Cannot normalize a zero-length vector")
        return self / mag

    def lerp(self, other: "Vec", t: float) -> "Vec":
        return self + (other - self) * t

    def distance_to(self, other: "Vec") -> float:
        return abs(other - self)

    # --- angles -------------------------------------------------------------

    def angle_to(self, other: "Vec") -> float:
        """Unsigned angle in radians (0..pi)."""
        cos_a = self.normalized() @ other.normalized()
        return math.acos(max(-1.0, min(1.0, cos_a)))

    def bisect_to(self, other: "Vec") -> "Vec":
        """
        Return the normalized bisector direction between self and other.

        self and other should be direction vectors (non-zero).
        Returns a normalized Vec pointing in the averaged direction.
        For collinear vectors pointing opposite directions (sum ≈ 0),
        raises ValueError because the sum cannot be normalized.
        Caller must guard against anti-parallel input vectors.
        """
        return (self.normalized() + other.normalized()).normalized()

    def signed_angle_to(self, other: "Vec", axis: "Vec") -> float:
        """Signed angle in radians around axis, right-hand rule (-pi..pi)."""
        n = axis.normalized()
        a = self.normalized()
        b = other.normalized()
        return math.atan2((a**b) @ n, a @ b)

    def angle_to_plane(self, plane_normal: "Vec") -> float:
        """Angle between self and a plane defined by its normal (-pi/2..pi/2)."""
        sin_a = self.normalized() @ plane_normal.normalized()
        return math.asin(max(-1.0, min(1.0, sin_a)))

    # --- rotation -----------------------------------------------------------

    def rotate_around(self, axis: "Vec", angle: float) -> "Vec":
        """
        Rotate self around axis by angle (radians), Rodrigues' formula.
        axis need not be normalised.
        """
        k = axis.normalized()
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        return self * cos_a + (k**self) * sin_a + k * (k @ self) * (1 - cos_a)

    # --- affine transforms --------------------------------------------------

    def transformed(self, t: "Transform") -> "Vec":
        """Apply a 4×4 affine transform to this point."""
        return t.apply(self)

    def mirrored(self, plane: "Plane") -> "Vec":
        """Mirror over an arbitrary plane. Returns a new Vec."""
        from ifckit.geometry.transform import Transform

        return Transform.reflection(plane).apply(self)

    def translated(self, delta: "Vec") -> "Vec":
        """Translate by *delta*. Returns a new Vec."""
        from ifckit.geometry.transform import Transform

        return Transform.translation(delta).apply(self)

    def rotated(self, axis: "Vec", angle: float) -> "Vec":
        """Rotate around *axis* by *angle* radians. Returns a new Vec."""
        from ifckit.geometry.transform import Transform

        return Transform.rotation(axis, angle).apply(self)

    def scaled(
        self, sx: float, sy: "Optional[float]" = None, sz: "Optional[float]" = None
    ) -> "Vec":
        """Scale by *sx*, *sy*, *sz* (default sy/sz = sx). Returns a new Vec."""
        from ifckit.geometry.transform import Transform

        if sy is None:
            sy = sx
        if sz is None:
            sz = sx
        return Transform.scaling(sx, sy, sz).apply(self)

    def copy(self) -> "Vec":
        """Return an independent copy."""
        return Vec(self.x, self.y, self.z)

    # --- conversion ---------------------------------------------------------

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "Vec":
        return cls(d["x"], d["y"], d["z"])


# ---------------------------------------------------------------------------
# Plane  (right-handed frame: origin, x_axis, y_axis; z = x ** y)
# ---------------------------------------------------------------------------


class Plane:
    """
    A right-handed coordinate frame in 3D space.

        z_axis = x_axis ** y_axis

    Useful as an IFC local placement and as a profile orientation.
    """

    __slots__ = ("origin", "x_axis", "y_axis")

    def __init__(self, origin: "Vec", x_axis: "Vec", y_axis: "Vec") -> None:
        x_norm = x_axis.normalized()
        y_norm = y_axis.normalized()
        dot = x_norm @ y_norm
        if abs(dot) > 1e-6:
            raise ValueError(
                f"Plane x_axis and y_axis must be orthogonal (dot={dot:.2e}). "
                f"Use Plane.from_origin_and_normal() to derive from a normal vector."
            )
        self.origin = origin
        self.x_axis = x_norm
        self.y_axis = y_norm

    @property
    def z_axis(self) -> "Vec":
        return (self.x_axis**self.y_axis).normalized()

    @classmethod
    def world_xy(cls) -> "Plane":
        """Standard XY plane at origin (normal = +Z)."""
        return cls(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))

    @classmethod
    def world_xz(cls) -> "Plane":
        """XZ plane at origin (normal = -Y).

        2D ``(X, Y)`` maps to 3D ``(X, 0, Y)`` — ``X`` becomes world-X,
        ``Y`` becomes world-Z.
        """
        return cls(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))

    @classmethod
    def world_yz(cls) -> "Plane":
        """YZ plane at origin (normal = +X)."""
        return cls(Vec(0, 0, 0), Vec(0, 1, 0), Vec(0, 0, 1))

    @classmethod
    def from_origin_and_normal(
        cls,
        origin: "Vec",
        normal: "Vec",
        ref_direction: Optional["Vec"] = None,
    ) -> "Plane":
        """
        Construct a plane from an origin and normal (z_axis = normal).

        Args:
            origin:  Point on the plane.
            normal:  Z-axis (normal to the plane).  For sectioned spine this is
                     the extrusion direction / spine tangent.
            ref_direction:  Optional reference direction for the X-axis.  The
                     X-axis is the projection of ref_direction onto the plane
                     (made orthogonal to normal).  When omitted, the least-aligned
                     world axis is chosen (can cause XY flipping when normal
                     changes gradually).
        """
        n = normal.normalized()
        if ref_direction is not None:
            # Project ref_direction onto the plane (Gram-Schmidt against n)
            r = ref_direction.normalized()
            x_raw = r - n * (r @ n)
            # If projection is degenerate (ref_direction parallel to n), fall through
            if x_raw.length() > 0.1:
                x = x_raw.normalized()
                y = (n**x).normalized()
                return cls(origin, x, y)
        # Fallback: pick world axis least aligned with n
        world_axes = [Vec(1, 0, 0), Vec(0, 1, 0), Vec(0, 0, 1)]
        ref = min(world_axes, key=lambda a: abs(n @ a))
        x = (n**ref).normalized()
        y = (n**x).normalized()
        return cls(origin, x, y)

    @classmethod
    def from_tangent(
        cls,
        origin: "Vec",
        tangent: "Vec",
        world_up: Optional["Vec"] = None,
    ) -> "Plane":
        """
        Construct a frame at origin where x_axis = tangent direction.
        Used for beam/column/bridge element placement along a path.
        y_axis is derived from world_up (default: +Z).
        """
        t = tangent.normalized()
        up = (world_up or Vec(0, 0, 1)).normalized()
        if abs(t @ up) > 0.999:
            # tangent nearly parallel to up — use +Y as fallback
            up = Vec(0, 1, 0)
        y = (up - t * (t @ up)).normalized()
        return cls(origin, t, y)

    def transform_point(self, local: "Vec") -> "Vec":
        """Transform a point from local frame coordinates to world coordinates."""
        return self.origin + self.x_axis * local.x + self.y_axis * local.y + self.z_axis * local.z

    def transform_vector(self, local: "Vec") -> "Vec":
        """Transform a vector (no translation) from local to world."""
        return self.x_axis * local.x + self.y_axis * local.y + self.z_axis * local.z

    def closest_point(self, world_pt: "Vec") -> "Vec":
        """Project a world point onto the plane (closest point on plane surface)."""
        d = world_pt - self.origin
        return world_pt - self.z_axis * (d @ self.z_axis)

    def to_local(self, world_pt: "Vec") -> "Vec":
        """Express a world point in local frame coordinates."""
        d = world_pt - self.origin
        return Vec(d @ self.x_axis, d @ self.y_axis, d @ self.z_axis)

    def to_local_vector(self, world_vec: "Vec") -> "Vec":
        """Express a world vector in local frame coordinates (no translation)."""
        return Vec(world_vec @ self.x_axis, world_vec @ self.y_axis, world_vec @ self.z_axis)

    def in_frame(self, target_frame: "Plane") -> "Plane":
        """Express this plane in target_frame's local coordinates."""
        return Plane(
            target_frame.to_local(self.origin),
            target_frame.to_local_vector(self.x_axis),
            target_frame.to_local_vector(self.y_axis),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin": self.origin.to_dict(),
            "x_axis": self.x_axis.to_dict(),
            "y_axis": self.y_axis.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Plane":
        return cls(
            origin=Vec.from_dict(d["origin"]),
            x_axis=Vec.from_dict(d["x_axis"]),
            y_axis=Vec.from_dict(d["y_axis"]),
        )

    def transformed(self, t: "Transform") -> "Plane":
        """Apply a 4×4 affine transform. Returns a new Plane."""
        return Plane(
            t.apply(self.origin),
            t.apply_vector(self.x_axis),
            t.apply_vector(self.y_axis),
        )

    def mirrored(self, plane: "Plane") -> "Plane":
        """Mirror over an arbitrary plane. Returns a new Plane."""
        from ifckit.geometry.transform import Transform

        return self.transformed(Transform.reflection(plane))

    def translated(self, delta: "Vec") -> "Plane":
        """Translate by *delta* (axes unchanged). Returns a new Plane."""
        return Plane(self.origin + delta, self.x_axis, self.y_axis)

    def rotated(self, axis: "Vec", angle: float) -> "Plane":
        """Rotate around *axis* by *angle* radians. Returns a new Plane."""
        from ifckit.geometry.transform import Transform

        t = Transform.rotation(axis, angle)
        return Plane(t.apply(self.origin), t.apply_vector(self.x_axis), t.apply_vector(self.y_axis))

    def copy(self) -> "Plane":
        """Return an independent copy."""
        return Plane(self.origin.copy(), self.x_axis.copy(), self.y_axis.copy())

    def __repr__(self) -> str:
        return f"Plane(origin={self.origin}, x={self.x_axis}, y={self.y_axis})"


# ---------------------------------------------------------------------------
# Line3
# ---------------------------------------------------------------------------


class Line:
    """A finite line segment from start to end."""

    __slots__ = ("start", "end")

    def __init__(self, start: "Vec", end: "Vec") -> None:
        self.start = start
        self.end = end

    @property
    def direction(self) -> "Vec":
        return (self.end - self.start).normalized()

    def tangent_at_start(self) -> "Vec":
        """For compatibility with Arc - returns the direction of the line."""
        return self.direction

    def tangent_at_end(self) -> "Vec":
        """For compatibility with Arc - returns the direction of the line."""
        return self.direction

    def tangent_at(self, t: float) -> "Vec":
        """Direction is constant along a line; t is ignored."""
        return self.direction

    def reverse(self) -> "Line":
        return Line(self.end, self.start)

    def transformed(self, t: "Transform") -> "Line":
        """Apply a 4×4 affine transform. Returns a new Line."""
        return Line(t.apply(self.start), t.apply(self.end))

    def mirrored(self, plane: "Plane") -> "Line":
        """Mirror over an arbitrary plane. Returns a new Line."""
        from ifckit.geometry.transform import Transform

        return self.transformed(Transform.reflection(plane))

    def translated(self, delta: "Vec") -> "Line":
        """Translate by *delta*. Returns a new Line."""
        return Line(self.start + delta, self.end + delta)

    def rotated(self, axis: "Vec", angle: float) -> "Line":
        """Rotate around *axis* by *angle* radians. Returns a new Line."""
        from ifckit.geometry.transform import Transform

        return self.transformed(Transform.rotation(axis, angle))

    def scaled(
        self, sx: float, sy: "Optional[float]" = None, sz: "Optional[float]" = None
    ) -> "Line":
        """Scale by *sx*, *sy*, *sz*. Returns a new Line."""
        from ifckit.geometry.transform import Transform

        if sy is None:
            sy = sx
        if sz is None:
            sz = sx
        return self.transformed(Transform.scaling(sx, sy, sz))

    def copy(self) -> "Line":
        """Return an independent copy."""
        return Line(self.start.copy(), self.end.copy())

    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)

    @property
    def midpoint(self) -> "Vec":
        return self.start.lerp(self.end, 0.5)

    def point_at(self, t: float) -> "Vec":
        """t=0 → start, t=1 → end."""
        return self.start.lerp(self.end, t)

    def to_polyline(self) -> "Polyline":
        return Polyline([self.start, self.end])

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "line", "start": self.start.to_dict(), "end": self.end.to_dict()}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Line":
        return cls(Vec.from_dict(d["start"]), Vec.from_dict(d["end"]))

    def __repr__(self) -> str:
        return f"Line({self.start} → {self.end})"


# ---------------------------------------------------------------------------
# Arc3
# ---------------------------------------------------------------------------


class Arc:
    """
    A circular arc in 3D space.

    Defined by:
        center  — center point
        normal  — axis of rotation (right-hand rule defines sweep direction)
        start   — start point (must lie on the circle)
        angle   — sweep angle in radians (positive = CCW around normal)
        radius  — derived from |start - center|

    The end point is computed from center, radius, normal, and angle.
    """

    __slots__ = ("center", "normal", "start", "angle")

    def __init__(
        self,
        center: "Vec",
        normal: "Vec",
        start: "Vec",
        angle: float,
    ) -> None:
        self.center = center
        self.normal = normal.normalized()
        self.start = start
        self.angle = angle  # radians, signed

    @property
    def radius(self) -> float:
        return self.start.distance_to(self.center)

    @property
    def end(self) -> "Vec":
        radial = self.start - self.center
        return self.center + radial.rotate_around(self.normal, self.angle)

    @property
    def midpoint(self) -> "Vec":
        radial = self.start - self.center
        return self.center + radial.rotate_around(self.normal, self.angle / 2)

    def reverse(self) -> "Arc":
        """Return a new arc traversing the same path in opposite direction.

        The reversed arc starts at self.end and ends at self.start,
        with angle negated to indicate opposite traversal direction.
        """
        return Arc(self.center, self.normal, self.end, -self.angle)

    def transformed(self, t: "Transform") -> "Arc":
        """Apply a 4×4 affine transform.

        Under uniform transforms (rotation, translation, reflection, uniform
        scale) the arc stays a circular arc.  Under non-uniform scale the arc
        would become an ellipse — raises ValueError; use ``to_path()`` instead.
        """
        if not t.is_uniform_scale():
            raise ValueError(
                "Arc.transformed() does not support non-uniform scale "
                "(would produce an ellipse). Use arc.to_path().transformed(t) instead."
            )
        new_center = t.apply(self.center)
        new_start = t.apply(self.start)
        new_normal = t.apply_vector(self.normal)
        return Arc(new_center, new_normal, new_start, self.angle)

    def mirrored(self, plane: "Plane") -> "Arc":
        """Mirror over an arbitrary plane. Returns a new Arc."""
        from ifckit.geometry.transform import Transform

        return self.transformed(Transform.reflection(plane))

    def translated(self, delta: "Vec") -> "Arc":
        """Translate by *delta*. Returns a new Arc."""
        return Arc(self.center + delta, self.normal, self.start + delta, self.angle)

    def rotated(self, axis: "Vec", angle: float) -> "Arc":
        """Rotate around *axis* by *angle* radians. Returns a new Arc."""
        from ifckit.geometry.transform import Transform

        r = Transform.rotation(axis, angle)
        c = r.apply(self.center)
        n = r.apply_vector(self.normal)
        s = r.apply(self.start)
        return Arc(c, n, s, self.angle)

    def scaled(
        self, sx: float, sy: "Optional[float]" = None, sz: "Optional[float]" = None
    ) -> "Arc":
        """Scale by *sx*, *sy*, *sz*. Non-uniform raises ValueError."""

        from ifckit.geometry.transform import Transform

        if sy is None:
            sy = sx
        if sz is None:
            sz = sx
        t = Transform.scaling(sx, sy, sz)
        return self.transformed(t)

    def copy(self) -> "Arc":
        """Return an independent copy."""
        return Arc(self.center.copy(), self.normal.copy(), self.start.copy(), self.angle)

    def point_at(self, t: float) -> "Vec":
        """t=0 → start, t=1 → end."""
        radial = self.start - self.center
        return self.center + radial.rotate_around(self.normal, self.angle * t)

    def sample(self, angle_step_deg: float = 5.0) -> List["Vec"]:
        """
        Sample the arc into a list of "Vec" points.
        Includes start and end; step size in degrees.
        """
        step = math.radians(angle_step_deg)
        n_steps = max(1, int(abs(self.angle) / step))
        return [self.point_at(i / n_steps) for i in range(n_steps + 1)]

    @property
    def length(self) -> float:
        return abs(self.angle) * self.radius

    def tangent_at_start(self) -> "Vec":
        radial = (self.start - self.center).normalized()
        sign = 1.0 if self.angle >= 0 else -1.0
        return (self.normal**radial) * sign

    def tangent_at_end(self) -> "Vec":
        radial = (self.end - self.center).normalized()
        sign = 1.0 if self.angle >= 0 else -1.0
        return (self.normal**radial) * sign

    def tangent_at(self, t: float) -> "Vec":
        """t=0 -> start tangent, t=1 -> end tangent."""
        radial = (self.point_at(t) - self.center).normalized()
        sign = 1.0 if self.angle >= 0 else -1.0
        return (self.normal**radial) * sign

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "arc",
            "center": self.center.to_dict(),
            "normal": self.normal.to_dict(),
            "start": self.start.to_dict(),
            "angle": self.angle,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Arc":
        return cls(
            Vec.from_dict(d["center"]),
            Vec.from_dict(d["normal"]),
            Vec.from_dict(d["start"]),
            d["angle"],
        )

    def __repr__(self) -> str:
        return (
            f"Arc(center={self.center}, r={self.radius:.3f}, angle={math.degrees(self.angle):.1f}°)"
        )


# ---------------------------------------------------------------------------
# "Polyline"
# ---------------------------------------------------------------------------


class Polyline:
    """An ordered sequence of "Vec" points forming a polyline.

    .. deprecated::
        Use :class:`Path` instead. ``Polyline`` is retained for backward
        compatibility with existing callers (``sample()``, bridge builder, etc.)
        and will be removed in a future version.
    """

    def __init__(self, points: List["Vec"], closed: bool = False) -> None:
        warnings.warn("Polyline is deprecated; use Path instead.", DeprecationWarning, stacklevel=2)
        self.points = list(points)
        self.closed = closed

    @classmethod
    def from_tuples(
        cls, tuples: List[Tuple[float, float, float]], closed: bool = False
    ) -> "Polyline":
        return cls([Vec(*t) for t in tuples], closed=closed)

    @property
    def is_closed(self) -> bool:
        if self.closed:
            return True
        if len(self.points) >= 2:
            return self.points[0].equals(self.points[-1])
        return False

    @property
    def length(self) -> float:
        total = 0.0
        pts = self.points
        n = len(pts) - 1 if not self.closed else len(pts)
        for i in range(n):
            total += pts[i].distance_to(pts[(i + 1) % len(pts)])
        return total

    def close(self) -> "Polyline":
        """Return a closed copy (appends first point if not already closed)."""
        pts = list(self.points)
        if not pts:
            return self
        if not pts[0].equals(pts[-1]):
            pts.append(pts[0])
        return Polyline(pts, closed=True)

    def ensure_ccw(self, normal: Optional["Vec"] = None) -> "Polyline":
        """
        Return a copy with vertices wound counter-clockwise around normal.
        If normal is None, uses the polygon's own computed normal (z_axis of best-fit plane).
        Requires the polyline to be planar and closed.
        """
        n = normal or _polygon_normal(self.points)
        if _signed_area(self.points, n) < 0:
            return Polyline(list(reversed(self.points)), closed=self.closed)
        return Polyline(list(self.points), closed=self.closed)

    def project_to_plane(self, plane: Plane) -> "Polyline":
        """Project all points to local 2D (x,y) coordinates of a plane."""
        return Polyline(
            [Vec(plane.to_local(p).x, plane.to_local(p).y, 0.0) for p in self.points],
            closed=self.closed,
        )

    def __len__(self) -> int:
        return len(self.points)

    def __iter__(self) -> Iterator["Vec"]:
        return iter(self.points)

    def __repr__(self) -> str:
        return f"Polyline({len(self.points)} pts, closed={self.is_closed})"


# ---------------------------------------------------------------------------
# Polygon helpers  (used by Polyline and Path)
# ---------------------------------------------------------------------------


def _polygon_normal(points: "List[Vec]") -> "Vec":
    """Newell's method: compute the normal of a (possibly non-planar) polygon."""
    n = Vec(0, 0, 0)
    count = len(points)
    for i in range(count):
        cur = points[i]
        nxt = points[(i + 1) % count]
        n = n + Vec(
            (cur.y - nxt.y) * (cur.z + nxt.z),
            (cur.z - nxt.z) * (cur.x + nxt.x),
            (cur.x - nxt.x) * (cur.y + nxt.y),
        )
    return n.normalized()


def _signed_area(points: "List[Vec]", normal: "Vec") -> float:
    """Signed area of a polygon projected onto the plane defined by normal."""
    area = Vec(0, 0, 0)
    count = len(points)
    for i in range(count):
        area = area + (points[i] ** points[(i + 1) % count])
    return (area @ normal) * 0.5
