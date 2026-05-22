#!/usr/bin/env python3
"""
example_footprint.py — Wall with footprint-bearing door.

Creates a 6 m wall with a left-swing door whose component provides
a ``footprint()`` method.  The resulting IFC file stores the footprint
curves as an ``IfcShapeRepresentation`` with
``RepresentationIdentifier='FootPrint'`` per the IFC4
**FootPrint GeomSet Geometry** concept template.

Usage:
    python examples/example_footprint.py
"""

from pathlib import Path

from ifckit import IfcModel, IfcSchema, LengthUnit, PendingDoor, PendingWall
from ifckit.geometry import Plane, Vec


def main():
    m = IfcModel(name="FootPrint Demo", schema=IfcSchema.IFC4, unit=LengthUnit.MILLIMETRE)

    site = m.add_site("Building Site")
    bldg = m.add_building(site, "Demo Building")
    storey = m.add_storey(bldg, "Ground Floor", elevation=0.0)

    wall = m.add(
        PendingWall(
            name="Wall-1",
            height=3000.0,
            footprint=[
                Vec(0, 0, 0),
                Vec(6000, 0, 0),
                Vec(6000, 300, 0),
                Vec(0, 300, 0),
            ],
            plane=Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
        ),
        storey,
    )

    door_l = m.add(
        PendingDoor(
            name="Door-L",
            overall_width=900,
            overall_height=2300,
            plane=Plane(Vec(600, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1)),
            component_graph="simple_door",
            operation_type="SINGLE_SWING_LEFT",
            parameters=dict(lining_thickness=50, wall_thickness=300),
        ),
        wall,
    )

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "footprint_demo.ifc"
    m.save(str(output_path))

    print(f"Saved -> {output_path}\n")
    print("Entity      Reps")
    print("------      ----")
    for h in [door_l]:
        rep_ids = [r.RepresentationIdentifier for r in h.entity.Representation.Representations]
        name = h.entity.Name or h.entity.is_a()
        print(f"{name:.<12} {', '.join(rep_ids)}")

    print(
        "\nThe FootPrint representation stores curve data per IFC4 spec.\n"
        "Current IFC viewers do not render curve-only geometry.\n"
    )


if __name__ == "__main__":
    main()
