"""
ifckit.geometry.field
=====================

Point fields on trimmed NURBS surfaces for architectural panelization.

A field is a structured quad lattice with exact on-surface positions,
native UV parameters and exact normals per point — the contract between
point-field generation (domain 1) and panel looping (domain 2, see
``patterns``): patterns only read the lattice, never NURBS geometry.
"""

# This file was generated with the assistance of an AI coding tool.

from __future__ import annotations

import math
from dataclasses import dataclass
from dataclasses import field as _dc_field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ifckit.geometry.primitives import Vec, _new_id
from ifckit.geometry.surface import (
    Surface,
    occ_normal_at,
    occ_project_point,
    occ_trim_loops,
    require_occ,
)

Uv = Tuple[float, float]


@dataclass
class FieldPoint:
    """One lattice node: exact on-surface position, native UV, exact normal.

    Attributes:
        pos:    Position, guaranteed on the NURBS surface (projection).
        uv:     Native ``(u, v)`` parameters on the owning face.
        normal: Exact normal (D1); orientation follows the parametrisation.
        face:   Owning face index within the field.
    """

    pos: Vec
    uv: Uv
    normal: Vec
    face: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "pos": self.pos.to_dict(),
            "uv": [self.uv[0], self.uv[1]],
            "normal": self.normal.to_dict(),
            "face": self.face,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FieldPoint":
        """Deserialize from a dict."""
        return cls(
            pos=Vec.from_dict(d["pos"]),
            uv=(d["uv"][0], d["uv"][1]),
            normal=Vec.from_dict(d["normal"]),
            face=d.get("face", 0),
        )


@dataclass
class Field:
    """Structured quad point field over one or more trimmed faces.

    Attributes:
        points:  All nodes (row-major per face, seam rows shared).
        lattice: ``(i, j)`` lattice key → index into ``points``.
        cells:   Quad cells as point-index quadruples.
        nu:      Divisions across (shared by all faces).
        nv:      Divisions along, one entry per face.
        id:      Stable identity.
        meta:    Free metadata.
    """

    points: List[FieldPoint] = _dc_field(default_factory=list)
    lattice: Dict[Tuple[int, int], int] = _dc_field(default_factory=dict)
    cells: List[Tuple[int, int, int, int]] = _dc_field(default_factory=list)
    nu: int = 0
    nv: List[int] = _dc_field(default_factory=list)
    id: Optional[str] = None
    meta: Dict[str, Any] = _dc_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = _new_id()

    def cell_points(self) -> List[List[Vec]]:
        """Resolve cells to ``Vec`` corner lists."""
        return [[self.points[k].pos for k in cell] for cell in self.cells]

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (incl. identity)."""
        return {
            "type": "field",
            "id": self.id,
            "meta": dict(self.meta),
            "points": [p.to_dict() for p in self.points],
            "lattice": [[[k[0], k[1]], v] for k, v in self.lattice.items()],
            "cells": [list(c) for c in self.cells],
            "nu": self.nu,
            "nv": list(self.nv),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Field":
        """Deserialize from a dict."""
        return cls(
            points=[FieldPoint.from_dict(p) for p in d["points"]],
            lattice={(k[0], k[1]): v for k, v in d["lattice"]},
            cells=[tuple(c) for c in d["cells"]],  # type: ignore[misc]
            nu=d["nu"],
            nv=list(d["nv"]),
            id=d.get("id"),
            meta=dict(d.get("meta", {})),
        )


# ---------------------------------------------------------------------------
# Pure helpers (no OCC): division, orientation, lengths
# ---------------------------------------------------------------------------


def _polyline_length(xyz: Sequence[Tuple[float, float, float]]) -> float:
    """Chord-length sum of an xyz polyline."""
    total = 0.0
    for a, b in zip(xyz, xyz[1:]):
        total += math.dist(a, b)
    return total


def divide_trim_edge(
    edge_uv: Sequence[Uv], edge_xyz: Sequence[Tuple[float, float, float]], n: int
) -> List[Uv]:
    """Divide a trim edge into *n* equal 3D-chord parts → *n+1* UV points.

    Pure Python; equidistant in world space, parametrised in native UV.

    Args:
        edge_uv:  Dense UV polyline along the edge.
        edge_xyz: Matching world positions.
        n:        Number of parts (≥ 1).

    Returns:
        List of *n+1* ``(u, v)`` tuples, endpoints exact.
    """
    if n < 1:
        raise ValueError(f"Division count must be ≥ 1, got {n}")
    if len(edge_uv) != len(edge_xyz) or len(edge_uv) < 2:
        raise ValueError("edge_uv and edge_xyz must be equal non-trivial polylines")
    seg = [math.dist(edge_xyz[k], edge_xyz[k + 1]) for k in range(len(edge_xyz) - 1)]
    total = sum(seg)
    if total <= 0.0:
        raise ValueError("Trim edge has zero length")
    out = [edge_uv[0]]
    acc, k = 0.0, 0
    for i in range(1, n):
        target = total * i / n
        while k < len(seg) - 1 and acc + seg[k] < target:
            acc += seg[k]
            k += 1
        f = (target - acc) / seg[k] if seg[k] > 0.0 else 0.0
        a, b = edge_uv[k], edge_uv[k + 1]
        out.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])))
    out.append(edge_uv[-1])
    return out


def orient_division(
    mov_uv: Sequence[Uv],
    mov_xyz: Sequence[Tuple[float, float, float]],
    ref0_xyz: Tuple[float, float, float],
    ref1_xyz: Tuple[float, float, float],
) -> List[Uv]:
    """Order a division so index 0 sits at the south/west corner side.

    Trims run head-to-tail around the face, so opposite edges inherently run
    opposite directions; parametrisation direction is unreliable on top of
    that. Match by 3D endpoints: keep order when ends are closer straight
    than crossed, else reverse. Pure Python.

    Args:
        mov_uv:  Division to orient.
        mov_xyz: Matching world positions.
        ref0_xyz: World position that index 0 must sit at.
        ref1_xyz: World position that index -1 must sit at.

    Returns:
        Oriented list of ``(u, v)`` tuples.
    """
    straight = math.dist(mov_xyz[0], ref0_xyz) + math.dist(mov_xyz[-1], ref1_xyz)
    flipped = math.dist(mov_xyz[0], ref1_xyz) + math.dist(mov_xyz[-1], ref0_xyz)
    if straight <= flipped:
        return list(mov_uv)
    return list(reversed(mov_uv))


# ---------------------------------------------------------------------------
# OCC-backed builders
# ---------------------------------------------------------------------------


def _sampled_loops(surf: Surface) -> List[Dict[str, list]]:
    """Trim loops as paired dense ``{"uv", "xyz"}`` polylines."""
    require_occ()
    out = []
    for loop in occ_trim_loops(surf, samples=200):
        xyz = []
        for u, v in loop:
            q = surf.point_at(u, v)
            xyz.append((q.x, q.y, q.z))
        out.append({"uv": list(loop), "xyz": xyz})
    return out


def _classify(loops: List[Dict[str, list]]) -> Dict[str, Dict[str, list]]:
    """Identify trim loops by midpoint extremes → south/north/west/east.

    Args:
        loops: Sampled loops from ``_sampled_loops``.

    Returns:
        Dict with exactly the keys south/north/west/east. Raises
        ``ValueError`` when fewer than 4 distinct loops exist (3/5-edge
        patches are future work, not silently misclassified).
    """
    if len(loops) < 4:
        raise ValueError(f"Expected ≥ 4 trim loops, got {len(loops)}")

    def mid(loop: Dict[str, list], key: int) -> float:
        col = [p[key] for p in loop["xyz"]]
        return sum(col) / len(col)

    def pick(key: int, which: str) -> int:
        order = sorted(((mid(loop, key), i) for i, loop in enumerate(loops)))
        return order[0][1] if which == "min" else order[-1][1]

    idx = {
        "south": pick(1, "min"),
        "north": pick(1, "max"),
        "west": pick(0, "min"),
        "east": pick(0, "max"),
    }
    if len(set(idx.values())) != 4:
        raise ValueError("Trim loops are degenerate (edges coincide)")
    return {name: loops[i] for name, i in idx.items()}


def _counts(edge: Dict[str, list], spacing: float) -> int:
    """Division count for an edge length and target spacing."""
    return max(1, round(_polyline_length(edge["xyz"]) / spacing))


def _mean_uv(*uvs: Uv) -> Uv:
    """Mean of UV points (corner unification)."""
    return (sum(u[0] for u in uvs) / len(uvs), sum(u[1] for u in uvs) / len(uvs))


def _eval_xyz(surf: Surface, uv: Uv) -> Tuple[float, float, float]:
    """Evaluate a UV point to an xyz tuple."""
    q = surf.point_at(*uv)
    return (q.x, q.y, q.z)


def _project_uv(face: Surface, xyz: Tuple[float, float, float]) -> Uv:
    """Native UV of a world point via exact projection (seam transfer)."""
    _, uv = occ_project_point(face, Vec(*xyz))
    return uv


def _intersect_uv(seg_a: Tuple[Uv, Uv], seg_b: Tuple[Uv, Uv], guess: Uv) -> Uv:
    """Exact 2D intersection of two UV segments (OCC ``Geom2dAPI``).

    Args:
        seg_a:  First segment as ``((u0, v0), (u1, v1))``.
        seg_b:  Second segment.
        guess:  Expected neighbourhood; nearest hit wins when several exist.

    Returns:
        ``(u, v)`` of the intersection. Raises ``RuntimeError`` on a miss.
    """
    require_occ()
    from OCC.Core.GCE2d import GCE2d_MakeSegment
    from OCC.Core.Geom2dAPI import Geom2dAPI_InterCurveCurve
    from OCC.Core.gp import gp_Pnt2d

    c_a = GCE2d_MakeSegment(gp_Pnt2d(*seg_a[0]), gp_Pnt2d(*seg_a[1])).Value()
    c_b = GCE2d_MakeSegment(gp_Pnt2d(*seg_b[0]), gp_Pnt2d(*seg_b[1])).Value()
    inter = Geom2dAPI_InterCurveCurve(c_a, c_b)
    best: Optional[Uv] = None
    best_d = 0.0
    for k in range(1, inter.NbPoints() + 1):
        p = inter.Point(k)
        d = (p.X() - guess[0]) ** 2 + (p.Y() - guess[1]) ** 2
        if best is None or d < best_d:
            best, best_d = (p.X(), p.Y()), d
    if best is None:
        raise RuntimeError("UV segments do not intersect")
    return best


def trim_grid(face: Surface, spacing: float) -> Field:
    """Transfinite quad field on one trimmed face (south → north).

    Divides the south and north trim edges equidistantly, connects pairs
    with on-surface lines and divides each connector equidistantly.
    All divisions are forced to the south/west-corner convention first.

    Args:
        face:    Trimmed surface (needs ``pythonocc-core``).
        spacing: Target panel measure in model units.

    Returns:
        Field with ``(nu+1) × (nv+1)`` nodes and ``nu × nv`` cells.
    """
    require_occ()
    edges = _classify(_sampled_loops(face))
    nu = _counts(edges["north"], spacing)
    nv = _counts(edges["west"], spacing)
    south = divide_trim_edge(edges["south"]["uv"], edges["south"]["xyz"], nu)
    north = divide_trim_edge(edges["north"]["uv"], edges["north"]["xyz"], nu)
    north = orient_division(
        north,
        [_eval_xyz(face, uv) for uv in north],
        _eval_xyz(face, south[0]),
        _eval_xyz(face, south[-1]),
    )
    field = Field(nu=nu, nv=[nv])
    for k in range(nu + 1):
        col = _connector_divide(face, south[k], north[k], nv)
        for j, uv in enumerate(col):
            field.lattice[(k, j)] = len(field.points)
            field.points.append(_node_at(face, uv, face_id=0))
    for i in range(nu):
        for j in range(nv):
            a = field.lattice[(i, j)]
            field.cells.append(
                (
                    a,
                    field.lattice[(i + 1, j)],
                    field.lattice[(i + 1, j + 1)],
                    field.lattice[(i, j + 1)],
                )
            )
    return field


def _connector_divide(face: Surface, uv_a: Uv, uv_b: Uv, n: int, samples: int = 120) -> List[Uv]:
    """On-surface line ``uv_a → uv_b`` divided into *n* equal 3D parts."""
    uv = [
        (uv_a[0] + (uv_b[0] - uv_a[0]) * k / samples, uv_a[1] + (uv_b[1] - uv_a[1]) * k / samples)
        for k in range(samples + 1)
    ]
    xyz = [_eval_xyz(face, p) for p in uv]
    return divide_trim_edge(uv, xyz, n)


def _node_at(face: Surface, uv: Uv, face_id: int) -> FieldPoint:
    """FieldPoint with exact position and normal at native ``uv``."""
    q = face.point_at(*uv)
    return FieldPoint(pos=q, uv=uv, normal=occ_normal_at(face, *uv), face=face_id)


def crossing_grid(
    faces: Sequence[Surface],
    spacing: float,
    shared: Sequence[Tuple[int, int]] = (),
) -> Field:
    """Crossing field: i-family (south→north) + j-family (west→east).

    Nodes on the boundary come from equidistant trim divisions; interior
    nodes are exact 2D intersections of the connector p-curves
    (``Geom2dAPI``), evaluated to exact on-surface positions with exact
    normals. Generalises to 3/5-edge patches via extra connector families.

    Args:
        faces:   Trimmed surfaces, ordered south → north.
        spacing: Target panel measure in model units.
        shared:  Explicit ``(face_a, face_b)`` pairs whose seam is one
            geometric row: north edge of *a* coincides with south edge
            of *b*. Stations are divided once on *a* and transferred to
            *b*'s native UV by exact projection — no auto-detection magic.

    Returns:
        Field with one shared lattice row per seam.
    """
    require_occ()
    if not faces:
        raise ValueError("crossing_grid needs at least one face")
    seals = {a: b for a, b in shared}
    for a, b in seals.items():
        if not (0 <= a < len(faces) and 0 <= b < len(faces)):
            raise ValueError(f"Shared pair {(a, b)} out of range")

    divs = [_divided_face(f, spacing) for f in faces]
    nu = max(d["nu"] for d in divs)
    # Unify nu across faces (shared rows need equal counts): re-divide.
    divs = [
        _divide_with_nu(f, edges, nu, spacing)
        for f, edges in ((f, d["edges"]) for f, d in zip(faces, divs))
    ]

    field = Field(nu=nu, nv=[])
    row_off = 0
    for fi, (face, d) in enumerate(zip(faces, divs)):
        south, north = d["south"], d["north"]
        west, east = d["west"], d["east"]
        nv = d["nv"]
        if fi in seals.values():
            prev = next(a for a, b in seals.items() if b == fi)
            # Same geometric row, own native UV: transfer seam stations
            # by exact projection (parametrisations differ per face).
            south = [_project_uv(face, _eval_xyz(faces[prev], uv)) for uv in divs[prev]["seam_row"]]
            # Pin west/east bottom exactly on the shared seam corners.
            west[0], east[0] = south[0], south[-1]
        nodes = _crossing_nodes(face, south, north, west, east, nu, nv)
        for (k, r), uv in nodes.items():
            key = (k, row_off + r)
            if key in field.lattice:
                continue  # shared seam row already owned by the previous face
            field.lattice[key] = len(field.points)
            field.points.append(_node_at(face, uv, face_id=fi))
        # Cells within this face (local rows 0..nv, mapped to lattice rows).
        for i in range(nu):
            for j in range(nv):
                quad = (
                    (i, row_off + j),
                    (i + 1, row_off + j),
                    (i + 1, row_off + j + 1),
                    (i, row_off + j + 1),
                )
                field.cells.append(tuple(field.lattice[q] for q in quad))
        divs[fi]["seam_row"] = north
        field.nv.append(nv)
        row_off += nv
    return field


def _divided_face(face: Surface, spacing: float) -> Dict[str, Any]:
    """Classify + count only (first pass for nu unification)."""
    edges = _classify(_sampled_loops(face))
    return {"edges": edges, "nu": _counts(edges["north"], spacing)}


def _divide_with_nu(
    face: Surface, edges: Dict[str, Dict[str, list]], nu: int, spacing: float
) -> Dict[str, Any]:
    """Divide all four edges with fixed *nu*; orient to the corner convention."""
    south = divide_trim_edge(edges["south"]["uv"], edges["south"]["xyz"], nu)
    north = divide_trim_edge(edges["north"]["uv"], edges["north"]["xyz"], nu)
    nv = _counts(edges["west"], spacing)
    west = divide_trim_edge(edges["west"]["uv"], edges["west"]["xyz"], nv)
    east = divide_trim_edge(edges["east"]["uv"], edges["east"]["xyz"], nv)
    north = orient_division(
        north,
        [_eval_xyz(face, uv) for uv in north],
        _eval_xyz(face, south[0]),
        _eval_xyz(face, south[-1]),
    )
    west = orient_division(
        west,
        [_eval_xyz(face, uv) for uv in west],
        _eval_xyz(face, south[0]),
        _eval_xyz(face, north[0]),
    )
    east = orient_division(
        east,
        [_eval_xyz(face, uv) for uv in east],
        _eval_xyz(face, west[0]),
        _eval_xyz(face, west[-1]),
    )
    south[0], west[0] = _unify(south[0], west[0])
    south[-1], east[0] = _unify(south[-1], east[0])
    north[0], west[-1] = _unify(north[0], west[-1])
    north[-1], east[-1] = _unify(north[-1], east[-1])
    return {"south": south, "north": north, "west": west, "east": east, "nv": nv, "edges": edges}


def _unify(a: Uv, b: Uv) -> Tuple[Uv, Uv]:
    """Unify two approximations of one corner to their mean."""
    m = _mean_uv(a, b)
    return m, m


def _mean_uv(*uvs: Uv) -> Uv:
    """Mean of UV points."""
    return (sum(u[0] for u in uvs) / len(uvs), sum(u[1] for u in uvs) / len(uvs))


def _crossing_nodes(
    face: Surface,
    south: List[Uv],
    north: List[Uv],
    west: List[Uv],
    east: List[Uv],
    nu: int,
    nv: int,
) -> Dict[Tuple[int, int], Uv]:
    """Boundary divisions + interior 2D intersections → ``(k, l) → uv``."""
    isegs = [((south[k]), (north[k])) for k in range(nu + 1)]
    jsegs = [((west[r]), (east[r])) for r in range(nv + 1)]
    nodes: Dict[Tuple[int, int], Uv] = {}
    for k in range(nu + 1):
        for r in range(nv + 1):
            if r == 0:
                nodes[(k, r)] = south[k]
            elif r == nv:
                nodes[(k, r)] = north[k]
            elif k == 0:
                nodes[(k, r)] = west[r]
            elif k == nu:
                nodes[(k, r)] = east[r]
            else:
                guess = ((south[k][0] + north[k][0]) / 2, (west[r][1] + east[r][1]) / 2)
                nodes[(k, r)] = _intersect_uv(isegs[k], jsegs[r], guess)
    return nodes
