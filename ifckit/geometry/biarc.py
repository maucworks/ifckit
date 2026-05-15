"""
ifckit.geometry.biarc
=====================

Bi-arc solver and recursive curve-to-biarcs fitter.

Translates the C# implementation from ``A171-gh-mauc/Core/BiarcSolver.cs``
and ``BiarcFitter.cs``.
"""

from __future__ import annotations

import math
from typing import Callable, List, Optional, Tuple

from ifckit.geometry.primitives import Arc, Line, Vec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _perp_in_plane(tangent: Vec, normal: Vec) -> Vec:
    """Unit vector perpendicular to *tangent* in the plane defined by *normal*."""
    try:
        p = (normal**tangent).normalized()
    except ValueError:
        return Vec(0, 0, 0)
    return p if p is not None else Vec(0, 0, 0)


def _signed_angle(a: Vec, b: Vec, axis: Vec) -> float:
    """Signed angle from *a* to *b* around *axis* (right-hand rule)."""
    cross = a**b
    sign = 1.0 if (cross @ axis) >= 0 else -1.0
    angle = a.angle_to(b)
    return sign * angle


def _closest_point_on_path(point: Vec, segments: list) -> float:
    """Minimum distance from *point* to any segment (Line or Arc)."""
    min_dist = float("inf")
    for seg in segments:
        if seg is None:
            continue
        if isinstance(seg, Line):
            d = _dist_to_line(point, seg)
        elif isinstance(seg, Arc):
            d = _dist_to_arc(point, seg)
        else:
            d = _dist_to_line(point, seg)
        if d < min_dist:
            min_dist = d
    return min_dist


def _dist_to_line(p: Vec, line: Line) -> float:
    """Exact perpendicular distance from *p* to a line segment."""
    ab = line.end - line.start
    ap = p - line.start
    t = (ap @ ab) / (ab @ ab) if (ab @ ab) > 1e-12 else 0.0
    t = max(0.0, min(1.0, t))
    closest = line.start + ab * t
    return (p - closest).length()


def _dist_to_arc(p: Vec, arc: Arc) -> float:
    """Distance from *p* to an arc, approximated by sampling."""
    samples = arc.sample(3)  # ~3° step → dense for small arcs
    return min((p - s).length() for s in samples)


# ---------------------------------------------------------------------------
# Arc construction
# ---------------------------------------------------------------------------


def build_arc_from_start_tangent(
    start: Vec, tangent: Vec, end: Vec, flip_normal: bool = False
) -> Tuple[Optional[Arc], float]:
    """Build an ``Arc`` from *start* with given *tangent* to *end*.

    Returns ``(None, 0.0)`` when the construction is degenerate
    (collinear → use a ``Line`` instead).
    """
    chord = end - start
    chord_len = chord.length()
    if chord_len < 1e-12:
        return None, 0.0

    # Normal of the arc plane (C# BuildArcWithTangent)
    if flip_normal:
        normal_raw = chord**tangent
    else:
        normal_raw = tangent**chord

    try:
        n = normal_raw.normalized()
    except ValueError:
        return None, 0.0
    if n is None:
        return None, 0.0

    # Perpendicular direction in arc plane
    try:
        perp = _perp_in_plane(tangent, n)
    except ValueError:
        return None, 0.0

    w = end - start
    den = 2.0 * (perp @ w)
    if abs(den) < 1e-12:
        return None, 0.0

    s = (w @ w) / den
    center = start + perp * s
    radius = abs(s)

    r0 = start - center
    r1 = end - center

    # Signed angle from r0 to r1 around n
    angle = _signed_angle(r0, r1, n)

    arc = Arc(center, n, start, angle)

    # Verify the arc points in the correct direction.
    # If the computed tangent at t=0 opposes the input tangent,
    # flip the normal and invert the angle.
    actual = arc.tangent_at(0.0)
    if actual is not None and (actual @ tangent) < 0:
        # Wrong direction — flip
        arc = Arc(center, n * -1, start, -angle)

    return arc, radius


# ---------------------------------------------------------------------------
# Biarc solver (Distinct plane mode — true 3D)
# ---------------------------------------------------------------------------


def solve_biarc(p0: Vec, t0: Vec, p1: Vec, t1: Vec) -> Tuple[Optional[Arc], Optional[Arc], Vec]:
    """Solve a balanced bi-arc in 3D (distinct planes).

    Args:
        p0: Start point.
        t0: Start tangent (will be normalised).
        p1: End point.
        t1: End tangent (will be normalised).

    Returns:
        ``(arc0, arc1, joint)`` where each arc is an ``Arc`` or ``Line``
        (``None`` for degenerate segments), and *joint* is the shared
        endpoint of the two arcs.
    """
    eps = 1e-9

    # Normalise tangents
    t0 = t0.normalized()
    t1 = t1.normalized()
    if t0 is None or t1 is None:
        return None, None, p0

    chord = p1 - p0
    chord_len = chord.length()
    if chord_len < eps:
        return None, None, p0

    # Balanced d-parameter (Piegl & Tiller style)
    v_dot_t = chord @ (t0 + t1)
    t0t1 = t0 @ t1
    v_dot_v = chord @ chord
    denom = 2.0 * (1.0 - t0t1)

    if abs(denom) < eps:
        # Parallel (or anti-parallel) tangents
        v_dot_t1 = chord @ t1
        if abs(v_dot_t1) < eps:
            # Semicircle case — split at midpoint
            mid = (p0 + p1) * 0.5
            a0 = Line(p0, mid)
            a1 = Line(mid, p1)
            return a0, a1, mid
        d = v_dot_v / (4.0 * v_dot_t1)
    else:
        disc = v_dot_t * v_dot_t + denom * v_dot_v
        d = (-v_dot_t + math.sqrt(max(0.0, disc))) / denom

    # Joint
    q0 = p0 + d * t0
    q1 = p1 - d * t1
    joint = (q0 + q1) * 0.5

    # Build Arc0: from P0 with tangent T0 to Joint
    arc0, _ = build_arc_from_start_tangent(p0, t0, joint, flip_normal=False)
    if arc0 is None:
        arc0 = Line(p0, joint)

    # Build Arc1: from P1 with tangent T1 to Joint, then reverse
    # (the solver naturally creates arcs toward the joint; PolyCurve
    #  chaining expects Joint → P1 for the second arc)
    arc1_raw, _ = build_arc_from_start_tangent(p1, t1, joint, flip_normal=True)
    if arc1_raw is None:
        arc1 = Line(joint, p1)
    elif isinstance(arc1_raw, Arc):
        # Reverse: go from Joint to P1 instead of P1 to Joint
        arc1 = Arc(arc1_raw.center, arc1_raw.normal, arc1_raw.end, -arc1_raw.angle)
    else:
        arc1 = arc1_raw.reverse() if hasattr(arc1_raw, "reverse") else arc1_raw

    return arc0, arc1, joint


# ---------------------------------------------------------------------------
# Recursive fitter
# ---------------------------------------------------------------------------


def estimate_deviation(
    curve_eval: Callable[[float], Vec],
    segments: tuple,
    t0: float,
    t1: float,
    samples: int = 9,
) -> float:
    """Estimate max deviation between *curve_eval* and *segments*.

    Samples *curve_eval* at ``samples`` interior points and measures
    the exact distance to each segment (Line) or a dense approximation
    (Arc).
    """
    max_dist = 0.0
    for i in range(1, samples):
        s = i / samples
        t = t0 + s * (t1 - t0)
        pt = curve_eval(t)
        dist = _closest_point_on_path(pt, segments)
        if dist > max_dist:
            max_dist = dist
    return max_dist


def _subdivide(
    curve_eval: Callable[[float], Vec],
    t0: float,
    t1: float,
    tol: float,
    depth: int,
    max_depth: int,
    out_arcs: List,
) -> None:
    """Recursive subdivision for bi‑arc fitting."""
    p0 = curve_eval(t0)
    p1 = curve_eval(t1)

    # Tangents via finite differences (works for any curve)
    eps_t = 1e-6 * (t1 - t0) if t1 - t0 > 1e-12 else 1e-6
    try:
        if t0 > 0:
            tan0 = (curve_eval(t0 + eps_t) - curve_eval(t0 - eps_t)).normalized()
        else:
            tan0 = (curve_eval(t0 + eps_t) - curve_eval(t0)).normalized()
    except ValueError:
        tan0 = None

    try:
        if t1 < 1:
            tan1 = (curve_eval(t1 + eps_t) - curve_eval(t1 - eps_t)).normalized()
        else:
            tan1 = (curve_eval(t1) - curve_eval(t1 - eps_t)).normalized()
    except ValueError:
        tan1 = None

    if tan0 is None or tan1 is None:
        out_arcs.append(Line(p0, p1))
        return

    # Solve bi‑arc
    arc0, arc1, _ = solve_biarc(p0, tan0, p1, tan1)
    if arc0 is None and arc1 is None:
        out_arcs.append(Line(p0, p1))
        return

    samples = max(5, 15 - (max_depth - depth))
    dev = estimate_deviation(curve_eval, (arc0, arc1), t0, t1, samples)

    if dev <= tol or depth <= 0:
        for seg in (arc0, arc1):
            if seg is not None:
                out_arcs.append(seg)
        return

    # Split and recurse
    t_mid = (t0 + t1) * 0.5
    _subdivide(curve_eval, t0, t_mid, tol, depth - 1, max_depth, out_arcs)
    _subdivide(curve_eval, t_mid, t1, tol, depth - 1, max_depth, out_arcs)


def fit_biarcs(
    curve_eval: Callable[[float], Vec],
    tolerance: float = 0.01,
    max_depth: int = 10,
) -> List:
    """Fit a parametric curve with G1‑continuous bi‑arcs.

    Args:
        curve_eval: A callable ``f(t) -> Vec`` for ``t ∈ [0, 1]``.
        tolerance:  Maximum allowed deviation.
        max_depth:  Maximum recursion depth (``10``).

    Returns:
        List of ``Arc`` and ``Line`` segments forming the approximation.
    """
    segments: List = []
    _subdivide(curve_eval, 0.0, 1.0, tolerance, max_depth, max_depth, segments)
    return segments
