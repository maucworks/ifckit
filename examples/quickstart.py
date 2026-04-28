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
site  = model.add_site("Site A")
bldg  = model.add_building(site, "Building 1")
floor = model.add_storey(bldg, "Ground Floor", elevation=0.0)

# Define the element
wall = PendingWall(
    footprint=[Vec(0, 0, 0), Vec(10, 0, 0), Vec(10, 0.3, 0), Vec(0, 0.3, 0)],
    plane=Plane.world_xy(),
    height=3.0,
    name="North Facade",
)

# Validate, then build into the IFC file
result = validate(wall)
assert result.ok, result.errors

reg = default_registry()
ctx = get_body_context(model.ifc_file)
reg.get("basic_wall").build(model.ifc_file, wall, floor.entity, ctx)

# Save
os.makedirs("output", exist_ok=True)
model.save("output/quickstart.ifc")
print("Saved: output/quickstart.ifc")
