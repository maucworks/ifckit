"""
ifckit.geometry.frames
======================

Transport frames, reference frames, and miter-scale computation for
sweeping profiles along 3D spine paths.
"""

from __future__ import annotations

import math
from typing import List, NamedTuple, Tuple

from ifckit.geometry.primitives import Plane, Vec


class FrameField(NamedTuple):
    """Result of frame computation."""

    frames: List["Plane"]
    scales: List[Tuple[float, str]]


def _points_from_arg(
    path_or_points,
    angle_step_deg: float,
) -> List["Vec"]:
    """Extract control points from a Path or list of Vecs."""
    from ifckit.geometry.path import Path

    if isinstance(path_or_points, Path):
        sampled = path_or_points.sample(angle_step_deg)
        return sampled.points
    return list(path_or_points)


def _connection_length(
    prev_x: "Vec",
    prev_y: "Vec",
    curr_x: "Vec",
    curr_y: "Vec",
    origin_shift: "Vec",
) -> float:
    """Sum of vertex-to-vertex distances between two consecutive sections."""
    total = 0.0
    for x2d, y2d in [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]:
        prev = prev_x * x2d + prev_y * y2d
        curr = curr_x * x2d + curr_y * y2d + origin_shift
        diff = curr - prev
        total += math.sqrt(diff @ diff)
    return total


def _unflip_frames(
    pts: List["Vec"],
    frames: List["Plane"],
) -> List["Plane"]:
    """Post-process frames to correct orientation discontinuities."""
    n = len(frames)
    if n < 2:
        return frames
    result = [frames[0]]
    for i in range(1, n):
        prev = result[i - 1]
        curr = frames[i]
        origin_shift = pts[i] - pts[i - 1]

        cx, cy = curr.x_axis, curr.y_axis
        candidates = [
            (cx, cy),
            (-cx, -cy),
            (-cy, cx),
            (cy, -cx),
        ]
        best_x, best_y = cx, cy
        best_d = _connection_length(prev.x_axis, prev.y_axis, cx, cy, origin_shift)
        for nx, ny in candidates[1:]:
            d = _connection_length(prev.x_axis, prev.y_axis, nx, ny, origin_shift)
            if d < best_d:
                best_d = d
                best_x, best_y = nx, ny
        result.append(Plane(curr.origin, best_x, best_y))
    return result


def _compute_miter_scales(
    pts: List["Vec"],
    frames: List["Plane"],
) -> List[Tuple[float, str]]:
    """Compute miter scale factor and scaling axis at each vertex (open path)."""
    n = len(pts)
    scales: List[Tuple[float, str]] = []
    for i in range(n):
        if i == 0 or i == n - 1:
            scales.append((1.0, ""))
            continue
        ba = pts[i - 1] - pts[i]
        bc = pts[i + 1] - pts[i]
        angle = ba.angle_to(bc)
        s = 1.0 / math.sin(angle / 2) if abs(angle) > 1e-10 else 1.0
        ax = (ba**bc).normalized()
        pl = frames[i]
        dot_x = abs(ax @ pl.x_axis)
        dot_y = abs(ax @ pl.y_axis)
        axis_label = "x" if dot_x >= dot_y else "y"
        scales.append((s, axis_label))
    return scales


# ---------------------------------------------------------------------------
# Closed-path helpers
# ---------------------------------------------------------------------------


def _pad_closed_points(pts: List["Vec"]) -> List["Vec"]:
    """Pad a closed polyline for corner-mitered sweeping.

    Returns a **4N+1**-point sequence where each vertex *Pi* is expanded
    to a triple ``(uns, mit, uns)`` so that straight segments are entirely
    unscaled and miter expansion is confined to the vertex point::

        [M0, P1_uns, P1_mit, P1_uns, M1, P2_uns, P2_mit, P2_uns,
         …, M_{N-1}, P0_uns, P0_mit, P0_uns, M0]

    where ``Mi = (Pi + P_{i+1}) / 2`` (wrap-around).
    The first and last entries are the same 3D point (M0).
    """
    n = len(pts)
    Q: List["Vec"] = []
    for i in range(n):
        Q.append((pts[i] + pts[(i + 1) % n]) * 0.5)  # Mi
        v = pts[(i + 1) % n]
        Q.append(v)  # uns
        Q.append(v)  # mit
        Q.append(v)  # uns
    Q.append(Q[0])  # duplicate M0
    return Q


def _pad_is_midpoint(idx: int) -> bool:
    """True if *idx* in the 4N+1 padded sequence is a midpoint section."""
    return idx % 4 == 0


def _pad_is_vertex_mit(idx: int) -> bool:
    """True if *idx* in the 4N+1 padded sequence is the mitered vertex."""
    return idx % 4 == 2


def _compute_vertex_miter_scales(
    pts_original: List["Vec"],
    padded_frames: List["Plane"],
) -> List[Tuple[float, str]]:
    """Compute miter scales only for ``P_mit`` sections (one per corner).

    Indices: ``4*i + 2`` for *i* = 0…N-1.
    """
    n_orig = len(pts_original)
    m = len(padded_frames)
    scales: List[Tuple[float, str]] = [(1.0, "")] * m

    for i in range(n_orig):
        ba = pts_original[i] - pts_original[(i + 1) % n_orig]
        bc = pts_original[(i + 2) % n_orig] - pts_original[(i + 1) % n_orig]
        angle = ba.angle_to(bc)
        s = 1.0 / math.sin(angle / 2) if abs(angle) > 1e-10 else 1.0
        ax = (ba**bc).normalized()

        mit_idx = 4 * i + 2
        pl = padded_frames[mit_idx]
        dot_x = abs(ax @ pl.x_axis)
        dot_y = abs(ax @ pl.y_axis)
        axis_label = "x" if dot_x >= dot_y else "y"
        scales[mit_idx] = (s, axis_label)

    return scales


def _pad_compute_tangents(
    pts: List["Vec"],
    pts_original: List["Vec"],
) -> List["Vec"]:
    """Compute Z-vectors for a padded closed sequence.

    Midpoints get pure segment directions.  Vertex triples (uns, mit, uns)
    all share the same bisector computed from the original corner geometry.
    Zero-length segments between co-located vertex points are skipped.
    """
    n_orig = len(pts_original)
    m = len(pts)

    # Pre-compute bisectors for each original vertex
    vertex_bisectors: List["Vec"] = []
    for i in range(n_orig):
        # incoming: P_{(i+1)%N} - P[i]  (toward corner from prev vertex)
        # outgoing: P_{(i+2)%N} - P_{(i+1)%N}  (away from corner to next vertex)
        inc = pts_original[(i + 1) % n_orig] - pts_original[i]
        out = pts_original[(i + 2) % n_orig] - pts_original[(i + 1) % n_orig]
        t = inc.normalized() + out.normalized()
        vertex_bisectors.append(t.normalized() if t.length() > 1e-10 else inc.normalized())

    # Compute segment directions for midpoints from adjacent vertices
    seg_dirs: List["Vec"] = []
    for i in range(n_orig):
        seg_dirs.append((pts_original[(i + 1) % n_orig] - pts_original[i]).normalized())

    # Assign Z to each padded index
    z_vecs: List["Vec"] = []
    for idx in range(m):
        # Last index (M0 duplicate) — same as the first midpoint
        if idx == m - 1:
            z_vecs.append(seg_dirs[0])
        elif _pad_is_midpoint(idx):
            block = idx // 4
            z_vecs.append(seg_dirs[block])
        else:
            # Vertex triple: bisector of the corner at P_{(block+1) % n}
            # vertex_bisectors[i] is bisector at corner P_{(i+1)%N}
            vtx_i = block % n_orig
            z_vecs.append(vertex_bisectors[vtx_i])

    return z_vecs


# ---------------------------------------------------------------------------
# Parallel-transport frames
# ---------------------------------------------------------------------------


def transport_frames(
    path_or_points,
    ref_direction: "Vec",
    angle_step_deg: float = 5.0,
    miter_scale: bool = True,
    closed: bool = False,
) -> FrameField:
    """Parallel-transport frames along a polyline path.

    Args:
        path_or_points: Spine control points or a Path.
        ref_direction:  Fixed world direction defining the initial X-axis.
        angle_step_deg: Arc sampling resolution (Path overload only).
        miter_scale:    Compute per-vertex miter scale factors.
        closed:         If True, the path is treated as a closed loop.
    """
    pts = _points_from_arg(path_or_points, angle_step_deg)

    if closed:
        pts_orig = pts
        pts = _pad_closed_points(pts_orig)

    n = len(pts)
    if n < 2:
        raise ValueError("Need at least 2 points")

    z_vecs = _pad_compute_tangents(pts, pts_orig) if closed else _compute_open_tangents(pts)
    r = ref_direction.normalized()

    z0 = z_vecs[0]
    x0 = r - z0 * (r @ z0)
    if x0.length() < 1e-10:
        x0 = Vec(1, 0, 0) - z0 * (Vec(1, 0, 0) @ z0)
        if x0.length() < 1e-10:
            x0 = Vec(0, 1, 0) - z0 * (Vec(0, 1, 0) @ z0)
    x0 = x0.normalized()
    y0 = z0**x0
    frames: List["Plane"] = [Plane(pts[0], x0, y0)]

    for i in range(1, n):
        prev_z = z_vecs[i - 1]
        curr_z = z_vecs[i]
        prev_x = frames[-1].x_axis

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

        y = curr_z**x
        frames.append(Plane(pts[i], x.normalized(), y.normalized()))

    frames = _unflip_frames(pts, frames)

    if closed:
        frames[-1] = frames[0]
        scales = _compute_vertex_miter_scales(pts_orig, frames) if miter_scale else [(1.0, "")] * n
    elif miter_scale:
        scales = _compute_miter_scales(pts, frames)
    else:
        scales = [(1.0, "")] * n

    return FrameField(frames=frames, scales=scales)


# ---------------------------------------------------------------------------
# Fixed-reference frames
# ---------------------------------------------------------------------------


def fixed_ref_frames(
    path_or_points,
    ref_direction: "Vec",
    angle_step_deg: float = 5.0,
    miter_scale: bool = True,
    closed: bool = False,
) -> FrameField:
    """Build section plane frames using a fixed reference direction for X."""
    pts = _points_from_arg(path_or_points, angle_step_deg)

    if closed:
        pts_orig = pts
        pts = _pad_closed_points(pts_orig)

    n = len(pts)
    if n < 2:
        raise ValueError("Need at least 2 points")

    z_vecs = _pad_compute_tangents(pts, pts_orig) if closed else _compute_open_tangents(pts)
    r = ref_direction.normalized()

    frames: List["Plane"] = []
    prev_x: "Vec | None" = None

    for i in range(n):
        z = z_vecs[i]

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

    frames = _unflip_frames(pts, frames)

    if closed:
        frames[-1] = frames[0]
        scales = _compute_vertex_miter_scales(pts_orig, frames) if miter_scale else [(1.0, "")] * n
    elif miter_scale:
        scales = _compute_miter_scales(pts, frames)
    else:
        scales = [(1.0, "")] * n

    return FrameField(frames=frames, scales=scales)


# ---------------------------------------------------------------------------
# Up-vector frames
# ---------------------------------------------------------------------------


def upvector_frames(
    path_or_points,
    world_up: "Vec",
    angle_step_deg: float = 5.0,
    miter_scale: bool = True,
    closed: bool = False,
) -> FrameField:
    """Build section plane frames keeping profile Y near a world-up direction."""
    pts = _points_from_arg(path_or_points, angle_step_deg)

    if closed:
        pts_orig = pts
        pts = _pad_closed_points(pts_orig)

    n = len(pts)
    if n < 2:
        raise ValueError("Need at least 2 points")

    z_vecs = _pad_compute_tangents(pts, pts_orig) if closed else _compute_open_tangents(pts)
    up = world_up.normalized()

    frames: List["Plane"] = []
    prev_y: "Vec | None" = None

    for i in range(n):
        z = z_vecs[i]

        y = up - z * (up @ z)
        if y.length() < 1e-10 and prev_y is not None:
            y = prev_y - z * (prev_y @ z)
        if y.length() < 1e-10:
            y = Vec(0, 0, 1) - z * (Vec(0, 0, 1) @ z)
            if y.length() < 1e-10:
                y = Vec(1, 0, 0) - z * (Vec(1, 0, 0) @ z)
        y = y.normalized()
        x = y**z
        prev_y = y

        frames.append(Plane(pts[i], x, y))

    frames = _unflip_frames(pts, frames)

    if closed:
        frames[-1] = frames[0]
        scales = _compute_vertex_miter_scales(pts_orig, frames) if miter_scale else [(1.0, "")] * n
    elif miter_scale:
        scales = _compute_miter_scales(pts, frames)
    else:
        scales = [(1.0, "")] * n

    return FrameField(frames=frames, scales=scales)


# ---------------------------------------------------------------------------
# Shared: open-path tangents
# ---------------------------------------------------------------------------


def _compute_open_tangents(pts: List["Vec"]) -> List["Vec"]:
    """Compute Z-vectors for an open path (standard endpoint handling)."""
    n = len(pts)
    segs = [pts[i + 1] - pts[i] for i in range(n - 1)]
    z_vecs: List["Vec"] = []
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
                t = inc
        z_vecs.append(t.normalized())
    return z_vecs
