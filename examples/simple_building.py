"""
simple_building.py
==================

Runnable example: a two-storey IFC4 office building with walls, slabs,
beams, and columns.

Run from the project root::

    python examples/simple_building.py
    # writes:  output/simple_building.ifc

The output can be opened in any IFC viewer (e.g. BlenderBIM, Solibri,
FZKViewer).
"""

import math
import os
import sys

# Allow running from the project root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ifckit import (
    IfcModel, IfcSchema,
    PendingWall, PendingSlab, PendingBeam, PendingColumn,
    Vec, Plane, Line,
    validate,
)
from ifckit.builders import default_registry
from ifckit.builders._geom import get_body_context


# ---------------------------------------------------------------------------
# Building geometry parameters
# ---------------------------------------------------------------------------

WIDTH = 12.0        # m  (X)
DEPTH = 8.0         # m  (Y)
STOREY_HEIGHT = 3.5 # m  (Z per storey)
WALL_THICKNESS = 0.3
SLAB_THICKNESS = 0.25
COLUMN_SIZE = 0.4
NUM_STOREYS = 2

# Outer footprint (CCW in XY)
OUTER_FOOTPRINT = [
    Vec(0, 0, 0),
    Vec(WIDTH, 0, 0),
    Vec(WIDTH, DEPTH, 0),
    Vec(0, DEPTH, 0),
]

# Square column profile (local YZ plane — XY here since builders project)
COLUMN_PROFILE = [
    Vec(0, 0),
    Vec(COLUMN_SIZE, 0),
    Vec(COLUMN_SIZE, COLUMN_SIZE),
    Vec(0, COLUMN_SIZE),
]

# Rectangular beam profile
BEAM_PROFILE = [
    Vec(0, -0.15),
    Vec(0.4, -0.15),
    Vec(0.4, 0.15),
    Vec(0, 0.15),
]

# Column grid: 4 corners + 2 mid-span points
COLUMN_X = [0.0, WIDTH / 2, WIDTH]
COLUMN_Y = [0.0, DEPTH]


def build_storey(model, storey, elevation: float, reg, ctx) -> None:
    """Add walls, slab, columns, and a span beam to one storey."""
    z = elevation

    # --- Perimeter wall (one per face, simple approach: one wall per side) ---
    wall_planes_and_footprints = [
        # South face
        (Plane.world_xy(),
         [Vec(0, 0, z), Vec(WIDTH, 0, z),
          Vec(WIDTH, WALL_THICKNESS, z), Vec(0, WALL_THICKNESS, z)]),
        # North face
        (Plane.world_xy(),
         [Vec(0, DEPTH - WALL_THICKNESS, z), Vec(WIDTH, DEPTH - WALL_THICKNESS, z),
          Vec(WIDTH, DEPTH, z), Vec(0, DEPTH, z)]),
        # West face
        (Plane.world_xy(),
         [Vec(0, 0, z), Vec(WALL_THICKNESS, 0, z),
          Vec(WALL_THICKNESS, DEPTH, z), Vec(0, DEPTH, z)]),
        # East face
        (Plane.world_xy(),
         [Vec(WIDTH - WALL_THICKNESS, 0, z), Vec(WIDTH, 0, z),
          Vec(WIDTH, DEPTH, z), Vec(WIDTH - WALL_THICKNESS, DEPTH, z)]),
    ]

    for i, (plane, fp) in enumerate(wall_planes_and_footprints):
        wall = PendingWall(
            footprint=fp,
            plane=plane,
            height=STOREY_HEIGHT,
            name=f"Wall_{storey.entity.Name}_{i}",
        )
        result = validate(wall)
        assert result.ok, f"Wall validation failed: {result.errors}"
        reg.get("basic_wall").build(model.ifc_file, wall, storey.entity, ctx)

    # --- Floor slab ---
    slab = PendingSlab(
        footprint=OUTER_FOOTPRINT,
        plane=Plane.world_xy(),
        thickness=SLAB_THICKNESS,
        name=f"Slab_{storey.entity.Name}",
    )
    result = validate(slab)
    assert result.ok, f"Slab validation failed: {result.errors}"
    reg.get("basic_slab").build(model.ifc_file, slab, storey.entity, ctx)

    # --- Columns at grid intersections ---
    for cx in COLUMN_X:
        for cy in COLUMN_Y:
            col_axis = Line(Vec(cx, cy, z), Vec(cx, cy, z + STOREY_HEIGHT))
            col = PendingColumn(
                axis=col_axis,
                profile=COLUMN_PROFILE,
                name=f"Col_{storey.entity.Name}_{cx:.0f}_{cy:.0f}",
            )
            result = validate(col)
            assert result.ok, f"Column validation failed: {result.errors}"
            reg.get("basic_column").build(model.ifc_file, col, storey.entity, ctx)

    # --- Span beams along X-axis at Y=DEPTH/2 ---
    for i in range(len(COLUMN_X) - 1):
        x0, x1 = COLUMN_X[i], COLUMN_X[i + 1]
        beam_axis = Line(Vec(x0, DEPTH / 2, z + STOREY_HEIGHT - 0.5),
                         Vec(x1, DEPTH / 2, z + STOREY_HEIGHT - 0.5))
        beam = PendingBeam(
            axis=beam_axis,
            profile=BEAM_PROFILE,
            name=f"Beam_{storey.entity.Name}_{i}",
        )
        result = validate(beam)
        assert result.ok, f"Beam validation failed: {result.errors}"
        reg.get("basic_beam").build(model.ifc_file, beam, storey.entity, ctx)


def main(output_path: str = "output/simple_building.ifc") -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    model = IfcModel(
        name="SimpleOfficeBuilding",
        schema=IfcSchema.IFC4,
        author="ifckit example",
    )

    site = model.add_site("Campus Site", description="Example site")
    building = model.add_building(site, "Office Block A")

    reg = default_registry()
    ctx = get_body_context(model.ifc_file)

    for level in range(NUM_STOREYS):
        elevation = level * STOREY_HEIGHT
        storey = model.add_storey(
            building,
            name=f"Level {level}",
            elevation=elevation,
        )
        build_storey(model, storey, elevation, reg, ctx)

    model.save(output_path)
    print(f"Saved: {output_path}")

    # Quick summary
    f = model.ifc_file
    print(f"  IfcWall:             {len(f.by_type('IfcWall'))}")
    print(f"  IfcSlab:             {len(f.by_type('IfcSlab'))}")
    print(f"  IfcColumn:           {len(f.by_type('IfcColumn'))}")
    print(f"  IfcBeam:             {len(f.by_type('IfcBeam'))}")
    print(f"  IfcBuildingStorey:   {len(f.by_type('IfcBuildingStorey'))}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "output/simple_building.ifc"
    main(out)
