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
    """Result of frame computation.

    Attributes:
        frames: ``List[Plane]`` — one per control / sample point.
                Z = tangent (bisector at corners), X/Y span the
                cross-section plane.
        scales: ``List[(float, str)]`` — per-vertex miter scale factors.
                Each entry is ``(scale, axis)`` where *axis* is ``'x'``,
                ``'y'``, or ``''`` (no miter).
    """

    frames: List["Plane"]
    scales: List[Tuple[float, str]]


def _points_from_arg(
    path_or_points,
    angle_step_deg: float,
) -> List["Vec"]:
    """Extract control points from a Path or list of Vecs."""
    from ifckit.geometry.path import Path  # deferred import

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
    """Pad a closed polyline with segment midpoints.

    Given *n* closed-loop vertices [P0, P1, ..., P_{n-1}], returns a
    **2n+1**-point sequence::

        [M0, P1, M1, P2, ..., P_{n-1}, M_{n-1}, P0, M0]

    where ``Mi = (Pi + P_{i+1}) / 2`` with wrap-around.

    The first and last entries are the same 3D point (M0), ensuring
    the seam closes naturally without endpoint-capping.
    """
    Q = []
    for i in range(len(pts)):
        mid = (pts[i] + pts[(i + 1) % len(pts)]) * 0.5
        Q.append(mid)
        Q.append(pts[(i + 1) % len(pts)])
    Q.append(Q[0])  # duplicate M0
    return Q


def _compute_vertex_miter_scales(
    pts_original: List["Vec"],
    padded_frames: List["Plane"],
) -> List[Tuple[float, str]]:
    """Compute miter scales for vertex frames in a closed padded sequence.

    Only vertex indices receive miter scales.  Midpoints get ``(1.0, "")``.

    Vertex *Pi* maps to padded index ``2i-1`` for *i >= 1*, and
    ``2n-1`` for *i == 0* (wrap-around).  The trailing duplicate M0
    (last index) inherits ``(1.0, "")``.
    """
    n_orig = len(pts_original)
    m = len(padded_frames)
    scales: List[Tuple[float, str]] = [(1.0, "")] * m

    for i in range(n_orig):
        ba = pts_original[(i - 1) % n_orig] - pts_original[i]
        bc = pts_original[(i + 1) % n_orig] - pts_original[i]
        angle = ba.angle_to(bc)
        s = 1.0 / math.sin(angle / 2) if abs(angle) > 1e-10 else 1.0
        ax = (ba**bc).normalized()

        padded_idx = 2 * n_orig - 1 if i == 0 else 2 * i - 1
        pl = padded_frames[padded_idx]
        dot_x = abs(ax @ pl.x_axis)
        dot_y = abs(ax @ pl.y_axis)
        axis_label = "x" if dot_x >= dot_y else "y"
        scales[padded_idx] = (s, axis_label)

    return scales


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

    Returns:
        ``FrameField`` with ``.frames`` and ``.scales``.
    """
    pts = _points_from_arg(path_or_points, angle_step_deg)

    if closed:
        pts_orig = pts
        pts = _pad_closed_points(pts_orig)

    n = len(pts)
    if n < 2:
        raise ValueError("Need at least 2 points")

    segs = [pts[i + 1] - pts[i] for i in range(n - 1)]
    r = ref_direction.normalized()

    # ---- Z vectors (tangents / bisectors) ------------------------------
    z_vecs = []
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

    # ---- initial X-axis ------------------------------------------------
    z0 = z_vecs[0]
    x0 = r - z0 * (r @ z0)
    if x0.length() < 1e-10:
        x0 = Vec(1, 0, 0) - z0 * (Vec(1, 0, 0) @ z0)
        if x0.length() < 1e-10:
            x0 = Vec(0, 1, 0) - z0 * (Vec(0, 1, 0) @ z0)
    x0 = x0.normalized()
    y0 = z0**x0
    frames: List["Plane"] = [Plane(pts[0], x0, y0)]

    # ---- transport X to remaining vertices ------------------------------
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
    """Build section plane frames using a fixed reference direction for X.

    Args:
        path_or_points: Spine control points or a Path.
        ref_direction:  World direction projected as the X-axis.
        angle_step_deg: Arc sampling resolution (Path overload only).
        miter_scale:    Compute per-vertex miter scale factors.
        closed:         If True, the path is treated as a closed loop.

    Returns:
        ``FrameField`` with ``.frames`` and ``.scales``.
    """
    pts = _points_from_arg(path_or_points, angle_step_deg)

    if closed:
        pts_orig = pts
        pts = _pad_closed_points(pts_orig)

    n = len(pts)
    if n < 2:
        raise ValueError("Need at least 2 points")

    segs = [pts[i + 1] - pts[i] for i in range(n - 1)]
    r = ref_direction.normalized()

    frames: List["Plane"] = []
    prev_x: "Vec | None" = None

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
    """Build section plane frames keeping profile Y near a "world-up" direction.

    Args:
        path_or_points: Spine control points or a Path.
        world_up:       Direction to keep profile Y close to.
        angle_step_deg: Arc sampling resolution (Path overload only).
        miter_scale:    Compute per-vertex miter scale factors.
        closed:         If True, the path is treated as a closed loop.

    Returns:
        ``FrameField`` with ``.frames`` and ``.scales``.
    """
    pts = _points_from_arg(path_or_points, angle_step_deg)

    if closed:
        pts_orig = pts
        pts = _pad_closed_points(pts_orig)

    n = len(pts)
    if n < 2:
        raise ValueError("Need at least 2 points")

    segs = [pts[i + 1] - pts[i] for i in range(n - 1)]
    up = world_up.normalized()

    frames: List["Plane"] = []
    prev_y: "Vec | None" = None

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
