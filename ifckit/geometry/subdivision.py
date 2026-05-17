"""
ifckit.geometry.subdivision
=============================

Catmull‑Clark subdivision surfaces — pure Python.

Implements the Catmull‑Clark subdivision scheme (Pixar 1998 formulation)
for quad‑dominant control meshes.  Each subdivision step refines the mesh
by splitting each face into quads using face‑points, edge‑points and
vertex‑points.

After subdivision the refined mesh can be exported as Wavefront OBJ,
and regular quad faces are extracted as bilinear ``Surface`` patches
suitable for IFC serialisation via ``to_ifc_bspline()``.

For full bicubic B‑spline accuracy use OpenSubdiv's ``Far::PatchTable``
to extract the exact 4×4 control‑point grids at extraordinary vertices.

References:
    E. Catmull and J. Clark. "Recursively generated B‑spline surfaces
    on arbitrary topological meshes." Computer‑Aided Design, 1978.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

from ifckit.geometry.primitives import Vec
from ifckit.geometry.surface import Surface

# ===================================================================
# Catmull‑Clark subdivision
# ===================================================================


def _catmull_clark_step(
    vertices: List[Vec],
    faces: List[List[int]],
    boundary: set,
) -> Tuple[List[Vec], List[List[int]]]:
    """One step of Catmull‑Clark subdivision.

    Process (for a closed mesh — boundary variants noted inline):

    1. **Face points** — centroid of each original face:
       ``F_i = Σ v / n``
    2. **Edge points** — average of edge endpoints and the two
       adjacent face points:
       interior: ``E = (v_a + v_b + F_0 + F_1) / 4``
       boundary: ``E = (v_a + v_b) / 2``
    3. **Vertex points** — weighted combination of old vertex,
       adjacent edge midpoints and adjacent face points:
       ``V_new = (F_avg + 2·R_avg + (n−3)·V_old) / n``
       where n = vertex valence, F_avg = average of face points,
       R_avg = average of edge midpoints of incident edges.
    4. **New faces** — for each original face with m vertices we
       create m quad sub‑faces.  Each sub‑face uses the new
       V‑point of one original vertex, the two adjacent E‑points,
       and the F‑point.
    """
    n_old = len(vertices)

    # ── Adjacency lookup tables ──────────────────────────────────
    # edge (sorted (min, max)) → face indices sharing the edge
    edge_to_faces: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    # vertex → list of incident edge keys
    vert_to_edges: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
    # vertex → list of incident face indices
    vert_to_faces: Dict[int, List[int]] = defaultdict(list)

    for fi, f in enumerate(faces):
        m = len(f)
        for j in range(m):
            a = f[j]
            b = f[(j + 1) % m]
            e = (min(a, b), max(a, b))
            edge_to_faces[e].append(fi)
            vert_to_edges.setdefault(a, []).append(e)
        for v in f:
            vert_to_faces.setdefault(v, []).append(fi)

    # ── 1. Face points (F‑points) ─────────────────────────────────
    face_pts: List[Vec] = []
    for f in faces:
        fp = Vec(0, 0, 0)
        for v in f:
            fp += vertices[v]
        face_pts.append(fp / len(f))

    # ── 2. Edge points (E‑points) ─────────────────────────────────
    edge_pts: Dict[Tuple[int, int], Vec] = {}
    for e, fi_list in edge_to_faces.items():
        a, b = e
        if e in boundary:
            # Boundary edge: midpoint of the two end‑vertices
            edge_pts[e] = (vertices[a] + vertices[b]) * 0.5
        elif len(fi_list) == 2:
            # Interior edge shared by two faces
            f0, f1 = fi_list
            edge_pts[e] = (vertices[a] + vertices[b] + face_pts[f0] + face_pts[f1]) * 0.25
        else:
            # Non‑manifold — treat as boundary
            edge_pts[e] = (vertices[a] + vertices[b]) * 0.5

    # ── Per‑vertex averages needed for V‑point formula ────────────
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

    # ── 3. Vertex points (V‑points) ───────────────────────────────
    vert_pts: Dict[int, Vec] = {}
    for v in range(n_old):
        n = len(vert_to_faces.get(v, []))  # valence
        if n == 0:
            # Isolated vertex — keep as is
            vert_pts[v] = vertices[v]
            continue

        is_boundary = any(e in boundary for e in vert_to_edges.get(v, []))
        if is_boundary and n <= 2:
            if n == 1:
                # Corner on boundary — pin
                vert_pts[v] = vertices[v]
            else:
                # Boundary (non‑corner): average of vertex and edge
                # midpoints
                vert_pts[v] = (edge_mid_avg[v] + vertices[v]) * 0.5
        else:
            # Standard Catmull‑Clark formula
            f_avg = face_pt_avg[v]
            e_avg = edge_mid_avg[v]
            vert_pts[v] = (f_avg + e_avg * 2 + vertices[v] * (n - 3)) / n

    # ── 4. Build the new mesh topology ────────────────────────────
    # We assign new indices in blocks: V‑points, then E‑points, then
    # F‑points.  This keeps the index scheme simple.
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

    # For each original face, create m quads (one per original
    # vertex).  Each quad is [V_i, E_ij, F, E_ki] in order.
    new_faces: List[List[int]] = []
    for fi, f in enumerate(faces):
        m = len(f)
        f_idx = f_map[fi]
        for j in range(m):
            v_cur = f[j]
            v_next = f[(j + 1) % m]
            # Edge keys: previous edge (j-1 → j) and next edge (j → j+1)
            e_prev = (
                min(f[j], f[(j - 1 + m) % m]),
                max(f[j], f[(j - 1 + m) % m]),
            )
            e_next = (min(v_cur, v_next), max(v_cur, v_next))
            new_faces.append([v_map[v_cur], e_map[e_next], f_idx, e_map[e_prev]])

    return new_pts, new_faces


# -------------------------------------------------------------------


def catmull_clark(
    vertices: Sequence[Vec],
    faces: Sequence[Sequence[int]],
    boundary: Sequence[Tuple[int, int]] | None = None,
    steps: int = 2,
) -> Tuple[List[Vec], List[List[int]]]:
    """Run *steps* of Catmull‑Clark subdivision on a quad‑dominant mesh.

    Boundary edges are auto‑detected (edges appearing only once in
    the face list).  After each step the boundary set is recomputed
    from the new mesh.

    Args:
        vertices:   Initial control points.
        faces:      Face index lists (closed polygons, any valence).
        boundary:   Optional explicit list of ``(i, j)`` edge pairs
                    treated as boundary edges (used in addition to
                    auto‑detection on the first step).
        steps:      Number of subdivision levels (default 2).  Each
                    step quadruples the face count for quad meshes.

    Returns:
        ``(new_vertices, new_faces)``.
    """
    pts = [Vec(*v) if not isinstance(v, Vec) else v for v in vertices]
    fcs = [list(f) for f in faces]

    for step_no in range(steps):
        # Detect boundary edges: edges appearing exactly once are
        # on the mesh boundary.
        edge_count: Dict[Tuple[int, int], int] = defaultdict(int)
        for f in fcs:
            n = len(f)
            for j in range(n):
                a, b = f[j], f[(j + 1) % n]
                edge_count[(min(a, b), max(a, b))] += 1
        boundary_set = {e for e, c in edge_count.items() if c == 1}

        # Merge in user‑specified boundaries only on the first step
        # (subsequent steps generate their own boundaries)
        if boundary is not None and step_no == 0:
            boundary_set |= set((min(a, b), max(a, b)) for a, b in boundary)

        pts, fcs = _catmull_clark_step(pts, fcs, boundary_set)

    return pts, fcs


# ===================================================================
# OBJ export
# ===================================================================


def write_obj(
    filepath: str,
    vertices: Sequence[Vec],
    faces: Sequence[Sequence[int]],
):
    """Export a mesh as a Wavefront OBJ file.

    OBJ face indices are 1‑based.  Each face is written as
    ``f i1 i2 … in`` (polygon, not limited to triangles).

    Args:
        filepath:  Output path (e.g. ``"mesh.obj"``).
        vertices:  Mesh vertices.
        faces:     Face index lists (0‑based indices).
    """
    with open(filepath, "w") as f:
        for v in vertices:
            f.write(f"v {v.x:.6f} {v.y:.6f} {v.z:.6f}\n")
        for face in faces:
            # OBJ uses 1‑based indexing
            indices = " ".join(str(idx + 1) for idx in face)
            f.write(f"f {indices}\n")


# ===================================================================
# Patch extraction (bilinear fallback)
# ===================================================================


def extract_patches(
    vertices: Sequence[Vec],
    faces: Sequence[Sequence[int]],
) -> List[Surface]:
    """Extract degree‑1 bilinear ``Surface`` patches from a quad mesh.

    Each quad face becomes a ``Surface`` with 2×2 control points,
    degree 1 in both U and V, and clamped knot vectors ``[0,0,1,1]``.
    The four face vertices (ordered counter‑clockwise) become the
    corner control points of the bilinear patch.

    .. note::
       This is a **fallback** — Catmull‑Clark limits produce exact
       bicubic (degree 3, 4×4 control points) patches at regular
       regions.  For production use, integrate OpenSubdiv's
       ``Far::PatchTable`` which provides the proper stencil weights.

    Args:
        vertices:  Subdivided mesh vertices.
        faces:     Quad face index lists.

    Returns:
        List of ``Surface`` patches (one per quad face).
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
