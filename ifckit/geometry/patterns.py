"""
ifckit.geometry.patterns
========================

Panel patterns as pure index operations on a field lattice.

Golden rule: patterns only ever return field nodes. Every ``Vec`` in the
output is a ``FieldPoint.pos`` — exact on the NURBS surface by
construction. Patterns must not create derived off-surface points (no
cell-centre averages, no 3D midpoints); any future relaxation (e.g.
planarization deviating from the surface) is a hard opt-in, never a
default. Motif patterns (hankin) derive topology in UV index space and
realize every point by NURBS evaluation — still exact on-surface.

Patterns never touch NURBS geometry except through explicit realization:
they recombine ``Field`` nodes into panel corner lists. New patterns
(pentagons, diamonds-in-diamonds) only add a function here. Pure Python
except ``hankin_cells``, which evaluates via ``pythonocc-core``.

Lattice convention: columns ``a, b, c, …`` (i), rows ``0, 1, 2, …`` (j).
A quad is ``[a0, a1, b1, b0]``; a diamond is ``[a1, b2, c1, b0]`` with
edge triangles ``[a0, a1, b1]`` along all boundary edges.
"""

# This file was generated with the assistance of an AI coding tool.

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as _dc_field
from typing import List

from ifckit.geometry.field import Field
from ifckit.geometry.primitives import Vec


@dataclass
class DiamondPattern:
    """Diamond pattern output: diamonds plus edge infill in one result.

    ``diamonds`` holds the ``[a1, b2, c1, b0]`` node diamonds (checkerboard
    nodes); ``edge`` holds the infill triangles covering the open boundary
    halves. The split is evident from the field names — no separate
    function needed. Together they partition the field exactly once.
    """

    diamonds: List[List[Vec]] = _dc_field(default_factory=list)
    edge: List[List[Vec]] = _dc_field(default_factory=list)


def quad_cells(field: Field) -> List[List[Vec]]:
    """Quad panels: the field cells resolved to corner positions.

    Args:
        field: Built field (see ``ifckit.geometry.field``).

    Returns:
        One ``[Vec × 4]`` corner list per cell.
    """
    return field.cell_points()


def _lattice_xyz(field: Field) -> dict:
    """Map lattice keys to positions."""
    return {key: field.points[idx].pos for key, idx in field.lattice.items()}


def diamond_cells(field: Field) -> DiamondPattern:
    """Diamond pattern: ``[a1, b2, c1, b0]`` on checkerboard nodes plus edge infill.

    Only nodes with even ``i + j`` carry a diamond — diamonds on every node
    would overlap (each spans two cells per axis). Every corner is a lattice
    node (exact on-surface, golden rule). ``result.edge`` holds the infill
    triangles: the uncovered half of every boundary quad, alternating with
    ``(i + j)`` parity so shared diagonals coincide (no overlaps, no gaps).

    Args:
        field: Built field.

    Returns:
        ``DiamondPattern`` with ``diamonds`` (``[Vec × 4]`` each) and
        ``edge`` (``[Vec × 3]`` each).
    """
    pos = _lattice_xyz(field)
    nrows = max(k[1] for k in pos)
    diamonds = []
    for i, j in sorted(pos):
        if i < 1 or i >= field.nu or j < 1 or j >= nrows or (i + j) % 2:
            continue
        diamonds.append([pos[(i - 1, j)], pos[(i, j + 1)], pos[(i + 1, j)], pos[(i, j - 1)]])
    quads = set()
    for i in range(field.nu):
        quads.add((i, 0))
        quads.add((i, nrows - 1))
    for j in range(nrows):
        quads.add((0, j))
        quads.add((field.nu - 1, j))
    edge = []
    for i, j in sorted(quads):
        if (i + j) % 2 == 0:
            edge.append([pos[(i, j)], pos[(i + 1, j)], pos[(i, j + 1)]])
        else:
            edge.append([pos[(i + 1, j)], pos[(i + 1, j + 1)], pos[(i, j + 1)]])
    return DiamondPattern(diamonds=diamonds, edge=edge)


def triangle_cells(field: Field, diagonal: str = "short") -> List[List[Vec]]:
    """Triangle panels: each quad split along a diagonal.

    Args:
        field:    Built field.
        diagonal: ``"short"`` (better aspect) or ``"a_c"`` / ``"b_d"`` fixed.

    Returns:
        One ``[Vec × 3]`` corner list per triangle (two per quad).
    """
    if diagonal not in ("short", "a_c", "b_d"):
        raise ValueError(f"Unknown diagonal {diagonal!r}")
    out = []
    for quad in field.cell_points():
        a, b, c, d = quad
        if diagonal == "a_c" or (diagonal == "short" and (c - a).length() <= (d - b).length()):
            out.extend([[a, b, c], [a, c, d]])
        else:
            out.extend([[a, b, d], [b, c, d]])
    return out


def wave_cells(field: Field) -> List[List[Vec]]:
    """Wave panels (PanelingTools Wave): zigzag triangle bands.

    Each quad is split along a diagonal alternating with ``(i + j)``
    parity, so diagonals form continuous zigzags across the field.
    Node-based (golden rule).

    Args:
        field: Built field.

    Returns:
        One ``[Vec × 3]`` corner list per triangle (two per quad).
    """
    pos = _lattice_xyz(field)
    nrows = max(k[1] for k in pos)
    out = []
    for j in range(nrows):
        for i in range(field.nu):
            a, b, c, d = pos[(i, j)], pos[(i + 1, j)], pos[(i + 1, j + 1)], pos[(i, j + 1)]
            if (i + j) % 2 == 0:
                out.extend([[a, b, c], [a, c, d]])
            else:
                out.extend([[a, b, d], [b, c, d]])
    return out


def anglebox_cells(field: Field) -> List[List[Vec]]:
    """Angle-box panels (PanelingTools AngleBox): quads alternating with split quads.

    Even ``(i + j)`` quads stay whole; odd quads split along ``a_c``.
    Node-based (golden rule).

    Args:
        field: Built field.

    Returns:
        Mixed ``[Vec × 4]`` quads and ``[Vec × 3]`` triangle pairs.
    """
    pos = _lattice_xyz(field)
    nrows = max(k[1] for k in pos)
    out = []
    for j in range(nrows):
        for i in range(field.nu):
            a, b, c, d = pos[(i, j)], pos[(i + 1, j)], pos[(i + 1, j + 1)], pos[(i, j + 1)]
            if (i + j) % 2 == 0:
                out.append([a, b, c, d])
            else:
                out.extend([[a, b, c], [a, c, d]])
    return out


def brick_cells(field: Field) -> List[List[Vec]]:
    """Brick panels (PanelingTools Brick): running bond, two cells wide.

    Even rows use bricks ``[(2i, j), (2i+2, j+1)]``; odd rows are offset by
    one column. Only full bricks are returned — leftover half cells at the
    boundary are dropped (real facades cut bricks; cutting is future work).

    Args:
        field: Built field.

    Returns:
        One ``[Vec × 4]`` corner list per full brick.
    """
    pos = _lattice_xyz(field)
    nrows = max(k[1] for k in pos)
    out = []
    for j in range(nrows):
        for i in range(field.nu - 1):
            a = i if j % 2 == 0 else i + 1
            if a + 2 > field.nu:
                continue
            out.append([pos[(a, j)], pos[(a + 2, j)], pos[(a + 2, j + 1)], pos[(a, j + 1)]])
    return out


# Dense (2×2 subdivision) and BoxX (diagonal cross) need points that are not
# lattice nodes (edge midpoints, cell centres). Under the golden rule those
# require UV-space derivation + NURBS realization (see hankin_cells), not
# 3D averaging — hence deferred, not silently approximated.


def truchet_cells(field: Field, seed: int = 0) -> List[List[Vec]]:
    """Truchet panels: per-quad diagonal chosen by a stable hash.

    Each quad splits into two triangles along ``a_c`` or ``b_d`` depending
    on bit ``(i * 73856093 ^ j * 19349663 ^ seed * 83492791) & 1`` —
    deterministic across runs (no ``hash()`` randomisation). Node-based.

    Args:
        field: Built field.
        seed:  Pattern variant selector.

    Returns:
        One ``[Vec × 3]`` corner list per triangle (two per quad).
    """
    pos = _lattice_xyz(field)
    nrows = max(k[1] for k in pos)
    out = []
    for j in range(nrows):
        for i in range(field.nu):
            a, b, c, d = pos[(i, j)], pos[(i + 1, j)], pos[(i + 1, j + 1)], pos[(i, j + 1)]
            if (i * 73856093 ^ j * 19349663 ^ seed * 83492791) & 1:
                out.extend([[a, b, d], [b, c, d]])
            else:
                out.extend([[a, b, c], [a, c, d]])
    return out


@dataclass
class HexPattern:
    """Hexagon pattern output: hexagons plus triangle infill in one result.

    ``hexes`` holds stretched node hexagons on the even ``(i, j)``
    sublattice; ``fill`` holds the gap triangles so both together partition
    the field exactly once. All corners are lattice nodes (golden rule).
    """

    hexes: List[List[Vec]] = _dc_field(default_factory=list)
    fill: List[List[Vec]] = _dc_field(default_factory=list)


_HEX_OFFSETS = [(-1, 0), (0, -1), (1, -1), (1, 0), (0, 1), (-1, 1)]


def _point_in_poly(px: float, py: float, poly: List[tuple]) -> bool:
    """Ray-casting point-in-polygon in lattice index space."""
    inside = False
    n = len(poly)
    for k in range(n):
        x0, y0 = poly[k]
        x1, y1 = poly[(k + 1) % n]
        if (y0 > py) != (y1 > py) and px < (x1 - x0) * (py - y0) / (y1 - y0) + x0:
            inside = not inside
    return inside


def hex_cells(field: Field) -> HexPattern:
    """Hexagon panels on the even ``(i, j)`` sublattice plus triangle infill.

    Hexagon edges run along lattice lines and quad anti-diagonals, so every
    quad half-triangle is either fully inside a hexagon or fully outside —
    never split. Outside halves become ``fill`` triangles, which makes the
    partition exact by construction (verified by area test).

    Args:
        field: Built field (needs ≥ 3 × 3 nodes for one hexagon).

    Returns:
        ``HexPattern`` with ``hexes`` (``[Vec × 6]`` each) and ``fill``
        (``[Vec × 3]`` each).
    """
    pos = _lattice_xyz(field)
    nrows = max(k[1] for k in pos)
    hex_idx = []
    for i in range(1, field.nu):
        for j in range(1, nrows):
            if i % 2 == 0 and j % 2 == 0:
                hex_idx.append([(i + dx, j + dy) for dx, dy in _HEX_OFFSETS])
    polys = [[(float(a), float(b)) for a, b in h] for h in hex_idx]

    def covered(tri: List[tuple]) -> bool:
        cx = sum(p[0] for p in tri) / 3
        cy = sum(p[1] for p in tri) / 3
        return any(_point_in_poly(cx, cy, h) for h in polys)

    fill = []
    for j in range(nrows):
        for i in range(field.nu):
            halves = [[(i, j), (i + 1, j), (i, j + 1)], [(i + 1, j), (i + 1, j + 1), (i, j + 1)]]
            for tri in halves:
                if not covered(tri):
                    fill.append([pos[p] for p in tri])
    return HexPattern(
        hexes=[[pos[p] for p in h] for h in hex_idx],
        fill=fill,
    )


def _seg_intersect_2d(p: tuple, d: tuple, q: tuple, e: tuple) -> "tuple[float, float] | None":
    """Intersection of rays ``p + t·d`` and ``q + s·e`` (2D, pure Python)."""
    denom = d[0] * e[1] - d[1] * e[0]
    if abs(denom) < 1e-12:
        return None
    w = (q[0] - p[0], q[1] - p[1])
    t = (w[0] * e[1] - w[1] * e[0]) / denom
    return (p[0] + t * d[0], p[1] + t * d[1])


def hankin_cells(field: Field, faces, theta_deg: float = 60.0) -> List[List[Vec]]:
    """Hankin star motif per quad (polygons-in-contact, Kaplan 2005).

    From each edge midpoint grow two rays at contact angle ``theta_deg`` to
    the edge, pointing inward; adjacent rays intersect to inner star
    vertices.     Output per quad: the star quad, four corner quads
    ``[corner, mid, star, mid]`` and four edge triangles ``[mid, star,
    star]`` covering the interstitial regions between star and corners
    (nine cells — a partition of the quad). Topology is
    derived in UV index space; every point is realized by NURBS evaluation
    on the owning face (transferred by exact projection across seams), so
    the golden rule holds. Angles live in native UV, which shears the motif
    on non-uniform parametrisations (documented limitation).

    Args:
        field:      Built field.
        faces:      Surfaces indexed by ``FieldPoint.face`` (needs OCC).
        theta_deg:  Contact angle to the edge, in degrees.

    Returns:
        Nine ``[Vec × 4]``/``[Vec × 3]`` corner lists per field quad
        (star, four corner quads, four edge triangles).
    """
    from ifckit.geometry.surface import occ_project_point, require_occ

    require_occ()
    import math as _math

    theta = _math.radians(theta_deg)

    def to_domain(owner_id: int, p) -> tuple:
        if p.face == owner_id:
            return p.uv
        _, transferred = occ_project_point(faces[owner_id], p.pos)
        return transferred

    out = []
    for quad in field.cells:
        corners = [field.points[k] for k in quad]
        owner = corners[2].face
        face = faces[owner]
        uv = [to_domain(owner, p) for p in corners]
        cx = sum(u[0] for u in uv) / 4
        cy = sum(u[1] for u in uv) / 4
        mids, star = [], []
        for k in range(4):
            a, b = uv[k], uv[(k + 1) % 4]
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            mids.append((mx, my))
        rays = []
        for k in range(4):
            a, b = uv[k], uv[(k + 1) % 4]
            ex, ey = b[0] - a[0], b[1] - a[1]
            el = _math.hypot(ex, ey) or 1.0
            ex, ey = ex / el, ey / el
            mx, my = mids[k]
            nx, ny = cx - mx, cy - my
            nl = _math.hypot(nx, ny) or 1.0
            nx, ny = nx / nl, ny / nl
            c, s = _math.cos(theta), _math.sin(theta)
            rays.append(((c * ex + s * nx, c * ey + s * ny), (-c * ex + s * nx, -c * ey + s * ny)))
        for k in range(4):
            # Star vertex at corner k: ray of edge k-1 towards its +end
            # meets ray of edge k towards its -end.
            prev = rays[(k - 1) % 4][0]
            cur = rays[k][1]
            hit = _seg_intersect_2d(mids[(k - 1) % 4], prev, mids[k], cur)
            star.append(hit if hit is not None else (cx, cy))
        realized = {uv[k]: corners[k].pos for k in range(4)}
        for m in mids:
            realized[m] = face.point_at(*m)
        for s in star:
            realized[s] = face.point_at(*s)
        out.append([realized[s] for s in star])
        for k in range(4):
            out.append(
                [
                    realized[uv[k]],
                    realized[mids[k]],
                    realized[star[k]],
                    realized[mids[(k - 1) % 4]],
                ]
            )
            out.append([realized[mids[k]], realized[star[k]], realized[star[(k + 1) % 4]]])
    return out
