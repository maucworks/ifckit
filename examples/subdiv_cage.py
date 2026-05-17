#!/usr/bin/env python3
"""
Catmull‑Clark subdivision example — exports limit mesh as OBJ.

Usage:
    python examples/subdiv_cage.py
"""

from pathlib import Path as FilePath

from ifckit.geometry import Vec
from ifckit.geometry.subdivision import catmull_clark, extract_patches, write_obj


def make_cube() -> tuple[list[Vec], list[list[int]]]:
    """Unit cube control cage."""
    verts = [
        Vec(-1, -1, -1), Vec(1, -1, -1), Vec(1, 1, -1), Vec(-1, 1, -1),
        Vec(-1, -1, 1),  Vec(1, -1, 1),  Vec(1, 1, 1),  Vec(-1, 1, 1),
    ]
    faces = [
        [0, 1, 2, 3],  # -Z
        [7, 6, 5, 4],  # +Z
        [0, 4, 5, 1],  # -Y
        [3, 2, 6, 7],  # +Y
        [0, 3, 7, 4],  # -X
        [1, 5, 6, 2],  # +X
    ]
    return verts, faces


def make_torus(radius: float = 3.0, tube: float = 1.0,
               radial: int = 8, axial: int = 6) -> tuple[list[Vec], list[list[int]]]:
    """Quad‑dominant torus control cage."""
    import math

    verts: list[Vec] = []
    faces: list[list[int]] = []

    # Create vertices
    for i in range(axial):
        theta = i * 2 * math.pi / axial
        for j in range(radial):
            phi = j * 2 * math.pi / radial
            x = (radius + tube * math.cos(phi)) * math.cos(theta)
            y = (radius + tube * math.cos(phi)) * math.sin(theta)
            z = tube * math.sin(phi)
            verts.append(Vec(x, y, z))

    # Create faces
    for i in range(axial):
        for j in range(radial):
            a = i * radial + j
            b = i * radial + (j + 1) % radial
            c = ((i + 1) % axial) * radial + (j + 1) % radial
            d = ((i + 1) % axial) * radial + j
            faces.append([a, b, c, d])

    return verts, faces


def main():
    # ── 1. Subdivide torus ────────────────────────────────────────
    verts, faces = make_torus()
    print(f"Cage: {len(verts)} verts, {len(faces)} faces")

    sub_verts, sub_faces = catmull_clark(verts, faces, steps=2)
    print(f"Subdiv (2 steps): {len(sub_verts)} verts, {len(sub_faces)} faces")

    # ── 2. Export OBJ ─────────────────────────────────────────────
    output_dir = FilePath(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    obj_path = output_dir / "subdiv_torus.obj"
    write_obj(str(obj_path), sub_verts, sub_faces)
    print(f"✓ OBJ saved to {obj_path}")

    # ── 3. Extract IFC patches ────────────────────────────────────
    patches = extract_patches(sub_verts, sub_faces)
    import ifcopenshell

    f = ifcopenshell.file(schema="IFC4")
    for i, s in enumerate(patches[:4]):  # first 4 patches
        e = s.to_ifc_bspline(f)
        print(f"  patch {i}: {e.is_a()}, Udeg={e.UDegree} Vdeg={e.VDegree}")
    ifc_path = output_dir / "subdiv_cage.ifc"
    f.write(str(ifc_path))
    print(f"✓ IFC saved to {ifc_path}")

    # ── 4. Cube ──────────────────────────────────────────────────
    cv, cf = make_cube()
    sv, sf = catmull_clark(cv, cf, steps=2)
    write_obj(str(output_dir / "subdiv_cube.obj"), sv, sf)
    print(f"✓ Cube OBJ saved to {output_dir / 'subdiv_cube.obj'}")


if __name__ == "__main__":
    main()
