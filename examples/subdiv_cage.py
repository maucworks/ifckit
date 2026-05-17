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

    # ── 3. Export IFC ──────────────────────────────────────────────
    patches = extract_patches(sub_verts, sub_faces)
    import ifcopenshell

    f = ifcopenshell.file(schema="IFC4")
    g = ifcopenshell.guid.new

    # Spatial structure
    si_unit = f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE")
    unit_assign = f.create_entity("IfcUnitAssignment", Units=[si_unit])

    owner = f.create_entity(
        "IfcPersonAndOrganization",
        f.create_entity("IfcPerson", GivenName="User"),
        f.create_entity("IfcOrganization", Name="ifckit"),
    )
    owner_hist = f.create_entity(
        "IfcOwnerHistory", OwningUser=owner, OwningApplication=owner,
        State="READWRITE", ChangeAction="ADDED",
    )
    proj = f.create_entity("IfcProject", g(), owner_hist, "SubdivCage",
                           UnitsInContext=unit_assign)

    ctx = f.create_entity(
        "IfcGeometricRepresentationContext",
        ContextIdentifier="Model", ContextType="Model",
        CoordinateSpaceDimension=3,
    )

    site = f.create_entity("IfcSite", g(), owner_hist, "Site")
    bldg = f.create_entity("IfcBuilding", g(), owner_hist, "Building")
    storey = f.create_entity("IfcBuildingStorey", g(), owner_hist, "Storey")
    f.create_entity("IfcRelAggregates", g(), owner_hist, RelatingObject=proj, RelatedObjects=[site])
    f.create_entity("IfcRelAggregates", g(), owner_hist, RelatingObject=site, RelatedObjects=[bldg])
    f.create_entity(
        "IfcRelAggregates", g(), owner_hist,
        RelatingObject=bldg, RelatedObjects=[storey],
    )

    # Patches as proxies
    for i, s in enumerate(patches):
        ifc_surf = s.to_ifc_bspline(f)
        rep = f.create_entity(
            "IfcShapeRepresentation", ContextOfItems=ctx,
            RepresentationIdentifier="Surface", RepresentationType="Surface3D",
            Items=[ifc_surf],
        )
        proxy = f.create_entity(
            "IfcBuildingElementProxy", g(), owner_hist, f"Patch-{i}",
            Representation=f.create_entity(
                "IfcProductDefinitionShape", Representations=[rep],
            ),
        )
        f.create_entity("IfcRelContainedInSpatialStructure",
                         g(), owner_hist,
                         RelatingStructure=storey, RelatedElements=[proxy])

    ifc_path = output_dir / "subdiv_cage.ifc"
    f.write(str(ifc_path))
    print(f"✓ IFC saved to {ifc_path}  ({len(patches)} patches)")

    # ── 4. Cube ──────────────────────────────────────────────────
    cv, cf = make_cube()
    sv, sf = catmull_clark(cv, cf, steps=2)
    write_obj(str(output_dir / "subdiv_cube.obj"), sv, sf)
    print(f"✓ Cube OBJ saved to {output_dir / 'subdiv_cube.obj'}")


if __name__ == "__main__":
    main()
