#!/usr/bin/env python3
"""
Surface → intersection → biarcs → revolved beams (I-beam).

Pipeline:
  1. NURBS surface (``ifckit.geometry.surface.Surface``)
  2. Intersect with YZ plane (OCC ``BRepAlgoAPI_Section``)
  3. Intersection curve → biarcs (``Curve.to_biarcs()``) → ``Path``
  4. Each arc → ``PendingRevolvedBeam`` with I-beam profile

Usage:
    python examples/surface_intersect_beam.py
"""

from pathlib import Path as FilePath

from ifckit import IfcModel, LengthUnit
from ifckit.elements.structural import PendingRevolvedBeam
from ifckit.geometry import Arc, Plane, Vec
from ifckit.geometry.surface import Surface, occ_intersect_plane
from ifckit.profiles import IBeamProfile


def make_wavy_surface() -> Surface:
    """4×4 rational B‑spline surface (degree 3)."""
    pts = [
        [Vec(0, 0, 0), Vec(1000, 0, 500), Vec(2000, 0, 0), Vec(3000, 0, 0)],
        [Vec(0, 1000, 200), Vec(1000, 1000, 1000), Vec(2000, 1000, 800), Vec(3000, 1000, 300)],
        [Vec(0, 2000, 0), Vec(1000, 2000, 700), Vec(2000, 2000, 1200), Vec(3000, 2000, 400)],
        [Vec(0, 3000, 0), Vec(1000, 3000, 300), Vec(2000, 3000, 500), Vec(3000, 3000, 0)],
    ]
    w = [[1.0, 1.0, 1.0, 1.0], [1.0, 0.9, 0.9, 1.0],
         [1.0, 0.9, 0.9, 1.0], [1.0, 1.0, 1.0, 1.0]]
    return Surface(pts, [0, 1], [0, 1], [4, 4], [4, 4], 3, 3, weights=w)


def main():
    import ifcopenshell

    guid = ifcopenshell.guid.new

    # ── 1. Build the surface ──────────────────────────────────────
    surf = make_wavy_surface()
    print(f"Surface: {surf}")

    # ── 2. Intersect with YZ plane at x = 1500 ────────────────────
    yz_plane = Plane.from_origin_and_normal(Vec(1500, 0, 0), Vec(1, 0, 0))
    curves = occ_intersect_plane(surf, yz_plane)
    print(f"Intersection curves: {len(curves)}")
    if not curves:
        return

    # ── 3. Intersection curve → biarcs ─────────────────────────────
    curve = curves[0]
    path = curve.to_biarcs(tol=500, max_iteration=3)
    arcs = [s for s in path.segments if isinstance(s, Arc)]
    print(f"Biarcs: {len(arcs)} arcs")

    if not arcs:
        print("✗ No arcs found")
        return

    # ── 4. I-beam profile points ──────────────────────────────────
    ibeam = IBeamProfile(height=200, width=120,
                         web_thickness=8, flange_thickness=12)
    profile = [s.start for s in ibeam.segments]

    # ── 5. IFC model ──────────────────────────────────────────────
    from ifckit.builders._geom import get_body_context
    from ifckit.builders.revolved_beam import RevolvedBeamBuilder

    model = IfcModel(unit=LengthUnit.MILLIMETRE)
    f = model._file
    proj = model._project

    o = f.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
    z = f.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
    x = f.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
    plc = f.create_entity("IfcAxis2Placement3D", Location=o, Axis=z, RefDirection=x)
    place = f.create_entity("IfcLocalPlacement", PlacementRelTo=None, RelativePlacement=plc)
    storey = f.create_entity(
        "IfcBuildingStorey", GlobalId=guid(), Name="Storey",
        ObjectPlacement=place,
    )
    f.create_entity(
        "IfcRelAggregates", GlobalId=guid(),
        RelatingObject=proj, RelatedObjects=[storey],
    )

    context = get_body_context(f)
    builder = RevolvedBeamBuilder()

    # ── 6. Build one beam per arc ──────────────────────────────────
    beams = []
    for i, arc in enumerate(arcs):
        pending = PendingRevolvedBeam(arc, profile, name=f"Beam-{i}")
        beam = builder.build(f, pending, storey, context)
        beams.append(beam)
        print(f"  Beam-{i}: arc radius={arc.radius:.0f}, angle={arc.angle:.3f} rad")

    # ── 7. Save ───────────────────────────────────────────────────
    output_dir = FilePath(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    out = output_dir / "surface_intersect_beam.ifc"
    f.write(str(out))
    print(f"✓ Saved to {out}  ({len(beams)} beams)")


if __name__ == "__main__":
    main()
