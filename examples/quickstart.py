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

from ifckit import IfcModel, IfcSchema, PendingWall, Vec, Plane, validate
from ifckit.builders import default_registry
from ifckit.builders._geom import get_body_context

# Build the spatial hierarchy
model = IfcModel(name="My Project", schema=IfcSchema.IFC4, author="you")
site = model.add_site("Site A")
bldg = model.add_building(site, "Building 1")
floor = model.add_storey(bldg, "Ground Floor", elevation=0.0)
floor_1 = model.add_storey(bldg, "First Floor", elevation=3.0)


# Define the elements — plane origin Z must be in world space
wall_gf = PendingWall(
    footprint=[Vec(0, 0, 0), Vec(10, 0, 0), Vec(10, 0.3, 0), Vec(0, 0.3, 0)],
    plane=Plane.world_xy(),                              # Z=0, elevation=0 → local Z=0
    height=3.0,
    name="North Facade GF",
)
wall_1f = PendingWall(
    footprint=[Vec(0, 0, 0), Vec(10, 0, 0), Vec(10, 0.3, 0), Vec(0, 0.3, 0)],
    plane=Plane(Vec(0, 0, 3.0), Vec(1, 0, 0), Vec(0, 1, 0)),  # Z=3, elevation=3 → local Z=0
    height=3.0,
    name="North Facade 1F",
)

# Validate, then build into the IFC file
for wall in (wall_gf, wall_1f):
    result = validate(wall)
    assert result.ok, result.errors

reg = default_registry()
ctx = get_body_context(model.ifc_file)
reg.get("basic_wall").build(model.ifc_file, wall_gf, floor.entity, ctx)
reg.get("basic_wall").build(model.ifc_file, wall_1f, floor_1.entity, ctx)


# Save
os.makedirs("output", exist_ok=True)
model.save("output/quickstart.ifc")
print("Saved: output/quickstart.ifc")
