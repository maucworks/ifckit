import re
from typing import List, Optional, Tuple, Union

import numpy as np

from ifckit.geometry import Arc, Line

_SVG_CMD_RE = re.compile(r"([MmLlHhVvAaZzCcSsQqTt])")
_SVG_NUM_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def parse_matrix3(matrix3_attr: str) -> Optional[Tuple[float, float, float]]:
    if not matrix3_attr:
        return None
    nums = [float(n) for n in _SVG_NUM_RE.findall(matrix3_attr)]
    if len(nums) >= 9:
        sc = nums[0]
        tx = nums[2]
        ty = nums[5]
        if sc == 0.0:
            return None
        return sc, tx, ty
    return None


def parse_plane_attr(plane_attr: str) -> Optional[List[float]]:
    if not plane_attr:
        return None
    nums = [float(n) for n in _SVG_NUM_RE.findall(plane_attr)]
    if len(nums) >= 16:
        return nums[:16]
    return None


def plane_mat_to_numpy(plane: List[float]) -> np.ndarray:
    m = np.array(plane).reshape(4, 4)
    m[3] = [0.0, 0.0, 0.0, 1.0]
    return m.T


def world_to_svg(
    world_pt: Tuple[float, float, float],
    plane_mat_inv: np.ndarray,
    sc: float,
    tx: float,
    ty: float,
) -> Tuple[float, float]:
    w = np.array([*world_pt, 1.0])
    local = plane_mat_inv @ w
    lx = local[0]
    ly = local[1]
    svg_x = lx * sc + tx
    svg_y = -ly * sc + ty
    return svg_x, svg_y


def curves_to_svg_d(
    curves: List[Union[Line, Arc]],
    plane_mat: Optional[List[float]],
    svg_transform: Tuple[float, float, float],
) -> str:
    sc, tx, ty = svg_transform
    if plane_mat:
        M = plane_mat_to_numpy(plane_mat)
        Minv = np.linalg.inv(M)
    else:
        Minv = None

    parts = []
    for crv in curves:
        if isinstance(crv, Arc):
            pts = crv.sample(90.0 / 7)
        elif isinstance(crv, Line):
            pts = [crv.start, crv.end]
        else:
            continue

        for i, pt in enumerate(pts):
            if Minv is not None:
                sx, sy = world_to_svg((pt.x, pt.y, pt.z), Minv, sc, tx, ty)
            else:
                sx = pt.x * sc + tx
                sy = -pt.y * sc + ty
            if i == 0:
                parts.append(f"M {sx:.3f},{sy:.3f}")
            else:
                parts.append(f"L {sx:.3f},{sy:.3f}")

    return " ".join(parts)


def parse_path_d(d: str) -> list[tuple]:
    tokens = _SVG_CMD_RE.split(d.strip())
    cmd_blocks: list[tuple[str, list[float]]] = []
    i = 1
    while i < len(tokens):
        cmd = tokens[i]
        nums_str = tokens[i + 1] if i + 1 < len(tokens) else ""
        nums = [float(n) for n in _SVG_NUM_RE.findall(nums_str)]
        cmd_blocks.append((cmd, nums))
        i += 2

    segments: list[tuple] = []
    cx, cy = 0.0, 0.0
    sx, sy = 0.0, 0.0

    for cmd, nums in cmd_blocks:
        if cmd in ("M", "m"):
            pairs = list(zip(nums[0::2], nums[1::2]))
            for k, (dx, dy) in enumerate(pairs):
                if cmd == "m":
                    cx += dx
                    cy += dy
                else:
                    cx, cy = dx, dy
                if k == 0:
                    sx, sy = cx, cy
                    segments.append(("M", cx, cy))
                else:
                    segments.append(("L", cx, cy))

        elif cmd in ("L", "l"):
            pairs = list(zip(nums[0::2], nums[1::2]))
            for dx, dy in pairs:
                if cmd == "l":
                    cx += dx
                    cy += dy
                else:
                    cx, cy = dx, dy
                segments.append(("L", cx, cy))

        elif cmd in ("H", "h"):
            for v in nums:
                cx = cx + v if cmd == "h" else v
                segments.append(("L", cx, cy))

        elif cmd in ("V", "v"):
            for v in nums:
                cy = cy + v if cmd == "v" else v
                segments.append(("L", cx, cy))

        elif cmd in ("A", "a"):
            n = 7
            for j in range(0, len(nums), n):
                chunk = nums[j : j + n]
                if len(chunk) < n:
                    break
                rx, ry, x_rot, large_arc, sweep, ex, ey = chunk
                if cmd == "a":
                    ex += cx
                    ey += cy
                segments.append(("A", rx, ry, x_rot, int(large_arc), int(sweep), ex, ey))
                cx, cy = ex, ey

        elif cmd in ("Z", "z"):
            segments.append(("Z",))
            cx, cy = sx, sy

        elif cmd in ("C", "c"):
            for j in range(0, len(nums), 6):
                chunk = nums[j : j + 6]
                if len(chunk) < 6:
                    break
                ex, ey = chunk[4], chunk[5]
                if cmd == "c":
                    ex += cx
                    ey += cy
                cx, cy = ex, ey
                segments.append(("L", cx, cy))

        elif cmd in ("S", "s"):
            for j in range(0, len(nums), 4):
                chunk = nums[j : j + 4]
                if len(chunk) < 4:
                    break
                ex, ey = chunk[2], chunk[3]
                if cmd == "s":
                    ex += cx
                    ey += cy
                cx, cy = ex, ey
                segments.append(("L", cx, cy))

        elif cmd in ("Q", "q"):
            for j in range(0, len(nums), 4):
                chunk = nums[j : j + 4]
                if len(chunk) < 4:
                    break
                ex, ey = chunk[2], chunk[3]
                if cmd == "q":
                    ex += cx
                    ey += cy
                cx, cy = ex, ey
                segments.append(("L", cx, cy))

        elif cmd in ("T", "t"):
            pairs = list(zip(nums[0::2], nums[1::2]))
            for dx, dy in pairs:
                if cmd == "t":
                    cx += dx
                    cy += dy
                else:
                    cx, cy = dx, dy
                segments.append(("L", cx, cy))

    return segments
