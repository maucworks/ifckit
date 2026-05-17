"""
ifckit.geometry.subdivision
=============================

Catmull‑Clark subdivision surfaces — pure Python.

Produces bicubic B‑spline ``Surface`` patches from a quad‑dominant
control cage.  Also supports Wavefront OBJ export of the subdivided
limit mesh.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

from ifckit.geometry.primitives import Vec
from ifckit.geometry.surface import Surface

# ---------------------------------------------------------------------------
# Catmull‑Clark subdivision
# ---------------------------------------------------------------------------


def _catmull_clark_step(
    vertices: List[Vec],
    faces: List[List[int]],
    boundary: set,
) -> Tuple[List[Vec], List[List[int]]]:
    """One step of Catmull‑Clark subdivision (Pixar 1998 formulation)."""
    n_old = len(vertices)

    # ── Adjacency ──────────────────────────────────────────────────
    edge_to_faces: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    vert_to_edges: Dict[int, List[Tuple[int, int]]] = defaultdict(list)

    for fi, f in enumerate(faces):
        m = len(f)
        for j in range(m):
            a = f[j]
            b = f[(j + 1) % m]
            e = (min(a, b), max(a, b))
            edge_to_faces[e].append(fi)
            vert_to_edges.setdefault(a, []).append(e)

    vert_to_faces: Dict[int, List[int]] = defaultdict(list)
    for fi, f in enumerate(faces):
        for v in f:
            vert_to_faces.setdefault(v, []).append(fi)

    # ── Face points ────────────────────────────────────────────────
    face_pts: List[Vec] = []
    for f in faces:
        fp = Vec(0, 0, 0)
        for v in f:
            fp += vertices[v]
        face_pts.append(fp / len(f))

    # ── Edge points ────────────────────────────────────────────────
    edge_pts: Dict[Tuple[int, int], Vec] = {}
    for e, fi_list in edge_to_faces.items():
        a, b = e
        if e in boundary:
            edge_pts[e] = (vertices[a] + vertices[b]) * 0.5
        elif len(fi_list) == 2:
            f0, f1 = fi_list
            edge_pts[e] = (vertices[a] + vertices[b] + face_pts[f0] + face_pts[f1]) * 0.25
        else:
            edge_pts[e] = (vertices[a] + vertices[b]) * 0.5

    # ── Average edge midpoints per vertex ──────────────────────────
    edge_mid_avg: Dict[int, Vec] = {}
    for v in range(n_old):
        edges = vert_to_edges.get(v, [])
        if not edges:
            continue
        n = len(edges)
        avg = Vec(0, 0, 0)
        for e in edges:
            a, b = e
            avg += (vertices[a] + vertices[b]) * 0.5
        edge_mid_avg[v] = avg / n

    # ── Average face points per vertex ─────────────────────────────
    face_pt_avg: Dict[int, Vec] = {}
    for v in range(n_old):
        fi_list = vert_to_faces.get(v, [])
        if not fi_list:
            continue
        n = len(fi_list)
        avg = Vec(0, 0, 0)
        for fi in fi_list:
            avg += face_pts[fi]
        face_pt_avg[v] = avg / n

    # ── Vertex points ──────────────────────────────────────────────
    vert_pts: Dict[int, Vec] = {}
    for v in range(n_old):
        n = len(vert_to_faces.get(v, []))
        if n == 0:
            vert_pts[v] = vertices[v]
            continue

        is_boundary = any(e in boundary for e in vert_to_edges.get(v, []))
        if is_boundary and n <= 2:
            if n == 1:
                vert_pts[v] = vertices[v]
            else:
                vert_pts[v] = (edge_mid_avg[v] + vertices[v]) * 0.5
        else:
            f_avg = face_pt_avg[v]
            e_avg = edge_mid_avg[v]
            vert_pts[v] = (f_avg + e_avg * 2 + vertices[v] * (n - 3)) / n

    # ── New topology ───────────────────────────────────────────────
    new_pts: List[Vec] = []
    v_map: Dict[int, int] = {}
    for v in range(n_old):
        v_map[v] = len(new_pts)
        new_pts.append(vert_pts[v])

    e_map: Dict[Tuple[int, int], int] = {}
    for e in edge_to_faces:
        e_map[e] = len(new_pts)
        new_pts.append(edge_pts[e])

    f_map: Dict[int, int] = {}
    for fi in range(len(faces)):
        f_map[fi] = len(new_pts)
        new_pts.append(face_pts[fi])

    new_faces: List[List[int]] = []
    for fi, f in enumerate(faces):
        m = len(f)
        f_idx = f_map[fi]
        for j in range(m):
            v_cur = f[j]
            v_next = f[(j + 1) % m]
            e_prev = (min(f[j], f[(j - 1 + m) % m]), max(f[j], f[(j - 1 + m) % m]))
            e_next = (min(v_cur, v_next), max(v_cur, v_next))
            new_faces.append([v_map[v_cur], e_map[e_next], f_idx, e_map[e_prev]])

    return new_pts, new_faces


def catmull_clark(
    vertices: Sequence[Vec],
    faces: Sequence[Sequence[int]],
    boundary: Sequence[Tuple[int, int]] | None = None,
    steps: int = 2,
) -> Tuple[List[Vec], List[List[int]]]:
    """Run *steps* of Catmull‑Clark subdivision on a quad‑dominant mesh.

    Args:
        vertices:  Initial control points.
        faces:     Face index lists (closed polygons, any valence).
        boundary:  Optional list of (i, j) edge pairs treated as
                   boundary edges (if ``None`` auto‑detected).
        steps:     Number of subdivision levels (default 2).

    Returns:
        ``(new_vertices, new_faces)``.
    """
    pts = [Vec(*v) if not isinstance(v, Vec) else v for v in vertices]
    fcs = [list(f) for f in faces]

    for _ in range(steps):
        # Detect boundary edges
        edge_count: Dict[Tuple[int, int], int] = defaultdict(int)
        for f in fcs:
            n = len(f)
            for j in range(n):
                a, b = f[j], f[(j + 1) % n]
                edge_count[(min(a, b), max(a, b))] += 1
        boundary_set = {e for e, c in edge_count.items() if c == 1}

        if boundary is not None and _ == 0:
            boundary_set |= set((min(a, b), max(a, b)) for a, b in boundary)

        pts, fcs = _catmull_clark_step(pts, fcs, boundary_set)

    return pts, fcs


# ---------------------------------------------------------------------------
# Utility: quad mesh → OBJ
# ---------------------------------------------------------------------------


def write_obj(filepath: str, vertices: Sequence[Vec], faces: Sequence[Sequence[int]]):
    """Export a mesh as a Wavefront OBJ file."""
    with open(filepath, "w") as f:
        for v in vertices:
            f.write(f"v {v.x:.6f} {v.y:.6f} {v.z:.6f}\n")
        for face in faces:
            indices = " ".join(str(idx + 1) for idx in face)
            f.write(f"f {indices}\n")


# ---------------------------------------------------------------------------
# Bicubic patch extraction (reguliere 4×4 blocks)
# ---------------------------------------------------------------------------


def extract_patches(
    vertices: Sequence[Vec],
    faces: Sequence[Sequence[int]],
) -> List[Surface]:
    """Extract degree‑1 bilinear ``Surface`` patches from a quad mesh.

    Each quad face becomes a 1×1 degree bilinear surface with
    clamped knots.  Suitable as a fallback; for full bicubic
    accuracy use OpenSubdiv's ``Far::PatchTable``.

    Returns:
        List of ``Surface`` patches.
    """
    patches: List[Surface] = []
    for f in faces:
        if len(f) != 4:
            continue
        v00 = vertices[f[0]]
        v01 = vertices[f[1]]
        v11 = vertices[f[2]]
        v10 = vertices[f[3]]
        patches.append(
            Surface(
                control_points=[[v00, v01], [v10, v11]],
                uknots=[0, 1],
                vknots=[0, 1],
                umults=[2, 2],
                vmults=[2, 2],
                udegree=1,
                vdegree=1,
            )
        )
    return patches
