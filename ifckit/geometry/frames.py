"""
ifckit.geometry.frames
======================

Transport frames, reference frames, and miter-scale computation for
sweeping profiles along 3D spine paths.
"""

from __future__ import annotations

import math
from typing import List, NamedTuple, Tuple

from ifckit.geometry.path import Path
from ifckit.geometry.primitives import Plane, Vec


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


def _connection_length(
    prev_x: "Vec",
    prev_y: "Vec",
    curr_x: "Vec",
    curr_y: "Vec",
    origin_shift: "Vec",
) -> float:
    """Sum of vertex-to-vertex distances between two consecutive sections.

    Uses a unit-square profile (4 vertices) to measure connection stretch.
    The actual profile dimensions scale this equally for both orientations,
    so the relative ordering is preserved.
    """
    # Unit square vertices: corners at (±0.5, ±0.5)
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
    """Post-process frames to correct orientation discontinuities between sections.

    At each frame (i ≥ 1), tests all four right-handed orientations reachable
    by 90° increments around Z (the section normal):

        (+X, +Y)   — current
        (-X, -Y)   — 180° flip
        (-Y, +X)   — 90° CCW around Z
        (+Y, -X)   — 90° CW  around Z

    Keeps the orientation with the shortest connection length to the previous
    section, so corresponding vertices stay on the same side of the spine and
    unwarranted 90° or 180° twists are corrected.
    """
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
            (cx, cy),  # 0°
            (-cx, -cy),  # 180°
            (-cy, cx),  # 90° CCW around Z
            (cy, -cx),  # 90° CW  around Z
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

    # -- rectify orientation flips by comparing vertex connections -----
    frames = _unflip_frames(pts, frames)

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

    # -- rectify orientation flips by comparing vertex connections -----
    frames = _unflip_frames(pts, frames)

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

    # -- rectify orientation flips by comparing vertex connections -----
    frames = _unflip_frames(pts, frames)

    if miter_scale:
        scales = _compute_miter_scales(pts, frames)
    else:
        scales = [(1.0, "")] * n

    return FrameField(frames=frames, scales=scales)
