#!/usr/bin/env python3
"""
Build an IFC file containing a NURBS surface.

Demonstrates:
  - Creating an ``ifckit.geometry.Surface`` (full Python, no OCC required).
  - Serialising it to ``IfcRationalBSplineSurfaceWithKnots``.
  - Embedding the surface in a minimal IFC model (IfcBuildingElementProxy).

Usage:
    python examples/build_surface.py
"""

from pathlib import Path
from ifckit.geometry import Vec, Surface


def make_wavy_surface() -> Surface:
    """A 4×4 rational B‑spline surface (degree 3 in both directions)."""
    points = [
        [
            Vec(0, 0000, 0),
            Vec(1000, 0000, 500),
            Vec(2000, 0000, 0),
            Vec(3000, 0000, 0.0),
        ],
        [
            Vec(0, 1000, 200),
            Vec(1000, 1000, 1000),
            Vec(2000, 1000, 800),
            Vec(3000, 1000, 300),
        ],
        [
            Vec(0, 2000, 0.0),
            Vec(1000, 2000, 700),
            Vec(2000, 2000, 1200),
            Vec(3000, 2000, 400),
        ],
        [
            Vec(0, 3000, 0.0),
            Vec(1000, 3000, 300),
            Vec(2000, 3000, 500),
            Vec(3000, 3000, 0.0),
        ],
    ]
    weights = [
        [1.0, 1.0, 1.0, 1.0],
        [1.0, 0.9, 0.9, 1.0],
        [1.0, 0.9, 0.9, 1.0],
        [1.0, 1.0, 1.0, 1.0],
    ]
    return Surface(
        control_points=points,
        uknots=[0, 1],
        umults=[4, 4],
        vknots=[0, 1],
        vmults=[4, 4],
        udegree=3,
        vdegree=3,
        weights=weights,
    )


def main():
    import ifcopenshell

    guid = ifcopenshell.guid.new

    # ── 1. Build the surface ──────────────────────────────────────
    surf = make_wavy_surface()
    print(f"Surface: {surf}")

    # ── 2. Create IFC model ───────────────────────────────────────
    f = ifcopenshell.file(schema="IFC4")

    # Units
    si_unit = f.create_entity(
        "IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE"
    )
    unit_assign = f.create_entity("IfcUnitAssignment", Units=[si_unit])

    # Owner history (required by many viewers)
    owner = f.create_entity(
        "IfcPersonAndOrganization",
        f.create_entity("IfcPerson", GivenName="User"),
        f.create_entity("IfcOrganization", Name="ifckit"),
    )
    owner_hist = f.create_entity(
        "IfcOwnerHistory",
        OwningUser=owner,
        OwningApplication=owner,
        State="READWRITE",
        ChangeAction="ADDED",
    )

    # Project
    proj = f.create_entity(
        "IfcProject",
        guid(),
        owner_hist,
        "Surface Example",
        UnitsInContext=unit_assign,
    )

    # Representation context
    model_ctx = f.create_entity(
        "IfcGeometricRepresentationContext",
        ContextIdentifier="Model",
        ContextType="Model",
        CoordinateSpaceDimension=3,
    )

    # Spatial structure
    site = f.create_entity("IfcSite", guid(), owner_hist, "Site")
    building = f.create_entity("IfcBuilding", guid(), owner_hist, "Building")
    storey = f.create_entity("IfcBuildingStorey", guid(), owner_hist, "Level 0")

    f.create_entity(
        "IfcRelAggregates",
        guid(),
        owner_hist,
        RelatingObject=proj,
        RelatedObjects=[site],
    )
    f.create_entity(
        "IfcRelAggregates",
        guid(),
        owner_hist,
        RelatingObject=site,
        RelatedObjects=[building],
    )
    f.create_entity(
        "IfcRelAggregates",
        guid(),
        owner_hist,
        RelatingObject=building,
        RelatedObjects=[storey],
    )

    # ── 3. Convert Surface to IFC ─────────────────────────────────
    ifc_surf = surf.to_ifc_rational(f)

    # Representations list — start with NURBS surface
    representations = []
    nurb_rep = f.create_entity(
        "IfcShapeRepresentation",
        ContextOfItems=model_ctx,
        RepresentationIdentifier="Surface",
        RepresentationType="Surface3D",
        Items=[ifc_surf],
    )
    representations.append(nurb_rep)

    # Optional: add tessellated mesh for viewers that don't render NURBS
    try:
        from ifckit.geometry.surface import occ_tessellate_to_ifc
        from ifckit.schema import TessellationDetail

        tfs = occ_tessellate_to_ifc(surf, f, deflection=TessellationDetail.COARSE)
        tess_rep = f.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=model_ctx,
            RepresentationIdentifier="Tessellation",
            RepresentationType="Tessellation",
            Items=[tfs],
        )
        representations.append(tess_rep)
        print("  + tessellated representation (OCC)")
    except ImportError:
        print("  (no OCC — skipping tessellated representation)")

    proxy = f.create_entity(
        "IfcBuildingElementProxy",
        guid(),
        owner_hist,
        "WavySurface",
        Representation=f.create_entity(
            "IfcProductDefinitionShape",
            Name="NURBS+Tessellation",
            Representations=representations,
        ),
    )

    f.create_entity(
        "IfcRelContainedInSpatialStructure",
        guid(),
        owner_hist,
        RelatingStructure=storey,
        RelatedElements=[proxy],
    )

    # ── 4. Save ───────────────────────────────────────────────────
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    path = output_dir / "wavy_surface.ifc"
    f.write(str(path))
    print(f"✓ Saved to {path}")

    # ── 5. Summary ────────────────────────────────────────────────
    surfs = f.by_type("IfcRationalBSplineSurfaceWithKnots")
    proxies = f.by_type("IfcBuildingElementProxy")
    print(f"\n  IfcRationalBSplineSurfaceWithKnots: {len(surfs)}")
    print(f"  IfcBuildingElementProxy:             {len(proxies)}")
    print(f"  IfcProject:                          {len(f.by_type('IfcProject'))}")
    print(f"  Total entities:                      {len(f.by_type('IfcRoot'))}")


if __name__ == "__main__":
    main()
