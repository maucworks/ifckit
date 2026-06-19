"""
ifckit.geometry.curve
=====================

Curve — a NURBS/BSpline curve with evaluation (De Boor) and IFC serialisation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

from ifckit.geometry.primitives import Arc, Line, Plane, Vec
from ifckit.geometry.transform import Transform

if TYPE_CHECKING:
    import ifcopenshell

    from ifckit.geometry.path import Path


# ---------------------------------------------------------------------------
# 4D homogeneous helpers
# ---------------------------------------------------------------------------

_Homo4D = Tuple[float, float, float, float]  # (wx, wy, wz, w)


def _build_full_knots(knots: Sequence[float], multiplicities: Sequence[int]) -> List[float]:
    """Expand compact (knot, mult) pairs into the full knot vector."""
    out: List[float] = []
    for k, m in zip(knots, multiplicities):
        out.extend([float(k)] * m)
    return out


def _cox_de_boor(span: int, p: int, u: float, uknots: List[float]) -> List[float]:
    """Evaluate p+1 non‑zero B‑spline basis functions at *u* (Alg 2.2)."""
    left: List[float] = [0.0] * (p + 1)
    right: List[float] = [0.0] * (p + 1)
    N: List[float] = [0.0] * (p + 1)
    N[0] = 1.0
    for j in range(1, p + 1):
        left[j] = u - uknots[span + 1 - j]
        right[j] = uknots[span + j] - u
        saved = 0.0
        for r in range(j):
            denom = right[r + 1] + left[j - r]
            if abs(denom) > 1e-12:
                t = N[r] / denom
                N[r] = saved + right[r + 1] * t
                saved = left[j - r] * t
            else:
                saved = 0.0
        N[j] = saved
    return N


def _cox_de_boor_deriv(span: int, p: int, u: float, uknots: List[float]) -> List[float]:
    """First derivative of the p+1 non‑zero basis functions at *u*."""
    Np = _cox_de_boor(span, p - 1, u, uknots)
    dN: List[float] = [0.0] * (p + 1)
    for i in range(p + 1):
        j = span - p + i
        a = uknots[j + p] - uknots[j]
        b = uknots[j + p + 1] - uknots[j + 1]
        if i < p:
            dN[i] = (p / a) * Np[i] if abs(a) > 1e-12 else 0.0
        if i > 0:
            dN[i] -= (p / b) * Np[i - 1] if abs(b) > 1e-12 else 0.0
    return dN


def _find_knot_span(u: float, p: int, n: int, uknots: List[float]) -> int:
    """Binary search for the knot span containing *u* (Alg 2.1)."""
    if u >= uknots[n + 1]:
        return n
    if u <= uknots[p]:
        return p
    lo, hi = p, n + 1
    mid = (lo + hi) // 2
    while u < uknots[mid] or u >= uknots[mid + 1]:
        if u < uknots[mid]:
            hi = mid
        else:
            lo = mid
        mid = (lo + hi) // 2
    return mid


# ---------------------------------------------------------------------------
# Cox‑de Boor evaluation
# ---------------------------------------------------------------------------


def _eval_homo(p: int, uknots: List[float], pts: List[_Homo4D], u: float) -> _Homo4D:
    """Evaluate a (homogeneous) BSpline at *u* via Cox‑de Boor basis functions."""
    n = len(pts) - 1
    span = _find_knot_span(u, p, n, uknots)
    N = _cox_de_boor(span, p, u, uknots)
    res = [0.0, 0.0, 0.0, 0.0]
    for i in range(p + 1):
        idx = span - p + i
        w = pts[idx]
        ni = N[i]
        res[0] += w[0] * ni
        res[1] += w[1] * ni
        res[2] += w[2] * ni
        res[3] += w[3] * ni
    return tuple(res)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Curve
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Curve
# ---------------------------------------------------------------------------


class Curve:
    """A NURBS / BSpline curve evaluated via the De Boor algorithm.

    IFC convention: the parameter lives in the knot domain
    ``[knots[0], knots[-1]]``.  ``Curve.point_at(t)`` accepts a **normalised**
    parameter ``t ∈ [0, 1]`` that is linearly mapped to the knot domain,
    consistent with ``Path.point_at(t)``.

    Args:
        control_points:  Control polygon vertices.
        knots:           Unique knot values (compact form).
        multiplicities:  Multiplicity of each unique knot.
        degree:          Curve degree.
        weights:         Weights for rational NURBS (``None`` = non‑rational).
        closed:          Whether the curve is closed in IFC sense.
    """

    def __init__(
        self,
        control_points: Sequence[Vec],
        knots: Sequence[float],
        multiplicities: Sequence[int],
        degree: int,
        weights: Optional[Sequence[float]] = None,
        closed: bool = False,
    ) -> None:
        ncpts = len(control_points)
        nknots = sum(multiplicities)
        expected = ncpts + degree + 1
        if nknots != expected:
            raise ValueError(
                f"Knot vector length ({nknots}) must equal control_points + degree + 1 ({expected})"
            )
        if degree < 1:
            raise ValueError(f"Degree must be >= 1, got {degree}")

        self.degree = degree
        self.points = [Vec(*p) if not isinstance(p, Vec) else p for p in control_points]
        self.knots = list(knots)
        self.multiplicities = list(multiplicities)
        self._weights = list(weights) if weights is not None else None
        self.closed = closed

        self._uknots = _build_full_knots(self.knots, self.multiplicities)

    # ── properties ──────────────────────────────────────────────────

    @property
    def rational(self) -> bool:
        return self._weights is not None

    @property
    def knot_domain(self) -> Tuple[float, float]:
        return self._uknots[0], self._uknots[-1]

    # ── parameter mapping ──────────────────────────────────────────

    def _u_of_t(self, t: float) -> float:
        u0, u1 = self.knot_domain
        if u1 - u0 < 1e-12:
            return u0
        t = max(0.0, min(1.0, t))
        return u0 + t * (u1 - u0)

    # ── evaluation ──────────────────────────────────────────────────

    def _homo_points(self) -> List[_Homo4D]:
        n = len(self.points)
        w = self._weights if self._weights is not None else [1.0] * n
        return [
            (self.points[i].x * w[i], self.points[i].y * w[i], self.points[i].z * w[i], w[i])
            for i in range(n)
        ]

    def point_at(self, t: float) -> Vec:
        """Evaluate point at normalised parameter ``t ∈ [0, 1]``."""
        u = self._u_of_t(t)
        h = _eval_homo(self.degree, self._uknots, self._homo_points(), u)
        if abs(h[3]) > 1e-12:
            return Vec(h[0] / h[3], h[1] / h[3], h[2] / h[3])
        return Vec(h[0], h[1], h[2])

    def tangent_at(self, t: float) -> Vec:
        """Evaluate unit tangent at normalised parameter ``t ∈ [0, 1]``.

        Uses central finite differences for robustness at clamped endpoints.
        """
        eps = 1e-6 * (self._uknots[-1] - self._uknots[0]) if len(self._uknots) > 1 else 1e-6
        t0 = max(0.0, t - eps)
        t1 = min(1.0, t + eps)
        p0 = self.point_at(t0)
        p1 = self.point_at(t1)
        v = (p1 - p0) / (t1 - t0)
        n = v.normalized()
        return n if n is not None else Vec(0, 0, 0)

    @property
    def length(self) -> float:
        """Numerical arc length via chord-length approximation."""
        n = max(50, 4 * self.degree)
        pts = self.sample(n)
        return sum((pts[i + 1] - pts[i]).length() for i in range(len(pts) - 1))

    def sample(self, n: int = 50) -> List[Vec]:
        """Sample *n* evenly‑spaced points in parameter space ``[0, 1]``."""
        return [self.point_at(i / max(n - 1, 1)) for i in range(n)]

    def reverse(self) -> "Curve":
        """Return a new curve with reversed direction.

        The new curve traverses the same geometry from end to start.
        Both control points and knot vector are reflected.
        """
        new_points = list(reversed(self.points))
        new_weights = list(reversed(self._weights)) if self._weights else None

        # Reflect interior knots:  k → k_first + k_last − k
        # then sort ascending to maintain valid knot vector
        k0, k1 = self.knots[0], self.knots[-1]
        interior = sorted(k0 + k1 - k for k in self.knots[1:-1])
        new_knots = [k0] + interior + [k1]

        return Curve(
            control_points=new_points,
            knots=new_knots,
            multiplicities=self.multiplicities,
            degree=self.degree,
            weights=new_weights,
            closed=self.closed,
        )

    # --- affine transforms (pure Python, no OCC needed) ------------------

    def transformed(self, t: "Transform") -> "Curve":
        """Apply a 4×4 affine transform to all control points.

        Works for any affine transform (translation, rotation, scale,
        reflection).  No OCC dependency needed — NURBS control points
        are transformed directly (Piegl & Tiller §6.5).
        """
        return Curve(
            control_points=[t.apply(cp) for cp in self.points],
            knots=list(self.knots),
            multiplicities=list(self.multiplicities),
            degree=self.degree,
            weights=list(self._weights) if self._weights else None,
            closed=self.closed,
        )

    def mirrored(self, plane: "Plane") -> "Curve":
        """Mirror over an arbitrary plane. Returns a new Curve."""
        return self.transformed(Transform.reflection(plane))

    def translated(self, delta: "Vec") -> "Curve":
        """Translate by *delta*. Returns a new Curve."""
        return self.transformed(Transform.translation(delta))

    def rotated(self, axis: "Vec", angle: float) -> "Curve":
        """Rotate around *axis* by *angle* radians. Returns a new Curve."""
        return self.transformed(Transform.rotation(axis, angle))

    def scaled(
        self, sx: float, sy: "Optional[float]" = None, sz: "Optional[float]" = None
    ) -> "Curve":
        """Scale by *sx*, *sy*, *sz*. Returns a new Curve."""
        if sy is None:
            sy = sx
        if sz is None:
            sz = sx
        return self.transformed(Transform.scaling(sx, sy, sz))

    def copy(self) -> "Curve":
        """Return an independent deep copy."""
        return Curve(
            control_points=[cp.copy() for cp in self.points],
            knots=list(self.knots),
            multiplicities=list(self.multiplicities),
            degree=self.degree,
            weights=list(self._weights) if self._weights else None,
            closed=self.closed,
        )

    def to_mesh_dict(
        self,
        n_points: int = 50,
        label: str = "",
        material: "dict | None" = None,
        y_up: bool = True,
    ) -> dict:
        """Serialize the curve as a polyline for 3D viewer consumption.

        Args:
            n_points:   Number of sample points.
            label:      Display name.
            material:   Visual properties (color, opacity, …).
            y_up:       If True (default), convert coordinates to
                        Three.js/glTF Y-up: ``(x, z, -y)``.

        Returns:
            A dict with ``primitive``, ``positions``, and optional
            ``label``, ``material`` keys.
        """
        pts = self.sample(n_points)
        if y_up:
            flat = [c for v in pts for c in (v.x, v.z, -v.y)]
        else:
            flat = [c for v in pts for c in (v.x, v.y, v.z)]
        d: dict = {
            "primitive": "line-strip",
            "positions": flat,
            "label": label or "Curve",
        }
        if material is not None:
            d["material"] = material
        return d

    def preview(
        self,
        label: str = "",
        material: "dict | None" = None,
        n_points: int = 50,
        y_up: bool = True,
    ) -> dict:
        """Return a ``__type__: "mesh"`` dict ready for the viewer pipeline."""
        return {
            "__type__": "mesh",
            **self.to_mesh_dict(label=label, material=material, n_points=n_points, y_up=y_up),
        }

    @property
    def start_point(self) -> Vec:
        return self.point_at(0.0)

    @property
    def end_point(self) -> Vec:
        return self.point_at(1.0)

    # ── bi‑arc fitting ──────────────────────────────────────────────

    def to_biarcs(
        self,
        tol: float = 0.01,
        max_iteration: int = 10,
        min_arc_angle: float = 0.001,
        plane: Optional[Plane] = None,
    ) -> "Path":
        """Approximate this NURBS curve as bi‑arcs → ``Path`` of ``Line`` + ``Arc``.

        Uses recursive bi‑arc fitting (``ifckit.geometry.biarc.fit_biarcs``).

        Args:
            tol:           Maximum deviation from the original curve.
            max_iteration: Maximum recursion depth (default 10).
            min_arc_angle: Arcs with ``|angle| < min_arc_angle`` (rad) are collapsed
                           to lines and G1 is iteratively restored (default 0.001).
            plane:         Optional reference plane.  When given, all points are
                           projected onto this plane and arc normals are set to
                           ``plane.z_axis``.  The resulting ``Path._plane`` is set,
                           enabling downstream methods (``continued``) to use the
                           plane for arc alignment.

        Returns:
            A ``Path`` containing only ``Line`` and ``Arc`` segments.
        """
        from ifckit.geometry.biarc import fit_biarcs, simplify_biarcs
        from ifckit.geometry.path import Path

        segments = fit_biarcs(self.point_at, tolerance=tol, max_depth=max_iteration)
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

    def to_path(
        self,
        tolerance: float = 0.01,
        max_depth: int = 10,
        min_arc_angle: float = 0.001,
    ) -> "Path":
        """Alias for :meth:`to_biarcs`."""
        return self.to_biarcs(tol=tolerance, max_iteration=max_depth, min_arc_angle=min_arc_angle)

    # ── IFC serialisation ──────────────────────────────────────────

    def _to_ifc_points(self, ifc_file: "ifcopenshell.file") -> list:
        from ifckit.builders._geom import pt3

        return [pt3(ifc_file, v.x, v.y, v.z) for v in self.points]

    def to_ifc_bspline(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        """Create an ``IfcBSplineCurveWithKnots`` (non‑rational)."""
        if self.rational:
            raise ValueError("Use to_ifc_rational() for rational NURBS curves")
        e = ifc_file.create_entity("IfcBSplineCurveWithKnots")
        e.Degree = self.degree
        e.ControlPointsList = self._to_ifc_points(ifc_file)
        e.CurveForm = "UNSPECIFIED"
        e.ClosedCurve = self.closed
        e.SelfIntersect = False
        e.Knots = self.knots
        e.KnotMultiplicities = self.multiplicities
        e.KnotSpec = "UNSPECIFIED"
        return e

    def to_ifc_rational(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        """Create an ``IfcRationalBSplineCurveWithKnots``."""
        if not self.rational:
            raise ValueError("Use to_ifc_bspline() for non‑rational curves")
        e = ifc_file.create_entity("IfcRationalBSplineCurveWithKnots")
        e.Degree = self.degree
        e.ControlPointsList = self._to_ifc_points(ifc_file)
        e.CurveForm = "UNSPECIFIED"
        e.ClosedCurve = self.closed
        e.SelfIntersect = False
        e.Knots = self.knots
        e.KnotMultiplicities = self.multiplicities
        e.KnotSpec = "UNSPECIFIED"
        e.WeightsData = self._weights
        return e

    # ── serialisation ──────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "degree": self.degree,
            "control_points": [v.to_dict() for v in self.points],
            "knots": self.knots,
            "multiplicities": self.multiplicities,
            "closed": self.closed,
        }
        if self._weights is not None:
            d["weights"] = self._weights
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Curve":
        return cls(
            control_points=[Vec.from_dict(v) for v in d["control_points"]],
            knots=d["knots"],
            multiplicities=d["multiplicities"],
            degree=d["degree"],
            weights=d.get("weights"),
            closed=d.get("closed", False),
        )

    def __repr__(self) -> str:
        w_str = ", rational" if self.rational else ""
        return (
            f"Curve(degree={self.degree}, "
            f"{len(self.points)} points, "
            f"knots={self.knots[:3]}...{self.knots[-3:]}{w_str})"
        )

    # ── Hermite-style construction ──────────────────────────────────

    @classmethod
    def from_tangents(
        cls,
        start: Vec,
        tan_start: Vec,
        end: Vec,
        tan_end: Vec,
        scale: float | None = None,
    ) -> "Curve":
        """Create a cubic Bezier curve from two points and their tangents.

        The curve passes through *start* and *end* with the given
        tangent directions at each endpoint.  The tangent **magnitude**
        determines the curve stiffness — a longer tangent pulls the
        curve further before bending toward the other endpoint.

        Args:
            start:      Start point.
            tan_start:  Start tangent (direction + magnitude).
            end:        End point.
            tan_end:    End tangent (direction + magnitude).
            scale:      Optional uniform multiplier to override both
                        tangent magnitudes.  When ``None`` (default)
                        the magnitude of each tangent vector is used
                        directly (falling back to ``|end - start| / 3``
                        for zero‑length tangents).

        Returns:
            A new degree‑3 BSpline (cubic Bezier) Curve.
        """
        chord = end - start
        default = chord.length() / 3.0

        ts_len = tan_start.length()
        te_len = tan_end.length()
        use_start = ts_len if ts_len > 1e-12 else default
        use_end = te_len if te_len > 1e-12 else default

        if scale is not None:
            use_start = use_end = scale

        ts = tan_start.normalized() * use_start if ts_len > 1e-12 else Vec(0, 0, 0)
        te = tan_end.normalized() * use_end if te_len > 1e-12 else Vec(0, 0, 0)

        control_points = [start, start + ts, end - te, end]
        knots = [0.0, 1.0]
        mults = [4, 4]
        return cls(
            control_points=control_points,
            knots=knots,
            multiplicities=mults,
            degree=3,
        )

    # ── Interpolation through points ────────────────────────────────

    @classmethod
    def from_points(
        cls,
        points: "Sequence[Vec]",
        degree: int = 3,
        tan_start: "Vec | None" = None,
        tan_end: "Vec | None" = None,
        knots: "Sequence[float] | None" = None,
    ) -> "Curve":
        """Interpolate a BSpline curve through a set of points.

        Uses OCC ``GeomAPI_Interpolate`` (requires ``pythonocc-core``).

        Args:
            points:    Points the curve must pass through (minimum 2).
            degree:    Target degree (default 3).  Minimum is clamped to
                      ``min(len(points) - 1, 3)``.
            tan_start: Optional start tangent for G1 end condition.
            tan_end:   Optional end tangent for G1 end condition.
            knots:     Optional explicit knot parameters ``∈ [0, 1]``.
                      Length must equal ``len(points)``.  When ``None``
                      chord‑length parameterisation is used.

        Returns:
            A new ``Curve`` through all *points*.
        """
        try:
            from OCC.Core.Geom import Geom_BSplineCurve
            from OCC.Core.GeomAPI import GeomAPI_Interpolate
            from OCC.Core.gp import gp_Pnt, gp_Vec
            from OCC.Core.TColgp import TColgp_HArray1OfPnt
            from OCC.Core.TColStd import TColStd_HArray1OfReal
        except ImportError:
            raise ImportError("Curve.from_points() requires pythonocc-core")

        n = len(points)
        if n < 2:
            raise ValueError("Need at least 2 points")

        pts_arr = TColgp_HArray1OfPnt(1, n)
        for i, p in enumerate(points):
            pts_arr.SetValue(i + 1, gp_Pnt(p.x, p.y, p.z))

        if knots is not None:
            if len(knots) != n:
                raise ValueError(f"knots length ({len(knots)}) must match points ({n})")
            par_arr = TColStd_HArray1OfReal(1, n)
            for i, k in enumerate(knots):
                par_arr.SetValue(i + 1, float(k))
            interp = GeomAPI_Interpolate(pts_arr, par_arr, False, 1e-6)
        else:
            interp = GeomAPI_Interpolate(pts_arr, False, 1e-6)

        if tan_start is not None or tan_end is not None:
            if tan_start is not None and tan_end is not None:
                interp.Load(
                    gp_Vec(tan_start.x, tan_start.y, tan_start.z),
                    gp_Vec(tan_end.x, tan_end.y, tan_end.z),
                )
            elif tan_start is not None:
                interp.Load(gp_Vec(tan_start.x, tan_start.y, tan_start.z))
            else:
                interp.Load(gp_Vec(tan_end.x, tan_end.y, tan_end.z))

        interp.Perform()

        curve = interp.Curve()
        bspline = Geom_BSplineCurve.DownCast(curve)
        if bspline is None:
            raise RuntimeError("GeomAPI_Interpolate did not produce a BSpline")

        poles = [
            Vec(bspline.Pole(i + 1).X(), bspline.Pole(i + 1).Y(), bspline.Pole(i + 1).Z())
            for i in range(bspline.NbPoles())
        ]

        return cls(
            control_points=poles,
            knots=[bspline.Knot(i + 1) for i in range(bspline.NbKnots())],
            multiplicities=[bspline.Multiplicity(i + 1) for i in range(bspline.NbKnots())],
            degree=bspline.Degree(),
        )

    @classmethod
    def assemble(
        cls,
        curves: "Sequence[Curve]",
        tol: float = 1e-6,
    ) -> "List[Curve]":
        """Join end-to-start connected curves into continuous BSpline curves.

        Uses OCC ``GeomConvert_CompCurveToBSplineCurve``.  Curves that
        are not G0‑connected (gap larger than *tol*) are split into
        separate groups.

        Args:
            curves:  Sequence of curves to join (must be G0 at
                     connections within *tol*).
            tol:     G0 tolerance for joining.

        Returns:
            List of joined ``Curve`` objects.
        """
        try:
            from OCC.Core.GeomConvert import GeomConvert_CompCurveToBSplineCurve
        except ImportError:
            raise ImportError("Curve.assemble() requires pythonocc-core") from None

        from ifckit.geometry.surface import _build_occ_curve, _curve_from_occ_bspline

        if not curves:
            return []

        # ── 1. Orient curves — try all 4 endpoint permutations ─────
        oriented: list = [curves[0]]
        groups: list[list] = []

        def _p(pts, i):
            return pts[i].point_at(0), pts[i].point_at(1)

        for i in range(1, len(curves)):
            prev_start, prev_end = _p(oriented, -1)
            curr_start, curr_end = _p(curves, i)

            def _dist(a, b):
                return (a - b).length()

            fwd = _dist(prev_end, curr_start)  # c0 → c1
            rev = _dist(prev_end, curr_end)  # c0 → c1⁻¹
            p_rev = _dist(prev_start, curr_start)  # c0⁻¹ → c1
            p_rev_r = _dist(prev_start, curr_end)  # c0⁻¹ → c1⁻¹

            if min(fwd, rev, p_rev, p_rev_r) > tol:
                groups.append(oriented)
                oriented = [curves[i]]
                continue

            def _apply(c, fl):
                return c.reverse() if fl else c

            if fwd <= tol:
                oriented.append(curves[i])
            elif rev <= tol:
                oriented.append(curves[i].reverse())
            elif p_rev <= tol:
                oriented[-1] = oriented[-1].reverse()
                oriented.append(curves[i])
            else:  # p_rev_r
                oriented[-1] = oriented[-1].reverse()
                oriented.append(curves[i].reverse())

        groups.append(oriented)

        # ── 2. Build OCC BSplineJoin for each group ────────────────
        from OCC.Core.GeomConvert import GeomConvert_CompCurveToBSplineCurve

        result: list = []
        for grp in groups:
            occ = [_build_occ_curve(c) for c in grp]
            joiner = GeomConvert_CompCurveToBSplineCurve()
            for oc in occ:
                joiner.Add(oc, tol)
            try:
                joined = joiner.BSplineCurve()
                result.append(_curve_from_occ_bspline(joined))
            except BaseException:
                # Join failed — add curves individually
                for c in grp:
                    result.append(c)

        return result

    @classmethod
    def from_occ_edge(cls, edge) -> "Curve":
        """Create a Curve from an OCC ``TopoDS_Edge``.

        Supports both FreeCAD ``Part.Edge`` and raw ``pythonocc-core``
        ``TopoDS_Edge``.  The edge must contain a ``Geom_BSplineCurve``
        — lines and circles are not supported (use ``Path`` for those).
        """
        # Try FreeCAD API (edge.Curve.getPoles)
        curve_attr = getattr(edge, "Curve", None)
        if curve_attr is not None and hasattr(curve_attr, "getPoles"):
            curve = curve_attr
            poles = [Vec(p.x, p.y, p.z) for p in curve.getPoles()]
            knots = list(curve.getKnots())
            mults = list(curve.getMultiplicities())
            degree = curve.Degree
            weights = list(curve.getWeights()) if curve.isRational() else None
            closed = curve.isPeriodic()
            return cls(
                control_points=poles,
                knots=knots,
                multiplicities=mults,
                degree=degree,
                weights=weights,
                closed=closed,
            )

        # Fall back to pythonocc-core API
        try:
            from OCC.Core.BRep import BRep_Tool
            from OCC.Core.Geom import Geom_BSplineCurve
        except ImportError:
            raise ImportError("Curve.from_occ_edge() requires either FreeCAD or pythonocc-core")

        result = BRep_Tool.Curve(edge)
        if result is None:
            raise TypeError("Edge has no curve")
        curve_handle, first_param, last_param = result

        # Downcast to BSpline
        bspline = Geom_BSplineCurve.DownCast(curve_handle)
        if bspline is None:
            raise TypeError("Edge contains a non-BSpline curve. Use Path for line/circle segments.")

        # If the edge is trimmed (parameter range ≠ full curve domain),
        # sample the edge within its actual bounds — the raw BSpline
        # extends beyond the edge's trim limits.
        k0 = bspline.Knot(1)
        k1 = bspline.Knot(bspline.NbKnots())
        eps = 1e-4 * max(1.0, abs(k1 - k0))
        if abs(first_param - k0) > eps or abs(last_param - k1) > eps:
            from OCC.Core.BRepAdaptor import BRepAdaptor_Curve

            adaptor = BRepAdaptor_Curve(edge)
            n = max(20, bspline.Degree() * 4)
            pts = []
            for i in range(n):
                u = first_param + (last_param - first_param) * i / (n - 1)
                p = adaptor.Value(u)
                pts.append(Vec(p.X(), p.Y(), p.Z()))
            try:
                return cls.from_points(pts, degree=min(3, len(pts) - 1))
            except BaseException:
                pass  # fall through to full-curve extraction below

        poles = []
        for i in range(bspline.NbPoles()):
            p = bspline.Pole(i + 1)
            poles.append(Vec(p.X(), p.Y(), p.Z()))

        knots = [bspline.Knot(i + 1) for i in range(bspline.NbKnots())]
        mults = [bspline.Multiplicity(i + 1) for i in range(bspline.NbKnots())]
        degree = bspline.Degree()
        weights = (
            [bspline.Weight(i + 1) for i in range(bspline.NbPoles())]
            if bspline.IsRational()
            else None
        )
        closed = bspline.IsPeriodic()

        return cls(
            control_points=poles,
            knots=knots,
            multiplicities=mults,
            degree=degree,
            weights=weights,
            closed=closed,
        )
