# This file was generated with the assistance of an AI coding tool.
"""
ifckit.geometry.spiral
=======================

Spiral — a procedural spiral generator (Archimedean, logarithmic, helix,
clothoid), evaluated exactly and converted to ``Path`` (``Line`` + ``Arc``)
at the boundary via :meth:`Spiral.to_biarcs` or :meth:`Spiral.to_polyline`.

``Path`` intentionally stays ``Line | Arc`` only; ``Spiral`` follows the
same pattern as ``Curve`` (exact math outside ``Path``, conversion into it)
so every downstream consumer (builders, IFC export, readers) keeps working
with universally readable segment types.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ifckit.geometry.primitives import Plane, Vec
from ifckit.geometry.transform import Transform

if TYPE_CHECKING:
    from ifckit.geometry.path import Path

_KINDS = ("archimedean", "logarithmic", "helix", "clothoid")

# Number of integration steps for the clothoid lookup table.
_CLOTHOID_STEPS = 256


def _basis(axis: Vec, ref_direction: Optional[Vec] = None) -> tuple[Vec, Vec]:
    """Build an orthonormal ``(u, v)`` frame perpendicular to *axis*.

    Follows the same least-aligned-world-axis rule as
    ``Plane.from_origin_and_normal()`` so results are deterministic.
    """
    n = axis.normalized()
    if ref_direction is not None:
        r = ref_direction.normalized()
        raw = r - n * (r @ n)
        if raw.length() > 0.1:
            u = raw.normalized()
            return u, (n**u).normalized()
    world = [Vec(1, 0, 0), Vec(0, 1, 0), Vec(0, 0, 1)]
    ref = min(world, key=lambda a: abs(n @ a))
    u = (n**ref).normalized()
    return u, (n**u).normalized()


class Spiral:
    """A procedural 2D/3D spiral curve with exact analytic evaluation.

    The locus is defined in the ``(u, v)`` plane perpendicular to ``axis``
    through ``center``. ``t`` in ``[0, 1]`` maps linearly onto the angle
    interval ``[theta0, theta1]`` (angle-uniform, like ``Arc.point_at`` —
    not arc-length-uniform; use :meth:`divide` for arc-length walking).
    Height along ``axis`` grows with ``pitch`` (per radian, 0 = planar).
    A planar spiral plus ``pitch != 0`` is a helical / conical ramp.

    Use the ``from_*`` factories; the constructor signature is internal.

    Args:
        kind: One of ``"archimedean"``, ``"logarithmic"``, ``"helix"``,
            ``"clothoid"``.
        center: Spiral origin (point on the axis).
        axis: Plane normal / helix axis (need not be normalised).
        theta0: Start angle in radians.
        theta1: End angle in radians (must differ from *theta0*, except
            clothoid which ignores both).
        r0: Start radius (> 0).
        growth: Archimedean ``b`` in ``r = r0 + b*(th - theta0)``;
            logarithmic ``b`` in ``r = r0*exp(b*(th - theta0))``;
            unused (0) for ``helix``/``clothoid``.
        pitch: Height gain per radian along *axis* (0 = planar).
        length: Clothoid arc length (> 0).
        start_curvature: Clothoid curvature at ``s = 0``.
        end_curvature: Clothoid curvature at ``s = length``.
        start_heading: Clothoid tangent heading at ``s = 0`` (radians
            in the ``(u, v)`` frame).
        ref_direction: Optional in-plane reference for the ``(u, v)`` frame.
    """

    __slots__ = (
        "_kind",
        "_center",
        "_axis",
        "_u",
        "_v",
        "_theta0",
        "_theta1",
        "_r0",
        "_growth",
        "_pitch",
        "_length",
        "_k0",
        "_k1",
        "_phi0",
        "_xs",
        "_ys",
    )

    def __init__(
        self,
        kind: str,
        center: Vec,
        axis: Vec,
        theta0: float = 0.0,
        theta1: float = math.tau,
        r0: float = 1.0,
        growth: float = 0.0,
        pitch: float = 0.0,
        length: float = 0.0,
        start_curvature: float = 0.0,
        end_curvature: float = 0.0,
        start_heading: float = 0.0,
        ref_direction: Optional[Vec] = None,
    ) -> None:
        if kind not in _KINDS:
            raise ValueError(f"kind must be one of {_KINDS}, got {kind!r}")
        if kind == "clothoid":
            if length <= 0:
                raise ValueError("clothoid length must be positive")
            if pitch != 0:
                raise ValueError("clothoid is planar-only; pitch must be 0")
        else:
            if abs(theta1 - theta0) < 1e-12:
                raise ValueError("theta0 and theta1 must differ")
            if r0 <= 0:
                raise ValueError("r0 must be positive")
            if kind == "archimedean" and r0 + growth * (theta1 - theta0) <= 0:
                raise ValueError("end radius must stay positive")
        self._kind = kind
        self._center = center.copy()
        self._axis = axis.normalized()
        self._u, self._v = _basis(self._axis, ref_direction)
        self._theta0 = float(theta0)
        self._theta1 = float(theta1)
        self._r0 = float(r0)
        self._growth = float(growth)
        self._pitch = float(pitch)
        self._length = float(length)
        self._k0 = float(start_curvature)
        self._k1 = float(end_curvature)
        self._phi0 = float(start_heading)
        self._xs: List[float] = []
        self._ys: List[float] = []
        if kind == "clothoid":
            self._build_clothoid_table()

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def from_archimedean(
        cls,
        center: Vec,
        axis: Vec,
        r0: float,
        growth: float,
        theta0: float = 0.0,
        theta1: float = math.tau,
        pitch: float = 0.0,
        ref_direction: Optional[Vec] = None,
    ) -> "Spiral":
        """Create an Archimedean spiral ``r = r0 + growth*(th - theta0)``."""
        return cls(
            "archimedean",
            center,
            axis,
            theta0,
            theta1,
            r0,
            growth,
            pitch,
            ref_direction=ref_direction,
        )

    @classmethod
    def from_logarithmic(
        cls,
        center: Vec,
        axis: Vec,
        r0: float,
        growth: float,
        theta0: float = 0.0,
        theta1: float = math.tau,
        pitch: float = 0.0,
        ref_direction: Optional[Vec] = None,
    ) -> "Spiral":
        """Create a logarithmic spiral ``r = r0*exp(growth*(th - theta0))``."""
        return cls(
            "logarithmic",
            center,
            axis,
            theta0,
            theta1,
            r0,
            growth,
            pitch,
            ref_direction=ref_direction,
        )

    @classmethod
    def from_helix(
        cls,
        center: Vec,
        axis: Vec,
        radius: float,
        pitch: float,
        theta0: float = 0.0,
        theta1: float = math.tau,
        ref_direction: Optional[Vec] = None,
    ) -> "Spiral":
        """Create a 3D helix (constant radius, steady rise per radian)."""
        return cls(
            "helix", center, axis, theta0, theta1, radius, 0.0, pitch, ref_direction=ref_direction
        )

    @classmethod
    def from_clothoid(
        cls,
        center: Vec,
        axis: Vec,
        length: float,
        end_curvature: float,
        start_curvature: float = 0.0,
        start_heading: float = 0.0,
        ref_direction: Optional[Vec] = None,
    ) -> "Spiral":
        """Create a planar clothoid (curvature varies linearly with length)."""
        return cls(
            "clothoid",
            center,
            axis,
            0.0,
            0.0,
            1.0,
            0.0,
            0.0,
            length,
            start_curvature,
            end_curvature,
            start_heading,
            ref_direction=ref_direction,
        )

    # ------------------------------------------------------------------
    # Clothoid internals (Fresnel lookup, exact headings)
    # ------------------------------------------------------------------

    def _clothoid_rate(self) -> float:
        """Curvature change per unit length."""
        return (self._k1 - self._k0) / self._length

    def _clothoid_heading(self, s: float) -> float:
        """Exact tangent heading at arc position *s*."""
        c = self._clothoid_rate()
        return self._phi0 + self._k0 * s + 0.5 * c * s * s

    def _build_clothoid_table(self) -> None:
        """Integrate headings into a local ``(x, y)`` lookup table."""
        n = _CLOTHOID_STEPS
        ds = self._length / n
        # Trapezoid rule over exact headings.
        prev = self._clothoid_heading(0.0)
        x = y = 0.0
        self._xs = [0.0]
        self._ys = [0.0]
        for i in range(1, n + 1):
            cur = self._clothoid_heading(i * ds)
            x += math.cos((prev + cur) * 0.5) * ds
            y += math.sin((prev + cur) * 0.5) * ds
            self._xs.append(x)
            self._ys.append(y)
            prev = cur

    def _clothoid_point(self, s: float) -> Vec:
        """World point at clothoid arc position *s* (linear extension outside)."""
        n = _CLOTHOID_STEPS
        ds = self._length / n
        if s <= 0:
            x, y = self._xs[0], self._ys[0]
            phi = self._clothoid_heading(0.0)
            x += math.cos(phi) * s
            y += math.sin(phi) * s
        elif s >= self._length:
            x, y = self._xs[n], self._ys[n]
            phi = self._clothoid_heading(self._length)
            x += math.cos(phi) * (s - self._length)
            y += math.sin(phi) * (s - self._length)
        else:
            f = s / ds
            i = int(f)
            frac = f - i
            x = self._xs[i] + (self._xs[i + 1] - self._xs[i]) * frac
            y = self._ys[i] + (self._ys[i + 1] - self._ys[i]) * frac
        return self._center + self._u * x + self._v * y

    # ------------------------------------------------------------------
    # Radius law (non-clothoid kinds)
    # ------------------------------------------------------------------

    def _radius(self, th: float) -> float:
        """Planar radius at absolute angle *th*."""
        d = th - self._theta0
        if self._kind == "archimedean":
            return self._r0 + self._growth * d
        if self._kind == "logarithmic":
            return self._r0 * math.exp(self._growth * d)
        return self._r0  # helix

    def _dradius(self, th: float) -> float:
        """Derivative of radius w.r.t. angle at *th*."""
        if self._kind == "archimedean":
            return self._growth
        if self._kind == "logarithmic":
            return self._radius(th) * self._growth
        return 0.0

    def _theta_of_t(self, t: float) -> float:
        """Angle at normalised parameter *t*."""
        return self._theta0 + (self._theta1 - self._theta0) * t

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def point_at(self, t: float) -> Vec:
        """Point at normalised parameter *t* (0 → start, 1 → end)."""
        if self._kind == "clothoid":
            return self._clothoid_point(t * self._length)
        th = self._theta_of_t(t)
        r = self._radius(th)
        return (
            self._center
            + self._u * (r * math.cos(th))
            + self._v * (r * math.sin(th))
            + self._axis * (self._pitch * (th - self._theta0))
        )

    def tangent_at(self, t: float) -> Vec:
        """Unit tangent in traversal direction at *t*."""
        if self._kind == "clothoid":
            s = min(max(t * self._length, 0.0), self._length)
            phi = self._clothoid_heading(s)
            return (self._u * math.cos(phi) + self._v * math.sin(phi)).normalized()
        th = self._theta_of_t(t)
        r = self._radius(th)
        dr = self._dradius(th)
        d = (
            self._u * (dr * math.cos(th) - r * math.sin(th))
            + self._v * (dr * math.sin(th) + r * math.cos(th))
            + self._axis * self._pitch
        )
        if self._theta1 < self._theta0:
            d = -d
        return d.normalized()

    def tangent_at_start(self) -> Vec:
        """Unit tangent at the start of the spiral."""
        return self.tangent_at(0.0)

    def tangent_at_end(self) -> Vec:
        """Unit tangent at the end of the spiral."""
        return self.tangent_at(1.0)

    def curvature_at(self, t: float, h: float = 1e-4) -> float:
        """Curvature at *t* via central differences (approximation)."""
        t0 = min(max(t - h, 0.0), 1.0)
        t1 = min(max(t + h, 0.0), 1.0)
        if t1 - t0 < 1e-12:
            return 0.0
        tan0 = self.tangent_at(t0)
        tan1 = self.tangent_at(t1)
        ds = self.point_at(t0).distance_to(self.point_at(t1))
        if ds < 1e-12:
            return 0.0
        return tan0.angle_to(tan1) / ds

    def radius_at(self, t: float) -> float:
        """Perpendicular distance from the spiral axis at *t*."""
        d = self.point_at(t) - self._center
        axial = d @ self._axis
        return (d - self._axis * axial).length()

    def _speed(self, t: float) -> float:
        """Magnitude of ``dPos/dt`` (exact per family; bounds distance slope)."""
        if self._kind == "clothoid":
            return self._length
        th = self._theta_of_t(t)
        r = self._radius(th)
        dr = self._dradius(th)
        sweep = abs(self._theta1 - self._theta0)
        return sweep * math.sqrt(r * r + dr * dr + self._pitch * self._pitch)

    def sample(self, n: int = 100) -> List[Vec]:
        """Sample *n* evenly spaced (in *t*) points, inclusive of endpoints."""
        if n < 2:
            raise ValueError("sample requires at least 2 points")
        return [self.point_at(i / (n - 1)) for i in range(n)]

    # ------------------------------------------------------------------
    # Topology
    # ------------------------------------------------------------------

    @property
    def kind(self) -> str:
        """Spiral family (archimedean, logarithmic, helix, clothoid)."""
        return self._kind

    @property
    def start(self) -> Vec:
        """Start point of the spiral."""
        return self.point_at(0.0)

    @property
    def end(self) -> Vec:
        """End point of the spiral."""
        return self.point_at(1.0)

    @property
    def midpoint(self) -> Vec:
        """Midpoint of the spiral (at t=0.5)."""
        return self.point_at(0.5)

    @property
    def length(self) -> float:
        """Arc length (exact for clothoid, Simpson quadrature otherwise)."""
        if self._kind == "clothoid":
            return self._length
        # Simpson's rule over |dPos/dth|.
        n = 200
        a, b = self._theta0, self._theta1
        h = (b - a) / n

        def speed(th: float) -> float:
            r = self._radius(th)
            dr = self._dradius(th)
            return math.sqrt(r * r + dr * dr + self._pitch * self._pitch)

        total = speed(a) + speed(b)
        for i in range(1, n):
            total += speed(a + i * h) * (4.0 if i % 2 else 2.0)
        return abs(total * h / 3.0)

    @property
    def is_planar(self) -> bool:
        """Whether the spiral lies in a single plane (pitch == 0)."""
        return self._pitch == 0.0

    @property
    def normal(self) -> Optional[Vec]:
        """Plane normal for planar spirals, else None."""
        return self._axis if self.is_planar else None

    @property
    def plane(self) -> Plane:
        """Local frame (origin=center, x=u, y=v) of the spiral."""
        return Plane(self._center, self._u, self._v)

    @property
    def num_turns(self) -> float:
        """Number of revolutions (absolute sweep / 2π)."""
        if self._kind == "clothoid":
            turn = abs(self._clothoid_heading(self._length) - self._phi0)
            return turn / math.tau
        return abs(self._theta1 - self._theta0) / math.tau

    # ------------------------------------------------------------------
    # Arc-length walking + division
    # ------------------------------------------------------------------

    def _length_table(self, n: int = 512) -> tuple[List[float], float]:
        """Cumulative arc-length table over uniform *t* steps."""
        pts = self.sample(n + 1)
        cum = [0.0]
        for i in range(1, len(pts)):
            cum.append(cum[-1] + pts[i - 1].distance_to(pts[i]))
        return cum, cum[-1]

    def _t_of_length(self, d: float) -> float:
        """Normalised *t* at arc-length distance *d* from the start."""
        cum, total = self._length_table()
        d = min(max(d, 0.0), total)
        n = len(cum) - 1
        for i in range(1, n + 1):
            if cum[i] >= d:
                span = cum[i] - cum[i - 1]
                frac = (d - cum[i - 1]) / span if span > 1e-12 else 0.0
                return ((i - 1) + frac) / n
        return 1.0

    def point_at_length(self, d: float) -> Vec:
        """Point at arc-length distance *d* from the start."""
        return self.point_at(self._t_of_length(d))

    def tangent_at_length(self, d: float) -> Vec:
        """Unit tangent at arc-length distance *d* from the start."""
        return self.tangent_at(self._t_of_length(d))

    def divide(
        self,
        num: Optional[int] = None,
        dist: Optional[float] = None,
    ) -> list:
        """Distribute points at equal arc-length intervals (like Path.divide).

        Exactly one of *num* or *dist* must be given. Returns ``PathPoint``
        objects (``.t``, ``.point``, ``.tangent``).
        """
        from ifckit.geometry.path import PathPoint

        if (num is None) == (dist is None):
            raise ValueError("Exactly one of 'num' or 'dist' must be specified")
        _, total = self._length_table()
        if total < 1e-12:
            raise ValueError("Cannot divide a zero-length spiral")
        if num is not None:
            if num < 2:
                raise ValueError("num must be at least 2")
            step = total / (num - 1)
            count = num
        else:
            assert dist is not None
            if dist <= 0:
                raise ValueError("dist must be positive")
            count = max(2, math.ceil(total / dist) + 1)
            step = total / (count - 1)
        result = []
        for i in range(count):
            d = min(i * step, total)
            t = d / total
            result.append(
                PathPoint(t=t, point=self.point_at_length(d), tangent=self.tangent_at_length(d))
            )
        return result

    # ------------------------------------------------------------------
    # Plane intersection (pure Python, no OCC)
    # ------------------------------------------------------------------

    def intersect_plane(self, plane: Plane, tol: float = 1e-6) -> List[Tuple[float, Vec]]:
        """Return ``(t, point)`` pairs where the spiral crosses *plane*.

        *t* is normalised ``[0, 1]`` along arc length (same convention as
        :meth:`Path.intersect_plane`). Crossings are isolated by an adaptive
        scan (resolution scales with :attr:`num_turns`, so each step spans
        less than a 64th of a turn) and refined with bisection on the exact
        spiral — no OCC and no intermediate approximation. Tangent touches,
        which show no sign change, are found by slope-bounded golden-section
        search (an interval can only hide a touch if the distance can drop
        to zero within it, bounded by the exact per-family speed). A spiral
        lying (nearly) in *plane* has no discrete solution and is silently
        skipped.

        Args:
            plane: The cutting plane.
            tol: Geometric tolerance for on-plane checks and refinement.

        Returns:
            List of ``(t, point)`` tuples, empty if no intersection.
        """
        axis = plane.z_axis
        origin = plane.origin

        def signed(t: float) -> float:
            return (self.point_at(t) - origin) @ axis

        def bisect(ta: float, tb: float) -> float:
            """Bisect a sign-change bracket (guaranteed convergence).

            Converges on interval width, not on ``|d| <= tol``: near a flat
            (tangent) touch the latter spans a wide ``t``-range and would
            return a sloppy point that escapes deduplication.
            """
            da = signed(ta)
            for _ in range(60):
                tm = 0.5 * (ta + tb)
                dm = signed(tm)
                if (da < 0.0) == (dm < 0.0):
                    ta, da = tm, dm
                else:
                    tb = tm
                if tb - ta < 1e-13:
                    return 0.5 * (ta + tb)
            return 0.5 * (ta + tb)

        def refine_touch(ta: float, tb: float) -> float:
            """Golden-section minimisation of ``|signed(t)|`` (tangent touch).

            Converges on interval width (same reason as :func:`bisect`).
            """
            gr = (math.sqrt(5.0) - 1.0) / 2.0
            c = tb - gr * (tb - ta)
            d = ta + gr * (tb - ta)
            fc, fd = abs(signed(c)), abs(signed(d))
            for _ in range(80):
                if fc < fd:
                    tb, d, fd = d, c, fc
                    c = tb - gr * (tb - ta)
                    fc = abs(signed(c))
                else:
                    ta, c, fc = c, d, fd
                    d = ta + gr * (tb - ta)
                    fd = abs(signed(d))
                if tb - ta < 1e-13:
                    break
            return 0.5 * (ta + tb)

        # Scan resolution scales with the turn count: each step spans less
        # than a 64th of a turn, so each bracket holds at most one crossing.
        steps = max(256, int(math.ceil(self.num_turns * 64.0)))
        ds = [signed(i / steps) for i in range(steps + 1)]
        if all(abs(d) <= tol for d in ds):
            return []

        candidates: List[float] = []
        for i in range(steps):
            t0, t1 = i / steps, (i + 1) / steps
            d0, d1 = ds[i], ds[i + 1]
            if abs(d0) <= tol and abs(d1) <= tol:
                continue  # (near-)coplanar stretch
            if (d0 < 0.0) != (d1 < 0.0):
                candidates.append(bisect(t0, t1))
            elif abs(d0) <= tol or abs(d1) <= tol:
                # Sample on the plane (endpoint or transversal hit): exact.
                candidates.append(t0 if abs(d0) <= tol else t1)
            else:
                # No sign change: a touch hides here only if the distance can
                # reach zero within the interval (mean value theorem with the
                # exact speed bound; speed is monotone per family, so the max
                # over the interval sits at an endpoint).
                h = t1 - t0
                smax = max(self._speed(t0), self._speed(t1))
                if min(abs(d0), abs(d1)) <= smax * h / 2.0 + tol:
                    touch = refine_touch(t0, t1)
                    if abs(signed(touch)) <= tol:
                        candidates.append(touch)
        if not candidates:
            return []

        cum, total = self._length_table()
        if total < 1e-12:
            return []

        def length_at(t: float) -> float:
            f = min(max(t, 0.0), 1.0) * (len(cum) - 1)
            i = min(int(f), len(cum) - 2)
            return cum[i] + (cum[i + 1] - cum[i]) * (f - i)

        results: List[Tuple[float, Vec]] = []
        for t in sorted(candidates):
            pt = self.point_at(t)
            if results and pt.equals(results[-1][1], tol):
                continue
            results.append((length_at(t) / total, pt))
        return results

    # ------------------------------------------------------------------
    # Boundary conversion → Path (Path stays Line | Arc)
    # ------------------------------------------------------------------

    def to_biarcs(
        self,
        tol: float = 0.01,
        max_depth: int = 10,
        min_arc_angle: float = 0.001,
        plane: Optional[Plane] = None,
    ) -> "Path":
        """Approximate this spiral as bi-arcs → ``Path`` of ``Line`` + ``Arc``.

        Args:
            tol: Maximum deviation from the exact spiral.
            max_depth: Maximum recursion depth (default 10).
            min_arc_angle: Arcs below this angle (rad) collapse to lines.
            plane: Optional reference plane for projection + arc alignment.

        Returns:
            A ``Path`` containing only ``Line`` and ``Arc`` segments.
        """
        from ifckit.geometry.biarc import fit_biarcs, simplify_biarcs
        from ifckit.geometry.path import Path
        from ifckit.geometry.primitives import Arc, Line

        segments = fit_biarcs(self.point_at, tolerance=tol, max_depth=max_depth)
        if min_arc_angle > 0:
            segments = simplify_biarcs(segments, min_angle=min_arc_angle)
        path = Path(plane=plane)
        for seg in segments:
            if isinstance(seg, Arc):
                if plane is not None:
                    center_p = plane.closest_point(seg.center)
                    start_p = plane.closest_point(seg.start)
                    sign = 1.0 if (seg.normal @ plane.z_axis) >= 0 else -1.0
                    seg = Arc(center_p, plane.z_axis, start_p, seg.angle * sign)
                path._segments.append(seg)
            elif isinstance(seg, Line):
                if plane is not None:
                    seg = Line(plane.closest_point(seg.start), plane.closest_point(seg.end))
                path._segments.append(seg)
        return path

    def to_polyline(self, n: int = 100, closed: bool = False) -> "Path":
        """Sample to a ``Path`` of ``Line`` segments (Bonsai/IFC2X3-safe).

        Args:
            n: Number of sample points (>= 2).
            closed: If True, append a closing segment.
        """
        from ifckit.geometry.path import Path

        return Path.from_pts(self.sample(n), closed=closed)

    # ------------------------------------------------------------------
    # Transforms (uniform only — mirrors Arc.transformed)
    # ------------------------------------------------------------------

    def reverse(self) -> "Spiral":
        """Return a new spiral traversing the same locus in reverse."""
        if self._kind == "clothoid":
            phi_end = self._clothoid_heading(self._length)
            rev = Spiral(
                "clothoid",
                self.end,
                self._axis,
                0.0,
                0.0,
                1.0,
                0.0,
                0.0,
                self._length,
                -self._k1,
                -self._k0,
                phi_end + math.pi,
            )
            rev._u, rev._v = self._u.copy(), self._v.copy()
            rev._build_clothoid_table()
            return rev
        rev = Spiral(
            self._kind,
            # Re-anchor along the axis only: the planar offset at th is shared
            # with the original, so shifting by end would double-count it.
            self._center + self._axis * (self._pitch * (self._theta1 - self._theta0)),
            self._axis,
            self._theta1,
            self._theta0,
            self._radius(self._theta1),
            self._growth,
            self._pitch,
        )
        rev._u, rev._v = self._u.copy(), self._v.copy()
        return rev

    def transformed(self, t: "Transform") -> "Spiral":
        """Apply a 4×4 affine transform (uniform scale only).

        Raises:
            ValueError: On non-uniform scale (would distort the spiral law);
                use ``to_biarcs().transformed(t)`` instead.
        """
        if not t.is_uniform_scale():
            raise ValueError(
                "Spiral.transformed() does not support non-uniform scale "
                "(would distort the spiral law). "
                "Use spiral.to_biarcs().transformed(t) instead."
            )
        scale = abs(t.apply_vector(self._u))
        new = self.copy()
        new._center = t.apply(self._center)
        new._axis = t.apply_vector(self._axis).normalized()
        new._u = t.apply_vector(self._u).normalized()
        new._v = t.apply_vector(self._v).normalized()
        if self._kind == "archimedean":
            new._r0 *= scale
            new._growth *= scale
        elif self._kind == "logarithmic":
            new._r0 *= scale
        elif self._kind == "helix":
            new._r0 *= scale
        else:  # clothoid: headings invariant under similarity
            new._length *= scale
            new._k0 /= scale
            new._k1 /= scale
            new._build_clothoid_table()
        new._pitch *= scale
        return new

    def mirrored(self, plane: "Plane") -> "Spiral":
        """Mirror over an arbitrary plane. Returns a new Spiral."""
        return self.transformed(Transform.reflection(plane))

    def translated(self, delta: "Vec") -> "Spiral":
        """Translate by *delta*. Returns a new Spiral."""
        new = self.copy()
        new._center = self._center + delta
        return new

    def rotated(self, axis: "Vec", angle: float) -> "Spiral":
        """Rotate around *axis* by *angle* radians. Returns a new Spiral."""
        return self.transformed(Transform.rotation(axis, angle))

    def scaled(self, sx: float, sy: Optional[float] = None, sz: Optional[float] = None) -> "Spiral":
        """Scale by *sx*, *sy*, *sz*. Non-uniform raises ValueError."""
        if sy is None:
            sy = sx
        if sz is None:
            sz = sx
        return self.transformed(Transform.scaling(sx, sy, sz))

    def copy(self) -> "Spiral":
        """Return an independent copy."""
        new = Spiral(
            self._kind,
            self._center,
            self._axis,
            self._theta0,
            self._theta1,
            self._r0,
            self._growth,
            self._pitch,
            self._length,
            self._k0,
            self._k1,
            self._phi0,
        )
        new._u, new._v = self._u.copy(), self._v.copy()
        if self._kind == "clothoid":
            new._xs, new._ys = list(self._xs), list(self._ys)
        return new

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "type": "spiral",
            "kind": self._kind,
            "center": self._center.to_dict(),
            "axis": self._axis.to_dict(),
            "theta0": self._theta0,
            "theta1": self._theta1,
            "r0": self._r0,
            "growth": self._growth,
            "pitch": self._pitch,
            "length": self._length,
            "start_curvature": self._k0,
            "end_curvature": self._k1,
            "start_heading": self._phi0,
            "u": self._u.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Spiral":
        """Deserialize from a dict."""
        ref = Vec.from_dict(d["u"]) if "u" in d else None
        spiral = cls(
            kind=d["kind"],
            center=Vec.from_dict(d["center"]),
            axis=Vec.from_dict(d["axis"]),
            theta0=d.get("theta0", 0.0),
            theta1=d.get("theta1", math.tau),
            r0=d.get("r0", 1.0),
            growth=d.get("growth", 0.0),
            pitch=d.get("pitch", 0.0),
            length=d.get("length", 0.0),
            start_curvature=d.get("start_curvature", 0.0),
            end_curvature=d.get("end_curvature", 0.0),
            start_heading=d.get("start_heading", 0.0),
            ref_direction=ref,
        )
        return spiral

    def __repr__(self) -> str:
        if self._kind == "clothoid":
            return f"Spiral(clothoid, L={self._length:.3f}, k={self._k0:.4f}→{self._k1:.4f})"
        return (
            f"Spiral({self._kind}, r0={self._r0:.3f}, "
            f"sweep={math.degrees(self._theta1 - self._theta0):.1f}°)"
        )
