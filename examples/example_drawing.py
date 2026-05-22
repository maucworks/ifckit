#!/usr/bin/env python3
"""
example_drawing.py — Wall + door + floor-plan drawing at z=1500 mm.

Generates:
- An IFC file with a wall, a door, and an IfcAnnotation[DRAWING] at z=1500.
- A headless SVG floor plan from ifcopenshell.draw, with door swing arcs
  injected by ifckit.draw.inject_symbols().

Usage:
    python examples/example_drawing.py
    # opens examples/output/demo_drawing.svg in browser
"""

from pathlib import Path

from ifckit import IfcModel, IfcSchema, LengthUnit, PendingDoor, PendingWall
from ifckit.draw import generate_svg, inject_symbols, save_svg
from ifckit.geometry import Plane, Vec


def main():
    m = IfcModel(name="Drawing Demo", schema=IfcSchema.IFC4, unit=LengthUnit.MILLIMETRE)

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

    m.add(
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

    m.add_drawing(
        name="Ground Floor Plan",
        target_view="PLAN_VIEW",
        position=(3000, 0, 1500),
        x_axis=(1, 0, 0),
        z_axis=(0, 0, -1),
    )

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    ifc_path = output_dir / "demo_drawing.ifc"
    m.save(str(ifc_path))
    print(f"IFC -> {ifc_path}")

    svg_path = output_dir / "demo_drawing.svg"
    svg_bytes = generate_svg(
        m, drawing_object_type="DRAWING", door_arcs=True, include_curves=True
    )
    svg_bytes = inject_symbols(svg_bytes, m.ifc_file)
    save_svg(svg_bytes, str(svg_path))
    print(f"SVG -> {svg_path}")

    paths_injected = sum(
        1 for line in svg_bytes.decode().splitlines()
        if 'class="IfcDoor"' in line and 'stroke-dasharray' in line
    )
    print(f"Door swing arcs injected: {paths_injected}")
    print("\nOpen the SVG in any browser or vector editor.")


if __name__ == "__main__":
    main()
