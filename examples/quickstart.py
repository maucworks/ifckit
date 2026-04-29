"""
quickstart.py
=============

Minimal runnable example: one wall in an IFC4 building.

Run from the project root::

    python examples/quickstart.py
    # writes:  output/quickstart.ifc
"""

import os
import sys

# Allow running from the project root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ifckit import IfcModel, IfcSchema, PendingWall, Vec, Plane

# Build the spatial hierarchy (handle chaining)
model = IfcModel(name="My Project", schema=IfcSchema.IFC4, author="you")
bldg = model.add_site("Site A").add_building("Building 1")
floor = bldg.add_storey("Ground Floor", elevation=0.0)
floor_1 = bldg.add_storey("First Floor", elevation=3.0)

# Define the elements — plane origin Z must be in world space
wall_gf = PendingWall(
    footprint=[Vec(0, 0, 0), Vec(10, 0, 0), Vec(10, 0.3, 0), Vec(0, 0.3, 0)],
    plane=Plane.world_xy(),  # Z=0, elevation=0 → local Z=0
    height=3.0,
    name="North Facade GF",
)
wall_1f = PendingWall(
    footprint=[Vec(0, 0, 0), Vec(10, 0, 0), Vec(10, 0.3, 0), Vec(0, 0.3, 0)],
    plane=Plane(Vec(0, 0, 3.0), Vec(1, 0, 0), Vec(0, 1, 0)),  # Z=3, elevation=3 → local Z=0
    height=3.0,
    name="North Facade 1F",
)

# Validate and build in one call — raises ValueError if invalid
floor.add(wall_gf)
floor_1.add(wall_1f)


# Save
os.makedirs("output", exist_ok=True)
model.save("output/quickstart.ifc")
print("Saved: output/quickstart.ifc")
