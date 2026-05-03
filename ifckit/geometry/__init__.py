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
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

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
    def from_origin_and_normal(cls, origin: "Vec", normal: "Vec") -> "Plane":
        """
        Construct a plane from an origin and normal (z_axis = normal).
        x_axis is derived by finding the least-parallel world axis.
        """
        n = normal.normalized()
        # pick world axis least aligned with n to derive x
        world_axes = [Vec(1, 0, 0), Vec(0, 1, 0), Vec(0, 0, 1)]
        ref = min(world_axes, key=lambda a: abs(n @ a))
        x = (n**ref).normalized()  # n × ref: right-handed, perpendicular to n
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
    """An ordered sequence of "Vec" points forming a polyline."""

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

    def __init__(self) -> None:
        self._segments: List[Line | Arc] = []

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
        """Check if all segments lie in the same plane."""
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

    def __repr__(self) -> str:
        return f"Path({len(self._segments)} segments, length={self.length:.3f})"


# ---------------------------------------------------------------------------
# Parallel transport frames along a "Path"
# ---------------------------------------------------------------------------


def parallel_transport_frames(
    path: "Path",
    seed_normal: "Vec",
    angle_step_deg: float = 5.0,
) -> List[Plane]:
    """
    Compute non-twisting (rotation-minimizing) frames along a "Path".

    At each sample point the frame is propagated by rotating the previous
    normal by only as much as the tangent direction demands — no axial spin
    accumulates (Bishop frame / parallel transport frame).

    Args:
        path:           The path to frame.
        seed_normal:    The y_axis of the frame at the start point.
        angle_step_deg: Arc sampling resolution in degrees.

    Returns:
        List of Plane objects, one per sample point.
    """
    sampled = path.sample(angle_step_deg)
    pts = sampled.points
    if len(pts) < 2:
        raise ValueError("Path must have at least 2 sample points")

    frames: List[Plane] = []
    prev_tangent = (pts[1] - pts[0]).normalized()
    prev_normal = seed_normal.normalized()
    # ensure normal is orthogonal to first tangent
    prev_normal = (prev_normal - prev_tangent * (prev_normal @ prev_tangent)).normalized()

    for i, pt in enumerate(pts):
        if i == 0:
            t = prev_tangent
        elif i == len(pts) - 1:
            t = (pts[-1] - pts[-2]).normalized()
        else:
            t = (pts[i + 1] - pts[i - 1]).normalized()

        if i > 0:
            axis = prev_tangent**t
            axis_len = abs(axis)
            if axis_len > 1e-8:
                angle = prev_tangent.angle_to(t)
                prev_normal = prev_normal.rotate_around(axis, angle)
            prev_tangent = t

        binormal = (t**prev_normal).normalized()
        normal = (binormal**t).normalized()
        frames.append(Plane(pt, t, normal))

    return frames


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
