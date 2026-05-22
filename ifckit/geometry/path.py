"""
ifckit.geometry.path
====================

Path — a G1-continuous sequence of Line and Arc segments, with fillet
support and path assembly helpers.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

if TYPE_CHECKING:
    import ifcopenshell

from ifckit.geometry.primitives import (
    Arc,
    Line,
    Plane,
    Polyline,
    Vec,
    _signed_area,
)
from ifckit.geometry.transform import Transform


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

    def _segment_and_local_t_at_length(self, d: float) -> "Tuple[int, float]":
        """Map distance *d* along path to ``(segment_index, local_t)``.

        Args:
            d: Distance from path start in ``[0, length]``.

        Returns:
            ``(index, t)`` where *index* is the segment index and
            *t* is the local parameter ``[0, 1]`` within that segment.
        """
        if not self._segments:
            raise ValueError("Path has no segments")
        total = self.length
        if d <= 0.0:
            return 0, 0.0
        if d >= total:
            return len(self._segments) - 1, 1.0
        accumulated = 0.0
        for i, seg in enumerate(self._segments):
            seg_len = seg.length
            if accumulated + seg_len >= d:
                local_t = (d - accumulated) / seg_len
                return i, local_t
            accumulated += seg_len
        return len(self._segments) - 1, 1.0

    def point_at_length(self, d: float) -> "Vec":
        """Point at distance *d* from the start of the path.

        Args:
            d: Distance from path start in ``[0, length]``.

        Returns:
            The point at that distance.
        """
        i, t = self._segment_and_local_t_at_length(d)
        return self._segments[i].point_at(t)

    def point_at(self, t: float) -> "Vec":
        """Point at normalized parameter *t* along the total path length.

        ``t=0`` → start point, ``t=1`` → end point.

        Args:
            t: Normalized parameter in ``[0, 1]``.

        Returns:
            The point at that parameter.
        """
        return self.point_at_length(t * self.length)

    def tangent_at_length(self, d: float) -> "Vec":
        """Tangent direction at distance *d* from the start of the path.

        Args:
            d: Distance from path start in ``[0, length]``.

        Returns:
            Normalized tangent direction at that distance.
        """
        i, t = self._segment_and_local_t_at_length(d)
        return self._segments[i].tangent_at(t)

    def tangent_at(self, t: float) -> "Vec":
        """Tangent direction at normalized parameter *t*.

        ``t=0`` → start tangent, ``t=1`` → end tangent.

        Args:
            t: Normalized parameter in ``[0, 1]``.

        Returns:
            Normalized tangent direction at that parameter.
        """
        return self.tangent_at_length(t * self.length)

    def subpath(self, t_start: float, t_end: float) -> "Path":
        """Return a new Path containing the portion from ``t_start`` to ``t_end``.

        Both parameters are normalized ``[0, 1]`` along the total path length.
        If *t_start* > *t_end* the two are swapped.  The result is a new Path
        whose segments are trimmed copies of the original.

        Args:
            t_start: Start parameter in ``[0, 1]``.
            t_end:   End parameter in ``[0, 1]``.

        Returns:
            A new Path spanning the requested portion.

        Raises:
            ValueError: If the path has no segments.
        """
        if not self._segments:
            raise ValueError("Path has no segments")

        t0 = max(0.0, min(1.0, t_start))
        t1 = max(0.0, min(1.0, t_end))
        if t0 > t1:
            t0, t1 = t1, t0

        total = self.length
        d0 = t0 * total
        d1 = t1 * total

        i0, lt0 = self._segment_and_local_t_at_length(d0)
        i1, lt1 = self._segment_and_local_t_at_length(d1)

        import copy

        new_path = Path(plane=self._plane)

        if i0 == i1:
            seg = self._segments[i0]
            if isinstance(seg, Line):
                new_path._segments.append(Line(seg.point_at(lt0), seg.point_at(lt1)))
            else:
                new_start = seg.point_at(lt0)
                new_angle = seg.angle * (lt1 - lt0)
                new_path._segments.append(Arc(seg.center, seg.normal, new_start, new_angle))
            return new_path

        # First segment trimmed from lt0 to end
        seg0 = self._segments[i0]
        if isinstance(seg0, Line):
            new_path._segments.append(Line(seg0.point_at(lt0), seg0.end))
        else:
            new_path._segments.append(
                Arc(
                    seg0.center,
                    seg0.normal,
                    seg0.point_at(lt0),
                    seg0.angle * (1.0 - lt0),
                )
            )

        # Full middle segments
        for i in range(i0 + 1, i1):
            new_path._segments.append(copy.copy(self._segments[i]))

        # Last segment trimmed from start to lt1
        seg1 = self._segments[i1]
        if isinstance(seg1, Line):
            new_path._segments.append(Line(seg1.start, seg1.point_at(lt1)))
        else:
            new_path._segments.append(Arc(seg1.center, seg1.normal, seg1.start, seg1.angle * lt1))

        return new_path

    def sample(self, angle_step_deg: float = 5.0) -> "Polyline":
        """
        Sample the entire path into a "Polyline".
        Consecutive segment endpoints are deduplicated.
        For closed paths the trailing duplicate of the start point is removed.
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
        # Closed path: last point == first point → strip trailing duplicate
        if len(pts) > 1 and pts[0].equals(pts[-1]):
            pts = pts[:-1]
        return Polyline(pts)

    def tessellate(self, angle_step_deg: float = 5.0) -> "Path":
        """Return a new Path with all Arc segments replaced by polyline approximations.

        The result contains only ``Line`` segments.  The stored plane is
        preserved so that ``to_ifc_profile()`` and other plane-dependent
        operations still work correctly.

        Useful when the downstream consumer cannot handle ``IfcTrimmedCurve``
        (e.g. Bonsai's profile editor) but a tessellated polyline is fine::

            solid = _path_to_solid(ifc_file, path.tessellate(5), depth, inset)

        Args:
            angle_step_deg: Arc sampling resolution in degrees (default 5°).

        Returns:
            New ``Path`` with only ``Line`` segments.
        """
        pts = self.sample(angle_step_deg).points
        return Path.from_pts(pts, plane=self._plane, closed=self.is_closed)

    def to_mesh_dict(
        self,
        angle_step_deg: float = 5.0,
        label: str = "",
        material: "dict | None" = None,
        y_up: bool = True,
    ) -> dict:
        """Serialize the path as a polyline for 3D viewer consumption.

        Args:
            angle_step_deg: Arc sampling resolution (degrees).
            label:          Display name.
            material:       Visual properties (color, opacity, …).
            y_up:           If True (default), convert coordinates from
                            ifckit Z-up to Three.js/glTF Y-up convention:
                            ``(x, z, -y)``.

        Returns:
            A dict with ``primitive``, ``positions``, and optional
            ``closed``, ``label``, ``material`` keys.
        """
        poly = self.sample(angle_step_deg)
        pts = poly.points if hasattr(poly, "points") else list(poly)
        if y_up:
            flat = [c for v in pts for c in (v.x, v.z, -v.y)]
        else:
            flat = [c for v in pts for c in (v.x, v.y, v.z)]
        d: dict = {
            "primitive": "line-loop" if self.is_closed else "line-strip",
            "positions": flat,
            "closed": self.is_closed,
            "label": label or "Path",
        }
        if material is not None:
            d["material"] = material
        return d

    def preview(
        self,
        label: str = "",
        material: "dict | None" = None,
        angle_step_deg: float = 5.0,
        y_up: bool = True,
    ) -> dict:
        """Return a ``__type__: "mesh"`` dict ready for the viewer pipeline.

        Equivalent to wrapping ``to_mesh_dict()`` in ``{"__type__": "mesh", …}``.

        Args:
            label:          Display name in the viewer.
            material:       Optional visual properties dict. Supported keys:

                - ``color`` (str, hex)        — ``"#FF6600"``
                - ``opacity`` (float 0‑1)
                - ``line_type`` (str)          — ``"solid"`` | ``"dashed"`` | ``"dotted"``
                - ``line_width`` (int)         — point size for ``"dotted"``
                - ``dash_size``, ``gap_size`` (float)  — for dashed lines

            angle_step_deg: Arc sampling resolution (degrees).

        Returns:
            ``{"__type__": "mesh", "primitive": …, "positions": […], …}``
        """
        return {
            "__type__": "mesh",
            **self.to_mesh_dict(
                label=label, material=material, angle_step_deg=angle_step_deg, y_up=y_up
            ),
        }

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
        if self._plane is not None:
            return self._plane
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

    def fillet(self, index: "int | List[int]", radius: float) -> "Path":
        """Round one or more corners with a circular arc of given *radius*.

        The vertex at *index* is the shared endpoint between
        ``_segments[index-1]`` (incoming) and ``_segments[index]``
        (outgoing).  For closed paths, *index* 0 addresses the wrap-around
        corner between the last and first segments.

        When *index* is a list, corners are processed in **descending**
        order so that earlier entries stay valid after earlier fillets
        have shifted subsequent segment indices::

            rect = Path.from_pts([...], closed=True)
            rect.fillet([0, 1, 2, 3], 20)  # all 4 corners, no index math

        Modifies the path **in place** and returns ``self`` so calls can
        be chained.

        The method silently warns and skips invalid corners (out of range,
        non-Line segments, collinear, too short).

        Args:
            index:  Vertex index (int) or list of indices.  For lists,
                    processed descending so lower indices stay valid.
            radius: Fillet radius (same units as the path coordinates).

        Returns:
            ``self`` (modified in place).
        """
        import warnings as _warnings

        # ── List overload: process in descending order ──────────────
        if isinstance(index, list):
            for idx in sorted(index, reverse=True):
                self.fillet(idx, radius)
            return self

        segs = self._segments
        n = len(segs)

        # ------------------------------------------------------------------
        # Guard: index must address an interior vertex between two segments.
        # For open paths: 1 … n-1.
        # For closed paths: 0 … n-1 (0 = wrap-around corner).
        # ------------------------------------------------------------------
        if index == 0 and not self.is_closed:
            _warnings.warn(
                "fillet: index 0 (wrap-around corner) is only valid on closed paths.",
                stacklevel=2,
            )
            return self

        if not (0 <= index <= n - 1) or (index == 0 and n < 2):
            _warnings.warn(
                f"fillet: index {index} is out of range — "
                f"valid interior vertex indices are 0 … {n - 1} "
                f"for a path with {n} segments.",
                stacklevel=2,
            )
            return self

        # Resolve adjacent segments (wrap-around for index 0)
        seg_in = segs[(index - 1) % n]
        seg_out = segs[index % n]
        corner = seg_in.end

        if not isinstance(seg_in, Line):
            _warnings.warn(
                f"fillet: incoming segment is not a Line "
                f"({type(seg_in).__name__}). Only Line–Line corners are supported.",
                stacklevel=2,
            )
            return self

        if not isinstance(seg_out, Line):
            _warnings.warn(
                f"fillet: outgoing segment is not a Line "
                f"({type(seg_out).__name__}). Only Line–Line corners are supported.",
                stacklevel=2,
            )
            return self

        # Guard: zero or negative radius is degenerate.
        if radius <= 0.0:
            _warnings.warn(
                f"fillet: radius must be positive, got {radius}. Fillet skipped.",
                stacklevel=2,
            )
            return self

        # Segment directions (pointing *along* travel direction)
        dir_in = seg_in.direction.normalized()  # incoming: toward corner
        dir_out = seg_out.direction.normalized()  # outgoing: away from corner

        # Unit tangents pointing *away* from the corner along each leg
        d_in = -dir_in  # away from corner along incoming leg
        d_out = dir_out  # away from corner along outgoing leg

        # ------------------------------------------------------------------
        # Collinearity check
        # ------------------------------------------------------------------
        cos_away = d_in @ d_out
        if cos_away < -1.0 + 1e-9:
            _warnings.warn(
                f"fillet: segments at vertex {index} are collinear (no corner). Fillet skipped.",
                stacklevel=2,
            )
            return self
        if cos_away > 1.0 - 1e-9:
            _warnings.warn(
                f"fillet: segments at vertex {index} form a 180° U-turn "
                f"— degenerate corner. Fillet skipped.",
                stacklevel=2,
            )
            return self

        # Angle between the two away-directions, and its half:
        half_angle = math.acos(max(-1.0, min(1.0, cos_away))) / 2.0
        tan_half = math.tan(half_angle)
        t = radius / tan_half if tan_half > 1e-12 else float("inf")

        # ------------------------------------------------------------------
        # Leg-length check
        # ------------------------------------------------------------------
        if t > seg_in.length + 1e-9:
            _warnings.warn(
                f"fillet: radius {radius} requires a tangent set-back of {t:.3f} "
                f"but the incoming segment is only {seg_in.length:.3f} long. "
                f"Fillet skipped.",
                stacklevel=2,
            )
            return self

        if t > seg_out.length + 1e-9:
            _warnings.warn(
                f"fillet: radius {radius} requires a tangent set-back of {t:.3f} "
                f"but the outgoing segment is only {seg_out.length:.3f} long. "
                f"Fillet skipped.",
                stacklevel=2,
            )
            return self

        # ------------------------------------------------------------------
        # Geometry: tangent points and arc center
        # ------------------------------------------------------------------
        tan_pt_in = corner + d_in * t  # tangent point on incoming leg
        tan_pt_out = corner + d_out * t  # tangent point on outgoing leg

        arc_normal = (dir_in**dir_out).normalized()

        bisector = (d_in + d_out).normalized()
        center = corner + bisector * (radius / math.sin(half_angle))

        radial_in = (tan_pt_in - center).normalized()
        radial_out = (tan_pt_out - center).normalized()
        cos_sweep = max(-1.0, min(1.0, radial_in @ radial_out))
        sin_sweep = arc_normal @ (radial_in**radial_out)
        sweep = math.atan2(sin_sweep, cos_sweep)

        # ------------------------------------------------------------------
        # Rebuild the three segments: shortened in, arc, shortened out
        # ------------------------------------------------------------------
        new_seg_in = Line(seg_in.start, tan_pt_in)
        arc_seg = Arc(center, arc_normal, tan_pt_in, sweep)
        new_seg_out = Line(tan_pt_out, seg_out.end)

        if index == 0:
            # Wrap-around corner: replace segs[-1] and segs[0] with the
            # three new segments.  segs[-1] → new_seg_in (truncated
            # closing segment); segs[0] → [arc, new_seg_out].
            self._segments[-1] = new_seg_in
            self._segments[0:1] = [arc_seg, new_seg_out]
        else:
            self._segments = (
                segs[: index - 1] + [new_seg_in, arc_seg, new_seg_out] + segs[index + 1 :]
            )
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

    def move(self, delta: "Vec") -> "Path":
        """Translate all segment points by *delta*. Returns ``self``."""
        new_segs = []
        for seg in self._segments:
            if isinstance(seg, Line):
                new_segs.append(Line(seg.start + delta, seg.end + delta))
            else:
                new_segs.append(Arc(seg.center + delta, seg.normal, seg.start + delta, seg.angle))
        self._segments = new_segs
        if self._plane is not None:
            self._plane = Plane(self._plane.origin + delta, self._plane.x_axis, self._plane.y_axis)
        return self

    def rotate(self, degrees: float, center: "Optional[Vec]" = None) -> "Path":
        """Rotate all segment points around *center* in the XY plane.

        Args:
            degrees: CCW rotation angle in degrees.
            center:  Rotation pivot. Defaults to ``Vec(0, 0, 0)``.

        Returns:
            ``self`` (modified in place).
        """
        import math as _math

        axis = Vec(0, 0, 1)
        ctr = center if center is not None else Vec(0, 0, 0)
        angle = _math.radians(degrees)
        new_segs = []
        for seg in self._segments:
            if isinstance(seg, Line):
                new_segs.append(
                    Line(
                        (seg.start - ctr).rotate_around(axis, angle) + ctr,
                        (seg.end - ctr).rotate_around(axis, angle) + ctr,
                    )
                )
            else:
                new_segs.append(
                    Arc(
                        (seg.center - ctr).rotate_around(axis, angle) + ctr,
                        seg.normal,
                        (seg.start - ctr).rotate_around(axis, angle) + ctr,
                        seg.angle,
                    )
                )
        self._segments = new_segs
        if self._plane is not None:
            self._plane = Plane(
                (self._plane.origin - ctr).rotate_around(axis, angle) + ctr,
                self._plane.x_axis.rotate_around(axis, angle),
                self._plane.y_axis.rotate_around(axis, angle),
            )
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

    # ------------------------------------------------------------------
    # Affine transforms  (return new Path)
    # ------------------------------------------------------------------

    def transformed(self, t: "Transform") -> "Path":
        """Apply a 4×4 affine transform to all segments + holes + plane.

        Returns a new Path.  Under non-uniform scale, Arc segments are
        sampled to polylines (since arcs become ellipses).
        """
        new_path = Path(plane=self._plane.transformed(t) if self._plane else None)
        new_path._segments = []
        # Use self.segments (property) to trigger lazy building (e.g. Profile)
        for seg in self.segments:
            if isinstance(seg, Line):
                new_path._segments.append(seg.transformed(t))
            elif t.is_uniform_scale():
                new_path._segments.append(seg.transformed(t))
            else:
                pts = seg.sample()
                for i in range(len(pts) - 1):
                    new_path._segments.append(Line(t.apply(pts[i]), t.apply(pts[i + 1])))
        new_path._holes = [h.transformed(t) for h in self._holes]
        return new_path

    def mirrored(self, plane: "Plane") -> "Path":
        """Mirror over an arbitrary plane. Returns a new Path."""
        return self.transformed(Transform.reflection(plane))

    def translated(self, delta: "Vec") -> "Path":
        """Translate by *delta*. Returns a new Path."""
        return self.transformed(Transform.translation(delta))

    def rotated(self, axis: "Vec", angle: float, center: "Optional[Vec]" = None) -> "Path":
        """Rotate around *axis* by *angle* radians. Returns a new Path.

        Args:
            axis:   Rotation axis (world space).
            angle:  Rotation angle in radians.
            center: Center of rotation. Defaults to world origin.
        """
        if center is not None:
            return (
                self.translated(-center)
                .transformed(Transform.rotation(axis, angle))
                .translated(center)
            )
        return self.transformed(Transform.rotation(axis, angle))

    def scaled(
        self,
        sx: float,
        sy: "Optional[float]" = None,
        sz: "Optional[float]" = None,
        center: "Optional[Vec]" = None,
    ) -> "Path":
        """Scale by factors *sx*, *sy*, *sz*. Returns a new Path.

        Args:
            sx:     X-axis scale factor.
            sy:     Y-axis scale factor (defaults to sx).
            sz:     Z-axis scale factor (defaults to sx).
            center: Center of scaling. Defaults to world origin.
        """
        if sy is None:
            sy = sx
        if sz is None:
            sz = sx
        t = Transform.scaling(sx, sy, sz)
        if center is not None:
            return self.translated(-center).transformed(t).translated(center)
        return self.transformed(t)

    def copy(self, delta: Optional["Vec"] = None) -> "Path":
        """Return an independent deep copy, optionally translated by *delta*.

        When *delta* is ``None`` (default) this is an alias for
        ``duplicate()``.

        Args:
            delta:  Optional translation vector.

        Returns:
            New Path (moved if *delta* was given).
        """
        cpy = self.duplicate()
        if delta is not None:
            cpy.move(delta)
        return cpy

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

    def continued(self, tol: float = 1e-9) -> "Path":
        """Return a new Path with all segments chained end‑to‑start.

        Segments whose end matches the next segment's **end** (reversed)
        are flipped so the chain is continuous.  This is the same logic
        used by :func:`assemble_path` but applied to a single already‑
        ordered path.

        Args:
            tol: Endpoint comparison tolerance.

        Returns:
            A new ``Path`` with consistent segment direction.
        """
        result = Path(plane=self._plane)
        if not self._segments:
            return result
        result._segments = [self._segments[0]]
        for seg in self._segments[1:]:
            _, rev = _segments_fit(result._segments[-1], seg, tol)
            result._segments.append(seg.reverse() if rev else seg)
        return result

    def normalize(self, tol: float = 1e-9) -> "Path":
        """Return a new Path with consistent arc normal direction.

        All ``Arc`` segments are flipped so their normals point in the
        same direction as the first arc in the path.  ``Line`` segments
        are left untouched.

        Args:
            tol: Dot‑product tolerance for opposite detection.

        Returns:
            A new ``Path`` with uniform arc normals.
        """
        result = Path(plane=self._plane)
        if not self._segments:
            return result

        # Find the canonical normal from the first Arc
        canonical = None
        for seg in self._segments:
            if isinstance(seg, Arc):
                canonical = seg.normal.normalized()
                break

        for seg in self._segments:
            if isinstance(seg, Arc) and canonical is not None:
                if (seg.normal.normalized() @ canonical) < 0:
                    result._segments.append(seg.reverse())
                    continue
            result._segments.append(seg)
        return result

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

    def offset(self, dist: float, cap: bool = False) -> "Path":
        """Return a new offset Path at distance *dist*, preserving arc segments.

        Each ``Line`` segment is shifted perpendicular to its direction.
        Each ``Arc`` segment keeps its center, normal and sweep angle; only
        the radius changes by ±*dist* (the sign depends on whether the arc
        curves toward or away from the offset direction).

        Consecutive offset segments are joined at their miter intersection so
        the result is a continuous path with no gaps.

        For **closed** paths: positive *dist* offsets inward (toward the
        centroid for a CCW-wound path).
        For **open** paths: positive *dist* offsets to the left of the travel
        direction, negative to the right.  When *cap* is ``True`` the result
        is a closed path (original + offset + end caps).

        Args:
            dist: Offset distance (same units as path coordinates).
            cap:  If ``True`` and the path is open, cap the ends to produce a
                  closed path (ignored for closed paths).

        Returns:
            New ``Path`` with offset geometry.  *self* is not modified.

        Raises:
            ValueError: If the path is degenerate or the offset distance is
                        too large (arc radius would go negative).
        """
        # Compute plane normal from stored plane or geometry
        n: "Vec | None" = None
        if self._plane is not None:
            n = self._plane.z_axis
        if n is None:
            n = self.normal
        if n is None:
            raise ValueError("Cannot determine plane normal for offset")

        segs = self._segments
        if not segs:
            raise ValueError("offset() requires at least one segment")

        # ------------------------------------------------------------------
        # Step 1 – offset each segment independently.
        # A Line is shifted by (n × direction) * dist.
        # An Arc keeps its center; start is moved radially.  The sign of the
        # radius delta depends on whether the arc normal is aligned with the
        # plane normal (positive sweep = CCW = inward side is toward center).
        # ------------------------------------------------------------------
        def _offset_seg(seg: "Line | Arc") -> "Line | Arc":
            if isinstance(seg, Line):
                d = (seg.end - seg.start).normalized()
                perp = (n**d).normalized() * dist
                return Line(seg.start + perp, seg.end + perp)

            # Arc: offset radius.
            # The arc sweeps CCW around seg.normal.  The "inward" side of the
            # arc (toward the center) has n × tangent pointing toward center.
            # sign: if arc normal aligns with plane normal → positive sweep →
            # center is to the left → inward offset *reduces* radius.
            sign = 1.0 if (seg.normal @ n) > 0 else -1.0
            new_radius = seg.radius - sign * dist
            if new_radius <= 0:
                raise ValueError(
                    f"offset(): arc radius {seg.radius:.3f} becomes non-positive "
                    f"({new_radius:.3f}) with dist={dist:.3f}"
                )
            radial = (seg.start - seg.center).normalized()
            new_start = seg.center + radial * new_radius
            return Arc(seg.center, seg.normal, new_start, seg.angle)

        offset_segs = [_offset_seg(s) for s in segs]

        # ------------------------------------------------------------------
        # Step 2 – reconnect: intersect each consecutive pair of offset
        # segments so they share an exact endpoint.
        # ------------------------------------------------------------------
        def _seg_line_repr(seg: "Line | Arc") -> "tuple[Vec, Vec]":
            """Return (point_on_line, direction) for the tangent line at the
            *start* of the segment — used for miter intersection."""
            if isinstance(seg, Line):
                return seg.start, (seg.end - seg.start).normalized()
            # Arc: tangent at start = normal × radial_start
            radial = (seg.start - seg.center).normalized()
            tangent = (seg.normal**radial).normalized()
            return seg.start, tangent

        def _seg_end_line_repr(seg: "Line | Arc") -> "tuple[Vec, Vec]":
            """Return (point_on_line, direction) for the tangent at the *end*."""
            if isinstance(seg, Line):
                return seg.start, (seg.end - seg.start).normalized()
            radial_end = (seg.end - seg.center).normalized()
            tangent_end = (seg.normal**radial_end).normalized()
            return seg.end, tangent_end

        def _set_start(seg: "Line | Arc", pt: "Vec") -> "Line | Arc":
            if isinstance(seg, Line):
                return Line(pt, seg.end)
            # radial = (pt - seg.center).normalized()
            return Arc(seg.center, seg.normal, pt, seg.angle)

        def _set_end(seg: "Line | Arc", pt: "Vec") -> "Line | Arc":
            if isinstance(seg, Line):
                return Line(seg.start, pt)
            # Adjust angle so the arc ends at pt
            radial_start = (seg.start - seg.center).normalized()
            radial_end = (pt - seg.center).normalized()
            cos_a = max(-1.0, min(1.0, radial_start @ radial_end))
            sin_a = seg.normal @ (radial_start**radial_end)
            new_angle = math.atan2(sin_a, cos_a)
            return Arc(seg.center, seg.normal, seg.start, new_angle)

        n_segs = len(offset_segs)
        indices = range(n_segs) if self.is_closed else range(n_segs - 1)

        for i in indices:
            j = (i + 1) % n_segs
            seg_a = offset_segs[i]
            seg_b = offset_segs[j]

            p1, d1 = _seg_end_line_repr(seg_a)
            p2, d2 = _seg_line_repr(seg_b)

            ip = _line_line_intersect_2d(p1, d1, p2, d2)
            if ip is None:
                # Parallel/collinear — use the midpoint of the gap
                ip = (seg_a.end + seg_b.start) * 0.5

            offset_segs[i] = _set_end(seg_a, ip)
            offset_segs[j] = _set_start(seg_b, ip)

        # ------------------------------------------------------------------
        # Step 3 – assemble result path
        # ------------------------------------------------------------------
        if self.is_closed:
            result = Path(plane=self._plane)
            result._segments = list(offset_segs)
            result._closed = True
            return result

        # Open path
        if not cap:
            result = Path(plane=self._plane)
            result._segments = list(offset_segs)
            return result

        # Cap: offset curve → end cap → original reversed → start cap
        orig_pts = self.sample().points
        result = Path(plane=self._plane)
        result._segments = list(offset_segs)
        result.add_line(offset_segs[-1].end, orig_pts[-1])
        for i in range(len(orig_pts) - 1, 0, -1):
            result.add_line(orig_pts[i], orig_pts[i - 1])
        result.add_line(orig_pts[0], offset_segs[0].start)
        result._closed = True
        return result

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

    # ------------------------------------------------------------------
    # IFC profile conversion (preserves arcs as IfcCircle + IfcTrimmedCurve)
    # ------------------------------------------------------------------

    def to_ifc_profile(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        """Convert this closed Path to an ``IfcProfileDef``, preserving arcs.

        Unlike ``to_profile_points()`` (which tessellates arcs to line
        segments), this method creates a proper ``IfcCompositeCurve``
        whose arc segments become ``IfcTrimmedCurve`` + ``IfcCircle``
        entities.  Holes become an ``IfcArbitraryProfileDefWithVoids``
        with the inner curve wound CW per IFC convention.

        Args:
            ifc_file:  Open ifcopenshell file.

        Returns:
            ``IfcArbitraryClosedProfileDef`` (or *WithVoids) ready for use
            as ``SweptArea`` in ``IfcExtrudedAreaSolid``.

        Raises:
            ValueError: If the path is not closed.
        """
        if not self.is_closed:
            raise ValueError("to_ifc_profile() requires a closed path")

        outer_curve = self._build_composite_curve(ifc_file, self._segments, same_sense=True)

        if not self._holes:
            return ifc_file.create_entity(
                "IfcArbitraryClosedProfileDef",
                ProfileType="AREA",
                OuterCurve=outer_curve,
            )

        inner_curves = []
        for hole in self._holes:
            rev = [seg.reverse() for seg in reversed(hole._segments)]
            inner_curves.append(self._build_composite_curve(ifc_file, rev, same_sense=True))

        return ifc_file.create_entity(
            "IfcArbitraryProfileDefWithVoids",
            ProfileType="AREA",
            OuterCurve=outer_curve,
            InnerCurves=inner_curves,
        )

    # ------------------------------------------------------------------
    # IFC curve-building helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _seg_to_ifc(
        ifc_file: "ifcopenshell.file",
        seg: "Line | Arc",
    ) -> "ifcopenshell.entity_instance":
        """Convert a single segment to an IFC curve entity.

        - ``Line`` → ``IfcPolyline``
        - ``Arc``  → ``IfcTrimmedCurve`` + ``IfcCircle``
        """
        from ifckit.geometry.primitives import Arc as _Arc, Line as _Line  # noqa: I001

        def _pt3(f, x, y, z):
            return f.create_entity(
                "IfcCartesianPoint",
                Coordinates=[round(x, 4), round(y, 4), round(z, 4)],
            )

        def _dir3(f, x, y, z):
            return f.create_entity(
                "IfcDirection",
                DirectionRatios=[round(x, 4), round(y, 4), round(z, 4)],
            )

        if isinstance(seg, _Line):
            return ifc_file.create_entity(
                "IfcPolyline",
                Points=[
                    _pt3(ifc_file, seg.start.x, seg.start.y, seg.start.z),
                    _pt3(ifc_file, seg.end.x, seg.end.y, seg.end.z),
                ],
            )

        if isinstance(seg, _Arc):
            center = seg.center
            if seg.angle >= 0:
                normal = seg.normal
                angle = seg.angle
            else:
                normal = -seg.normal
                angle = -seg.angle

            ref_dir = (seg.start - center).normalized()

            pos = ifc_file.create_entity(
                "IfcAxis2Placement3D",
                Location=_pt3(ifc_file, center.x, center.y, center.z),
                Axis=_dir3(ifc_file, normal.x, normal.y, normal.z),
                RefDirection=_dir3(ifc_file, ref_dir.x, ref_dir.y, ref_dir.z),
            )

            circle = ifc_file.create_entity("IfcCircle", Position=pos, Radius=seg.radius)

            return ifc_file.create_entity(
                "IfcTrimmedCurve",
                BasisCurve=circle,
                Trim1=[ifc_file.create_entity("IfcParameterValue", 0.0)],
                Trim2=[ifc_file.create_entity("IfcParameterValue", angle)],
                SenseAgreement=True,
                MasterRepresentation="PARAMETER",
            )

        raise TypeError(f"Unsupported segment type: {type(seg).__name__}")

    @classmethod
    def _build_composite_curve(
        cls,
        ifc_file: "ifcopenshell.file",
        segments: "List[Line | Arc]",
        same_sense: bool = True,
    ) -> "ifcopenshell.entity_instance":
        """Wrap a list of segments into an ``IfcCompositeCurve``."""
        seg_entities = []
        n = len(segments)
        for i, seg in enumerate(segments):
            curve = cls._seg_to_ifc(ifc_file, seg)
            seg_entities.append(
                ifc_file.create_entity(
                    "IfcCompositeCurveSegment",
                    Transition="CONTINUOUS" if i < n - 1 else "DISCONTINUOUS",
                    SameSense=same_sense,
                    ParentCurve=curve,
                )
            )
        return ifc_file.create_entity("IfcCompositeCurve", Segments=seg_entities)

    def to_pts(self, plane: Optional["Plane"] = None) -> List["Vec"]:
        """Return segment endpoint Vecs (3D world coords by default).

        Args:
            plane: If provided, points are projected to 2D local coords and
                   returned as ``Vec(u, v, 0)``.

        Returns:
            List of Vec points (deduplicated at consecutive segment
            boundaries, with trailing close-point stripped).
        """
        pts: List["Vec"] = []
        for seg in self._segments:
            if isinstance(seg, Arc):
                seg_pts = seg.sample()
            else:
                seg_pts = [seg.start, seg.end]
            if pts and pts[-1].equals(seg_pts[0], tol=1e-9):
                seg_pts = seg_pts[1:]
            pts.extend(seg_pts)

        if len(pts) >= 2 and pts[0].equals(pts[-1], tol=1e-9):
            pts = pts[:-1]

        if plane is not None:
            return [
                Vec(
                    (p - plane.origin) @ plane.x_axis,
                    (p - plane.origin) @ plane.y_axis,
                    0.0,
                )
                for p in pts
            ]
        return pts

    def to_profile(
        self,
        plane: Optional["Plane"] = None,
        name: Optional[str] = None,
    ):
        """Convert a closed planar Path to a :class:`PolygonProfile`.

        Arc segments are sampled to a polyline approximation before
        projection.  The returned profile supports ``.anchor``,
        ``.rotation``, and ``.offset_x``/``.offset_y``.

        Args:
            plane: Reference plane for 2D projection.
                   Falls back to *self._plane*.
            name:  Optional profile name.

        Returns:
            :class:`ifckit.profiles.PolygonProfile` backed by this path's
            sampled vertices.

        Raises:
            ValueError: If path is not closed.
            ValueError: If no plane is available.
        """
        from ifckit.profiles.shapes import PolygonProfile

        pts = self.to_profile_points(plane=plane)
        return PolygonProfile(pts, name=name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plane": self._plane.to_dict() if self._plane else None,
            "segments": [s.to_dict() for s in self._segments],
            "holes": [h.to_dict() for h in self._holes],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Path":
        plane = Plane.from_dict(d["plane"]) if d.get("plane") else None
        path = cls(plane=plane)

        for sd in d.get("segments", []):
            if sd["type"] == "line":
                path._segments.append(Line.from_dict(sd))
            elif sd["type"] == "arc":
                path._segments.append(Arc.from_dict(sd))

        for hd in d.get("holes", []):
            hole = cls.from_dict(hd)
            path._holes.append(hole)

        return path

    def __repr__(self) -> str:
        return f"Path({len(self._segments)} segments, length={self.length:.3f})"


# ---------------------------------------------------------------------------
# Parallel transport frames along a "Path"
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# FrameField — result type for transport_frames / fixed_ref_frames
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Assemble unordered segments into continuous paths
# ---------------------------------------------------------------------------


def _segments_connected(
    a: "Line | Arc",
    b: "Line | Arc",
    tol: float = 1e-9,
) -> bool:
    """Check if b's start matches a's end within tolerance."""
    return a.end.equals(b.start, tol)


def _line_line_intersect_2d(p1: "Vec", d1: "Vec", p2: "Vec", d2: "Vec") -> "Optional[Vec]":
    """Find intersection of two lines in the XY plane."""
    denom = d1.x * (-d2.y) - d1.y * (-d2.x)
    if abs(denom) < 1e-12:
        return None
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    t = (dx * (-d2.y) - dy * (-d2.x)) / denom
    return Vec(p1.x + t * d1.x, p1.y + t * d1.y, p1.z + t * d1.z)


def _segments_fit(
    a: "Line | Arc",
    b: "Line | Arc",
    tol: float = 1e-9,
) -> "tuple[bool, bool]":
    """Check if two segments can connect (forward, reversed)."""
    forward = a.end.equals(b.start, tol)
    reversed_ = a.end.equals(b.end, tol)
    return forward, reversed_


def assemble_path(
    segments: "Sequence[Line | Arc]",
    tol: float = 1e-9,
) -> "List[Path]":
    """Assemble unordered Line/Arc segments into one or more continuous Paths."""
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
            added = False
            for i in sorted(unused):
                nxt = segs[i]
                forward, rev = _segments_fit(path._segments[-1], nxt, tol)
                if forward:
                    added = True
                    unused.remove(i)
                    if isinstance(nxt, Line):
                        path.add_line(nxt.start, nxt.end)
                    elif isinstance(nxt, Arc):
                        path.add_arc(nxt.center, nxt.normal, nxt.start, nxt.angle)
                    break
                elif rev:
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

        paths.append(path)

    if not paths:
        raise ValueError("Could not assemble any path")
    return paths


# ---------------------------------------------------------------------------
# Internal polygon helpers (used by Path.fillet and Path.sample)
# ---------------------------------------------------------------------------
