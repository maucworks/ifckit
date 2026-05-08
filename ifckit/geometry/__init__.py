"""
ifckit.geometry
===============

Framework-agnostic geometry primitives for IFC construction.
No Rhino, no Grasshopper, no external dependencies beyond the standard library.

Classes:
    Vec      — 3D vector / point
    Plane    — origin + two axes (right-handed frame)
    Line     — start + end Vec
    Arc      — center, normal, start, end, radius
    Polyline — ordered list of Vec (open or closed)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, NamedTuple, Optional, Sequence, Tuple

if TYPE_CHECKING:
    import ifcopenshell

# ---------------------------------------------------------------------------
# "Vec"
# ---------------------------------------------------------------------------


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
        if mag == 0.0:
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
        returns a zero Vec — caller must handle this case.
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
        """Standard XY plane at origin."""
        return cls(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))

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
            x = (r - n * (r @ n)).normalized()
            # If projection is degenerate (ref_direction parallel to n), fall through
            if x.length() > 0.1:
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
        x = (t**y).normalized()  # noqa: F841
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

    def reverse(self) -> "Line":
        return Line(self.end, self.start)

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
        return Arc(self.center, -self.normal, self.end, self.angle)

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
# "Path"  — mixed polyline + arc path (for bridge alignments)
# ---------------------------------------------------------------------------


class Path:
    """
    A G1-continuous path made of Line3 and Arc3 segments.
    Used for bridge alignment, extrusion paths, etc.

    NOTE ON isinstance() VS type-name CHECKS
    -----------------------------------------
    This class uses ``isinstance(seg, Arc)`` / ``isinstance(seg, Line)`` throughout.
    This is intentional and correct. ``Arc`` and ``Line`` are defined in this same
    module (``ifckit.geometry``). They are *not* user-defined subclasses and are
    *not* subject to Rhino/Grasshopper module-reload identity splits.

    The ``type(x).__name__ == "..."`` pattern is only needed for ``PendingElement``
    subclasses (``ifckit.elements.*``) because those live in user-facing modules
    that Grasshopper scripts may reload, creating a new class object for the same
    logical type. Geometry primitives (Arc, Line, Vec, Plane, …) are internal
    infrastructure and are never reloaded independently.

    Do NOT replace ``isinstance`` here with string-name checks.
    """

    def __init__(self, plane: Optional["Plane"] = None) -> None:
        self._segments: List[Line | Arc] = []
        self._plane: Optional["Plane"] = plane
        self._holes: List["Path"] = []

    @property
    def holes(self) -> "List[Path]":
        """Inner curves (holes) for profile-with-voids. Read-only list copy."""
        return list(self._holes)

    def with_hole(self, inner: "Path") -> "Path":
        """Return a shallow copy of this Path with ``inner`` added as a hole.

        The original path is not modified.  Holes represent inner curves
        for ``IfcArbitraryProfileDefWithVoids``.

        Args:
            inner:  A closed Path describing the void boundary (CW winding
                    expected by IFC for inner curves, but ``profile_from_points``
                    will enforce this automatically).

        Returns:
            New Path with same outer segments and one extra hole.
        """
        import copy

        new_path = Path(plane=self._plane)
        new_path._segments = [copy.copy(seg) for seg in self._segments]
        new_path._holes = list(self._holes) + [inner]
        return new_path

    @property
    def segments(self) -> List[Line | Arc]:
        return list(self._segments)

    def add_line(self, start: "Vec", end: "Vec") -> "Path":
        self._segments.append(Line(start, end))
        return self

    def add_arc(
        self,
        center: "Vec",
        normal: "Vec",
        start: "Vec",
        angle: float,
    ) -> "Path":
        self._segments.append(Arc(center, normal, start, angle))
        return self

    @property
    def length(self) -> float:
        return sum(seg.length for seg in self._segments)

    def sample(self, angle_step_deg: float = 5.0) -> "Polyline":
        """
        Sample the entire path into a "Polyline".
        Consecutive segment endpoints are deduplicated.
        """
        pts: List["Vec"] = []
        for seg in self._segments:
            if isinstance(seg, Arc):
                seg_pts = seg.sample(angle_step_deg)
            else:
                seg_pts = [seg.start, seg.end]
            if pts and pts[-1].equals(seg_pts[0]):
                seg_pts = seg_pts[1:]
            pts.extend(seg_pts)
        return Polyline(pts)

    def start_point(self) -> Optional["Vec"]:
        if not self._segments:
            return None
        return self._segments[0].start

    def end_point(self) -> Optional["Vec"]:
        if not self._segments:
            return None
        return self._segments[-1].end

    def start_tangent(self) -> Optional["Vec"]:
        if not self._segments:
            return None
        seg = self._segments[0]
        if isinstance(seg, Line):
            return seg.direction
        return seg.tangent_at_start()

    def tangent_at_start(self) -> Optional["Vec"]:
        """Alias for start_tangent() for compatibility with Arc interface."""
        return self.start_tangent()

    def end_tangent(self) -> Optional["Vec"]:
        if not self._segments:
            return None
        seg = self._segments[-1]
        if isinstance(seg, Line):
            return seg.direction
        return seg.tangent_at_end()

    @property
    def is_planar(self) -> bool:
        """Check if all segments lie in the same plane.

        If a reference plane was set via __init__ or make_planar(),
        that plane is authoritative and True is returned immediately.
        Otherwise, falls back to heuristic checks on segment geometry.
        """
        # Authoritative: trust explicitly set plane
        if self._plane is not None:
            return True

        # --- rest van bestaande logica ongewijzigd ---
        if len(self._segments) <= 1:
            return True

        # For arcs, check if all have the same normal.
        # isinstance is safe here — Arc is a module-internal primitive, not a reloadable user class.
        arc_normals = []
        for seg in self._segments:
            if isinstance(seg, Arc):  # safe: Arc never reloaded independently
                arc_normals.append(seg.normal)

        if arc_normals:
            # Check if all arc normals are the same (or opposite)
            first_n = arc_normals[0].normalized()
            for n in arc_normals[1:]:
                n_normalized = n.normalized()
                if abs(first_n @ n_normalized) < 0.999:
                    return False
            return True

        # For Lines only — check if all collinear.
        # isinstance is safe here — Line is a module-internal primitive,
        # not a reloadable user class.
        all_lines = all(
            isinstance(seg, Line) for seg in self._segments
        )  # safe: Line never reloaded
        if len(self._segments) >= 2 and all_lines:
            # Check if all lines are collinear (same direction or opposite)
            first_dir = self._segments[0].direction.normalized()
            for seg in self._segments[1:]:
                dir_normalized = seg.direction.normalized()
                if (
                    abs(first_dir @ dir_normalized) < 0.999
                    and abs((first_dir @ dir_normalized) + 1.0) > 0.001
                ):
                    return False
            return True

        return True  # Single segment or mixed that we can't easily verify

    @property
    def is_closed(self) -> bool:
        """True if the path's last endpoint equals its first startpoint."""
        if len(self._segments) < 2:
            return False
        sp = self.start_point()
        ep = self.end_point()
        if sp is None or ep is None:
            return False
        return sp.equals(ep, tol=1e-9)

    @classmethod
    def from_pts(
        cls,
        pts: List["Vec"],
        plane: Optional["Plane"] = None,
        closed: bool = False,
    ) -> "Path":
        """Build a Path from a list of Vec points as consecutive Line segments.

        Args:
            pts:    List of at least 2 Vec points.
            plane:  Optional reference plane stored on the Path.
            closed: If True, appends a closing segment from pts[-1] to pts[0].

        Raises:
            ValueError: If fewer than 2 points are provided.
        """
        if len(pts) < 2:
            raise ValueError("from_pts requires at least 2 points")
        path = cls(plane=plane)
        for i in range(len(pts) - 1):
            path._segments.append(Line(pts[i], pts[i + 1]))
        if closed and not pts[-1].equals(pts[0], tol=1e-9):
            path._segments.append(Line(pts[-1], pts[0]))
        return path

    @classmethod
    def rect(cls, plane: "Plane", p0: "Vec", p1: "Vec") -> "Path":
        """Build a closed rectangular Path in the given plane.

        p0 and p1 are corner points in LOCAL plane coordinates (z ignored).
        The result is a closed CCW path with 4 Line segments.
        self._plane is set to the given plane.

        Args:
            plane:  The reference plane. x_axis and y_axis define the 2D frame.
            p0:     First corner in local coords (u0, v0).
            p1:     Opposite corner in local coords (u1, v1).

        Returns:
            Closed Path with 4 segments, CCW winding relative to plane.z_axis.
        """
        u0, v0 = p0.x, p0.y
        u1, v1 = p1.x, p1.y
        # Build 4 world-space corners
        A = plane.origin + plane.x_axis * u0 + plane.y_axis * v0
        B = plane.origin + plane.x_axis * u1 + plane.y_axis * v0
        C = plane.origin + plane.x_axis * u1 + plane.y_axis * v1
        D = plane.origin + plane.x_axis * u0 + plane.y_axis * v1
        pts = [A, B, C, D]
        path = cls(plane=plane)
        for i in range(4):
            path._segments.append(Line(pts[i], pts[(i + 1) % 4]))
        return path

    @property
    def normal(self) -> Optional["Vec"]:
        """Return the normal of the plane if the path is planar."""
        if not self.is_planar:
            return None

        # Find the first Arc to get its normal.
        # isinstance is safe here — Arc is a module-internal primitive, not a reloadable user class.
        for seg in self._segments:
            if isinstance(seg, Arc):  # safe: Arc never reloaded independently
                return seg.normal

        # For Lines only: use first segment direction and derive a perpendicular.
        # isinstance is safe here — Line is a module-internal primitive,
        # not a reloadable user class.
        if len(self._segments) > 0 and isinstance(
            self._segments[0], Line
        ):  # safe: Line never reloaded
            first_dir = self._segments[0].direction.normalized()
            # Return an arbitrary perpendicular to the line direction
            if abs(first_dir.z) < 0.9:
                return (Vec(0, 0, 1) ** first_dir).normalized()
            else:
                return (Vec(0, 1, 0) ** first_dir).normalized()

        return None

    @property
    def plane(self) -> "Plane":
        """Return the plane if the path is planar, otherwise raise ValueError."""
        if not self._segments:
            raise ValueError("Path has no segments")
        if not self.is_planar:
            raise ValueError("Path is not planar")
        normal = self.normal
        if normal is None:
            raise ValueError("Cannot determine plane normal")
        origin = self.start_point()
        if origin is None:
            raise ValueError("Path has no segments")
        return Plane(origin, Vec(1, 0, 0), normal)

    @classmethod
    def assemble(
        cls,
        segments: "Sequence[Line | Arc]",
        tol: float = 1e-9,
    ) -> "List[Path]":
        """Assemble unordered segments into connected Paths.

        Thin wrapper around the module-level assemble_path() function.
        Returns a list because segments may form multiple disconnected paths.
        """
        return assemble_path(list(segments), tol=tol)

    def close(self) -> "Path":
        """Append a closing segment if not already closed. Returns self.

        No-op if already closed or fewer than 2 segments.
        """
        if self.is_closed or len(self._segments) < 1:
            return self
        sp = self.start_point()
        ep = self.end_point()
        if sp is not None and ep is not None and not ep.equals(sp, tol=1e-9):
            self._segments.append(Line(ep, sp))
        return self

    def reverse(self) -> "Path":
        """Reverse the order and direction of all segments. Returns self."""
        reversed_segs = []
        for seg in reversed(self._segments):
            if isinstance(seg, Line):
                reversed_segs.append(Line(seg.end, seg.start))
            else:  # Arc
                reversed_segs.append(Arc(seg.center, seg.normal, seg.end, -seg.angle))
        self._segments = reversed_segs
        return self

    def make_planar(self, plane: Optional["Plane"] = None) -> "Path":
        """Project all segment points onto the given plane. Returns self.

        Args:
            plane: The target plane. Falls back to self._plane if None.

        Raises:
            ValueError: If no plane is available.
        """
        target = plane or self._plane
        if target is None:
            raise ValueError("make_planar() requires a plane argument or self._plane to be set")
        new_segs = []
        for seg in self._segments:
            if isinstance(seg, Line):
                new_start = target.closest_point(seg.start)
                new_end = target.closest_point(seg.end)
                new_segs.append(Line(new_start, new_end))
            else:  # Arc
                new_center = target.closest_point(seg.center)
                new_start = target.closest_point(seg.start)
                new_segs.append(Arc(new_center, target.z_axis, new_start, seg.angle))
        self._segments = new_segs
        self._plane = target
        return self

    def assert_ccw(self, normal: Optional["Vec"] = None) -> "Path":
        """Ensure CCW winding relative to normal. Reverses if CW. Returns self.

        Requires is_closed == True.

        Args:
            normal: Reference normal. Defaults to self._plane.z_axis or self.normal.

        Raises:
            ValueError: If path is not closed.
        """
        if not self.is_closed:
            raise ValueError("assert_ccw() requires a closed path")
        n = normal
        if n is None and self._plane is not None:
            n = self._plane.z_axis
        if n is None:
            n = self.normal
        if n is None:
            raise ValueError("Cannot determine normal for CCW check")
        pts = [seg.start for seg in self._segments]
        if _signed_area(pts, n) < 0:
            self.reverse()
        return self

    def duplicate(self) -> "Path":
        """Return a deep copy of this Path. Changes to the copy do not affect the original."""
        import copy

        new_path = Path(plane=self._plane)
        new_path._segments = [copy.copy(seg) for seg in self._segments]
        new_path._holes = [h.duplicate() for h in self._holes]
        return new_path

    def project_to_plane(self, target_plane: "Plane") -> "Path":
        """Project this Path onto a target plane and return a new Path.

        Takes a 2D-style path defined in world XY coordinates
        and projects each vertex onto the target plane.

        This allows you to:
        - Define profiles with clean 90° angles in XY
        - Then project them onto a skewed plane (e.g., sloped sill)

        Each segment becomes a Line in 3D between the projected points.
        Arc segments are NOT supported in this method.

        Args:
            target_plane: The target plane (may be rotated/tilted)

        Returns:
            A new Path with segments projected onto target_plane

        Raises:
            ValueError: If any segment is an Arc
        """
        # Check for Arc segments
        for seg in self._segments:
            if isinstance(seg, Arc):
                raise ValueError("project_to_plane() does not support Arc segments")

        # Project each vertex
        origin = target_plane.origin
        x_axis = target_plane.x_axis
        y_axis = target_plane.y_axis

        projected_pts = []
        for seg in self._segments:
            pt = origin + x_axis * seg.start.x + y_axis * seg.start.y
            projected_pts.append(pt)

        # Add the closing point if closed
        if self.is_closed and len(self._segments) > 0:
            last_seg = self._segments[-1]
            pt = origin + x_axis * last_seg.end.x + y_axis * last_seg.end.y
            projected_pts.append(pt)

        # Create new path with projected points
        new_path = Path(plane=target_plane)
        for i in range(len(projected_pts) - 1):
            new_path._segments.append(Line(projected_pts[i], projected_pts[i + 1]))

        # Handle holes the same way
        for hole in self._holes:
            hole_projected = hole.project_to_plane(target_plane)
            new_path._holes.append(hole_projected)

        return new_path

    def directrix(self, ifc_file) -> "ifcopenshell.entity_instance":
        """Create an IfcCompositeCurve for use in IfcSectionedSpine.

        Converts the Path segments (Line/Arc) into IFC geometric representation.
        Each segment becomes an IfcCompositeCurveSegment.

        Requires: ifcopenshell package

        Args:
            ifc_file: ifcopenshell file instance

        Returns:
            IfcCompositeCurve entity
        """
        from ifckit.builders._geom import directrix_from_path as _directrix

        return _directrix(ifc_file, self)

    def offset(self, dist: float) -> "Path":
        """Return a new inward-offset Path at distance dist.

        Only works for closed paths made entirely of Line segments.
        Only correct for convex polygons in v1.

        Args:
            dist: Offset distance (positive = inward).

        Returns:
            New Path with offset geometry. self is not modified.

        Raises:
            ValueError: If path is not closed.
            ValueError: If any segment is an Arc.
            ValueError: If offset causes degenerate geometry (non-convex).
        """
        if not self.is_closed:
            raise ValueError("offset() requires a closed path")
        for seg in self._segments:
            if isinstance(seg, Arc):
                raise ValueError("offset() does not support Arc segments in v1")

        n = None
        if self._plane is not None:
            n = self._plane.z_axis
        if n is None:
            n = self.normal
        if n is None:
            raise ValueError("Cannot determine plane normal for offset")

        segs = self._segments

        shifted = []
        for seg in segs:
            direction = (seg.end - seg.start).normalized()
            inward_n = (n**direction).normalized()
            anchor = Vec(
                seg.start.x + inward_n.x * dist,
                seg.start.y + inward_n.y * dist,
                seg.start.z + inward_n.z * dist,
            )
            shifted.append((anchor, direction))

        new_pts = []
        n_segs = len(shifted)
        for i in range(n_segs):
            prev_i = (i - 1) % n_segs
            p1, d1 = shifted[prev_i]
            p2, d2 = shifted[i]
            pt = _line_line_intersect_2d(p1, d1, p2, d2)
            if pt is None:
                raise ValueError(
                    f"offset(): parallel adjacent edges at corner {i} — "
                    "path may be degenerate or dist too large"
                )
            new_pts.append(pt)

        return Path.from_pts(new_pts, plane=self._plane, closed=True)

    def to_profile_points(
        self,
        plane: Optional["Plane"] = None,
    ) -> List[Tuple[float, float]]:
        """Convert a closed planar Path to 2D profile points in local plane coords.

        Arc segments are sampled to polyline approximation before projection.

        Args:
            plane: Reference plane for 2D projection.
                  Falls back to self._plane if not provided.

        Returns:
            List of (x, y) tuples in local plane coordinates.

        Raises:
            ValueError: If path is not closed.
            ValueError: If no plane is available.
        """
        if not self.is_closed:
            raise ValueError("to_profile_points() requires a closed path")
        target = plane or self._plane
        if target is None:
            raise ValueError(
                "to_profile_points() requires a plane argument or self._plane to be set"
            )

        world_pts: List["Vec"] = []
        for seg in self._segments:
            if isinstance(seg, Arc):
                seg_pts = seg.sample()
            else:
                seg_pts = [seg.start, seg.end]
            if world_pts and world_pts[-1].equals(seg_pts[0], tol=1e-9):
                seg_pts = seg_pts[1:]
            world_pts.extend(seg_pts)

        if len(world_pts) >= 2 and world_pts[0].equals(world_pts[-1], tol=1e-9):
            world_pts = world_pts[:-1]

        result = []
        for pt in world_pts:
            delta = pt - target.origin
            u = delta @ target.x_axis
            v = delta @ target.y_axis
            result.append((u, v))

        return result

    def __repr__(self) -> str:
        return f"Path({len(self._segments)} segments, length={self.length:.3f})"


# ---------------------------------------------------------------------------
# Parallel transport frames along a "Path"
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# FrameField — result type for transport_frames / fixed_ref_frames
# ---------------------------------------------------------------------------


class FrameField(NamedTuple):
    """Result of parallel-transport or fixed-ref frame computation.

    Attributes:
        frames: ``List[Plane]`` — one per control / sample point.
                Z = tangent (bisector at corners), X/Y span the
                cross-section plane.
        scales: ``List[(float, str)]`` — per-vertex miter scale factors.
                Each entry is ``(scale, axis)`` where *axis* is ``'x'``,
                ``'y'``, or ``''`` (endpoints).  Apply ``scale`` to the
                profile dimension corresponding to *axis* at corners.
    """

    frames: List["Plane"]
    scales: List[Tuple[float, str]]


def _points_from_arg(
    path_or_points: "Path" | List["Vec"],
    angle_step_deg: float,
) -> List["Vec"]:
    """Extract control points from a Path or list of Vecs."""
    if isinstance(path_or_points, Path):
        sampled = path_or_points.sample(angle_step_deg)
        return sampled.points
    return list(path_or_points)


def _compute_miter_scales(
    pts: List["Vec"],
    frames: List["Plane"],
) -> List[Tuple[float, str]]:
    """Compute miter scale factor and scaling axis at each vertex.

    Interior corners get a scale > 1 applied to the profile dimension
    perpendicular to the minimal-rotation axis.  Endpoints return
    ``(1.0, '')``.
    """
    n = len(pts)
    scales: List[Tuple[float, str]] = []
    for i in range(n):
        if i == 0 or i == n - 1:
            scales.append((1.0, ""))
            continue
        ba = pts[i - 1] - pts[i]
        bc = pts[i + 1] - pts[i]
        angle = ba.angle_to(bc)
        s = 1.0 / math.sin(angle / 2) if angle > 0 else 1.0
        # corner-plane normal = BA × BC (segments: A→B = -BA, B→C = BC)
        ax = (ba**bc).normalized()
        pl = frames[i]
        dot_x = abs(ax @ pl.x_axis)
        dot_y = abs(ax @ pl.y_axis)
        axis_label = "x" if dot_x >= dot_y else "y"
        scales.append((s, axis_label))
    return scales


# ---------------------------------------------------------------------------
# Parallel-transport frames (spine convention)
# ---------------------------------------------------------------------------


def transport_frames(
    path_or_points: "Path" | List["Vec"],
    ref_direction: "Vec",
    angle_step_deg: float = 5.0,
    miter_scale: bool = True,
) -> FrameField:
    """
    Parallel-transport frames along a polyline path.

    The returned Plane has Z (plane-normal) = path tangent / bisector, which
    is the IFC SectionedSpine convention (Axis = section normal = extrusion
    direction).  X and Y span the cross-section plane.

    The profile's X-dimension maps to world X; the Y-dimension maps to
    Y = Z × X (= the direction in the cross-section plane perpendicular to X).

    Overload: if a ``Path`` is passed instead of ``List[Vec]``, it is sampled
    first (via ``path.sample(angle_step_deg)``) and frames are produced at
    the sample points.

    Args:
        path_or_points: Spine control points [P0, P1, ..., Pn], or a Path.
        ref_direction:  Fixed world direction used to define the initial X-axis
                        (projected onto the plane perpendicular to the tangent).
        angle_step_deg: Arc sampling resolution (only used when a Path is passed).
        miter_scale:    When True (default), computes miter scale factors at
                        interior corners in the returned ``FrameField.scales``.

    Returns:
        ``FrameField`` with ``.frames`` (one Plane per vertex) and ``.scales``
        (per-vertex miter scale factor and axis ``'x'``/``'y'``).
    """
    pts = _points_from_arg(path_or_points, angle_step_deg)
    n = len(pts)
    if n < 2:
        raise ValueError("Need at least 2 points")

    # ---- segment directions and vertex tangents ----------------------------
    segs = [pts[i + 1] - pts[i] for i in range(n - 1)]
    z_vecs: List["Vec"] = []  # tangents = future Z-axes (section normals)

    for i in range(n):
        if i == 0:
            t = segs[0]
        elif i == n - 1:
            t = segs[-1]
        else:
            inc = segs[i - 1].normalized()
            out = segs[i].normalized()
            t = inc + out
            if t.length() < 1e-10:
                t = inc  # straight line — bisector is degenerate
        z_vecs.append(t.normalized())

    # ---- initial X-axis at P0 ----------------------------------------------
    z0 = z_vecs[0]
    r = ref_direction.normalized()
    x0 = r - z0 * (r @ z0)
    if x0.length() < 1e-10:
        x0 = Vec(1, 0, 0) - z0 * (Vec(1, 0, 0) @ z0)
        if x0.length() < 1e-10:
            x0 = Vec(0, 1, 0) - z0 * (Vec(0, 1, 0) @ z0)
    x0 = x0.normalized()
    y0 = z0**x0
    frames: List["Plane"] = [Plane(pts[0], x0, y0)]

    # ---- transport X to remaining vertices ---------------------------------
    for i in range(1, n):
        prev_z = z_vecs[i - 1]
        curr_z = z_vecs[i]

        prev_frame = frames[-1]
        prev_x = prev_frame.x_axis

        v = prev_z**curr_z
        c = prev_z @ curr_z

        if abs(c - 1.0) < 1e-10:
            x = prev_x
        elif abs(c + 1.0) < 1e-10:
            perp = Vec(1, 0, 0) - prev_z * (Vec(1, 0, 0) @ prev_z)
            if perp.length() < 1e-10:
                perp = Vec(0, 1, 0) - prev_z * (Vec(0, 1, 0) @ prev_z)
            perp = perp.normalized()
            x = prev_x.rotate_around(perp, math.pi)
        else:
            axis = v.normalized()
            angle = math.acos(c)
            x = prev_x.rotate_around(axis, angle)

        y = curr_z**x  # Y = Z × X
        frames.append(Plane(pts[i], x.normalized(), y.normalized()))

    if miter_scale:
        scales = _compute_miter_scales(pts, frames)
    else:
        scales = [(1.0, "")] * n

    return FrameField(frames=frames, scales=scales)


def fixed_ref_frames(
    path_or_points: "Path" | List["Vec"],
    ref_direction: "Vec",
    angle_step_deg: float = 5.0,
    miter_scale: bool = True,
) -> FrameField:
    """
    Build section plane frames using a fixed reference direction for X.

    At each vertex, Z = path tangent (bisector). X = projection of ref_direction
    onto the plane ⟂ Z.  Unlike parallel transport, X does NOT rotate — it is
    recomputed independently at each vertex from the same ref_direction.

    Advantage:  X stays as close as possible to a consistent world direction.
                No X-rotation between vertices.
    Disadvantage: When Z aligns with ref_direction, the projection is degenerate
                and falls back to a world axis, causing an abrupt X-flip.

    Overload: if a ``Path`` is passed instead of ``List[Vec]``, it is sampled
    first (via ``path.sample(angle_step_deg)``) and frames are produced at
    the sample points.

    Args:
        path_or_points: Spine control points [P0, ..., Pn], or a Path.
        ref_direction:  World direction to project onto the cross-section plane
                        as the X-axis.
        angle_step_deg: Arc sampling resolution (only used when a Path is passed).
        miter_scale:    When True (default), computes miter scale factors at
                        interior corners in the returned ``FrameField.scales``.

    Returns:
        ``FrameField`` with ``.frames`` and ``.scales``.
    """
    pts = _points_from_arg(path_or_points, angle_step_deg)
    n = len(pts)
    if n < 2:
        raise ValueError("Need at least 2 points")

    segs = [pts[i + 1] - pts[i] for i in range(n - 1)]

    frames: List["Plane"] = []
    prev_x: "Vec" | None = None
    for i in range(n):
        if i == 0:
            z = segs[0].normalized()
        elif i == n - 1:
            z = segs[-1].normalized()
        else:
            inc = segs[i - 1].normalized()
            out = segs[i].normalized()
            t = inc + out
            z = t.normalized() if t.length() > 1e-10 else inc

        # Project ref_direction onto plane ⟂ z
        r = ref_direction.normalized()
        x = r - z * (r @ z)
        if x.length() < 1e-10 and prev_x is not None:
            x = prev_x - z * (prev_x @ z)
        if x.length() < 1e-10:
            x = Vec(1, 0, 0) - z * (Vec(1, 0, 0) @ z)
            if x.length() < 1e-10:
                x = Vec(0, 1, 0) - z * (Vec(0, 1, 0) @ z)
        x = x.normalized()
        y = z**x
        prev_x = x

        frames.append(Plane(pts[i], x, y))

    if miter_scale:
        scales = _compute_miter_scales(pts, frames)
    else:
        scales = [(1.0, "")] * n

    return FrameField(frames=frames, scales=scales)


def upvector_frames(
    path_or_points: "Path" | List["Vec"],
    world_up: "Vec",
    angle_step_deg: float = 5.0,
    miter_scale: bool = True,
) -> FrameField:
    """
    Build section plane frames keeping profile Y near a \"world-up\" direction.

    At each vertex the profile's **Y-axis** is the world-up vector projected
    onto the plane ⟂ Z.  X = Z × Y completes the right-hand frame.

    This avoids the 90° Y-axis flip that can occur with ``fixed_ref_frames``
    when the spine changes direction across orthogonal planes.

    Args:
        path_or_points: Spine control points or a Path.
        world_up:       Direction to keep profile Y close to (projected
                        onto each cross-section plane).
        angle_step_deg: Arc sampling resolution (Path overload only).
        miter_scale:    Compute per-vertex miter scale factors.

    Returns:
        ``FrameField`` with ``.frames`` and ``.scales``.
    """
    pts = _points_from_arg(path_or_points, angle_step_deg)
    n = len(pts)
    if n < 2:
        raise ValueError("Need at least 2 points")

    segs = [pts[i + 1] - pts[i] for i in range(n - 1)]

    up = world_up.normalized()
    frames: List["Plane"] = []
    prev_y: "Vec" | None = None

    for i in range(n):
        if i == 0:
            z = segs[0].normalized()
        elif i == n - 1:
            z = segs[-1].normalized()
        else:
            inc = segs[i - 1].normalized()
            out = segs[i].normalized()
            t = inc + out
            z = t.normalized() if t.length() > 1e-10 else inc

        # Project world_up onto plane ⟂ Z → becomes profile Y
        y = up - z * (up @ z)
        if y.length() < 1e-10 and prev_y is not None:
            y = prev_y - z * (prev_y @ z)
        if y.length() < 1e-10:
            y = Vec(0, 0, 1) - z * (Vec(0, 0, 1) @ z)
            if y.length() < 1e-10:
                y = Vec(1, 0, 0) - z * (Vec(1, 0, 0) @ z)
        y = y.normalized()
        x = y**z  # X = Y × Z (right-handed: Z = X × Y)
        prev_y = y

        frames.append(Plane(pts[i], x, y))

    if miter_scale:
        scales = _compute_miter_scales(pts, frames)
    else:
        scales = [(1.0, "")] * n

    return FrameField(frames=frames, scales=scales)


# ---------------------------------------------------------------------------
# Assemble unordered segments into continuous paths
# ---------------------------------------------------------------------------


def _segments_connected(
    a: Line | Arc,
    b: Line | Arc,
    tol: float = 1e-9,
) -> bool:
    """Check if b's start matches a's end within tolerance."""
    return a.end.equals(b.start, tol)


def _line_line_intersect_2d(p1: "Vec", d1: "Vec", p2: "Vec", d2: "Vec") -> Optional["Vec"]:
    """Find intersection of two lines in the XY plane.

    Lines defined as Q = p1 + t*d1 and R = p2 + s*d2.
    Returns the intersection point, or None if lines are parallel.
    Works in 2D (x,y) — z of result is taken from p1.
    """
    denom = d1.x * (-d2.y) - d1.y * (-d2.x)
    if abs(denom) < 1e-12:
        return None
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    t = (dx * (-d2.y) - dy * (-d2.x)) / denom
    return Vec(p1.x + t * d1.x, p1.y + t * d1.y, p1.z + t * d1.z)


# def _flip_line(line: Line) -> Line:
#     """Return a Line with flipped direction."""
#     return Line(line.end, line.start)


def _segments_fit(
    a: Line | Arc,
    b: Line | Arc,
    tol: float = 1e-9,
) -> tuple[bool, bool]:
    """
    Check if two segments can connect.

    Returns (forward, reversed) where:
      - forward: b.start matches a.end (b connects as-is)
      - reversed: b.end matches a.end (b needs to be flipped)
    """
    forward = a.end.equals(b.start, tol)
    reversed = a.end.equals(b.end, tol)
    return forward, reversed


def assemble_path(
    segments: Sequence[Line | Arc],
    tol: float = 1e-9,
) -> List["Path"]:
    """
    Assemble unordered Line/Arc segments into one or more continuous Paths.

    Segments may be:
      - Unordered (any start order)
      - Flipped (line direction or arc sweep may be reversed)
      - Mixed Line and Arc

    The function:
      1. Chains segments by matching endpoints (within tol)
      2. Flips segment direction to maintain continuity
      3. Normalizes all arc normals to the path's plane normal
      4. Returns List[Path] — one per connected subpath

    Raises ValueError if no segments provided.
    """
    if not segments:
        raise ValueError("segments must not be empty")

    segs = list(segments)
    unused = set(range(len(segs)))
    paths: List[Path] = []

    while unused:
        start_idx = min(unused)
        unused.remove(start_idx)
        path = Path()
        seg = segs[start_idx]

        if isinstance(seg, Line):
            path.add_line(seg.start, seg.end)
        elif isinstance(seg, Arc):
            path.add_arc(seg.center, seg.normal, seg.start, seg.angle)

        while True:
            current_end = path.end_point()  # noqa: F841
            current_start = path.start_point()  # noqa: F841
            added = False

            for i in sorted(unused):
                nxt = segs[i]
                forward, reversed = _segments_fit(path._segments[-1], nxt, tol)
                if forward:
                    added = True
                    unused.remove(i)
                    if isinstance(nxt, Line):
                        path.add_line(nxt.start, nxt.end)
                    elif isinstance(nxt, Arc):
                        path.add_arc(nxt.center, nxt.normal, nxt.start, nxt.angle)
                    break
                elif reversed:
                    added = True
                    unused.remove(i)
                    if isinstance(nxt, Line):
                        flipped = nxt.reverse()
                        path.add_line(flipped.start, flipped.end)
                    elif isinstance(nxt, Arc):
                        flipped = nxt.reverse()
                        path.add_arc(flipped.center, flipped.normal, flipped.start, flipped.angle)
                    break

            if not added:
                break

            if path.start_tangent is None or path.end_tangent is None:
                break

        paths.append(path)

    if not paths:
        raise ValueError("Could not assemble any path")

    return paths


# def assemble_path_planar(
#     segments: Sequence[Line | Arc],
#     plane_normal: Vec,
#     tol: float = 1e-9,
# ) -> List["Path"]:
#     """
#     Assemble unordered Line/Arc segments, normalized to plane_normal.
#
#     Unlike assemble_path(), this version:
#       - Takes an explicit plane_normal to use as the canonical normal
#       - Normalizes all Arc segments to have normal parallel to plane_normal
#       - Works even when segments don't form a single planar path on their own
#     """
#     if not segments:
#         raise ValueError("segments must not be empty")
#
#     segs = list(segments)
#     unused = set(range(len(segs)))
#     paths: List[Path] = []
#
#     while unused:
#         start_idx = min(unused)
#         unused.remove(start_idx)
#         path = Path()
#         seg = segs[start_idx]
#
#         if isinstance(seg, Line):
#             path.add_line(seg.start, seg.end)
#         elif isinstance(seg, Arc):
#             adj_arc = seg.reverse() if seg.normal.dot(plane_normal) < 0 else seg
#             path.add_arc(adj_arc.center, adj_arc.normal, adj_arc.start, adj_arc.angle)
#
#         while True:
#             current_end = path.end_point()
#             if current_end is None:
#                 break
#             found = False
#             for i in sorted(unused):
#                 nxt = segs[i]
#                 forward, reversed = _segments_fit(path._segments[-1], nxt, tol)
#                 if forward:
#                     found = True
#                     unused.remove(i)
#                     if isinstance(nxt, Line):
#                         path.add_line(nxt.start, nxt.end)
#                     elif isinstance(nxt, Arc):
#                         adj_nxt = (
#                             nxt.reverse() if nxt.normal.dot(plane_normal) < 0 else nxt
#                         )
#                         path.add_arc(
#                             adj_nxt.center, adj_nxt.normal, adj_nxt.start, adj_nxt.angle
#                         )
#                     break
#                 elif reversed:
#                     found = True
#                     unused.remove(i)
#                     if isinstance(nxt, Line):
#                         flipped = _flip_line(nxt)
#                         path.add_line(flipped.start, flipped.end)
#                     elif isinstance(nxt, Arc):
#                         flipped = nxt.reverse()
#                         path.add_arc(
#                             flipped.center, flipped.normal, flipped.start, flipped.angle
#                         )
#                     break
#             if not found:
#                 break
#
#         paths.append(path)
#
#     if not paths:
#         raise ValueError("Could not assemble any path")
#
#     return paths


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _polygon_normal(points: List["Vec"]) -> "Vec":
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


def _signed_area(points: List["Vec"], normal: "Vec") -> float:
    """Signed area of a polygon projected onto the plane defined by normal."""
    area = Vec(0, 0, 0)
    count = len(points)
    for i in range(count):
        area = area + (points[i] ** points[(i + 1) % count])
    return (area @ normal) * 0.5
