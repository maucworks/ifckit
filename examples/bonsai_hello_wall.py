"""
bonsai_hello_wall.py — voeg een ifckit hello_wall toe aan een lopend Bonsai project
=====================================================================================
Run this in Blender's Scripting workspace while a Bonsai IFC project is open.

Uses IfcModel.from_file() to wrap the active Bonsai IFC file, then builds
the same hello_wall model as examples/hello_wall.json using the full ifckit
API — including Model B windows with component_graph-driven openings.

After running, save with Ctrl+S to persist changes to the .ifc file.

Requirements
------------
ifckit must be installed in Blender's Python.  Run once in the Scripting editor:

    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pip", "install", "ifckit[ifc]"], check=True)

ifcopenshell is bundled with Bonsai.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Name for the new wall and its storey.
# If a storey with this name already exists it will be reused.
STOREY_NAME = "ifckit Demo Floor"
WALL_NAME   = "ifckit Wall"

# Wall footprint (millimetres — Bonsai project must use mm units)
WALL_LENGTH_MM = 8000.0
WALL_THICKNESS_MM = 300.0
WALL_HEIGHT_MM = 3000.0

# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------

import sys

try:
    import bpy
except ModuleNotFoundError:
    raise RuntimeError("Run this inside Blender's Scripting workspace.")

try:
    import importlib.metadata as _meta
    from packaging.version import Version as _V
    _required = "0.2.1"
    try:
        _installed = _meta.version("ifckit")
    except _meta.PackageNotFoundError:
        _installed = "0.0.0"
    if _V(_installed) < _V(_required):
        raise ImportError(f"ifckit {_installed} < {_required}")
    import ifckit  # noqa: F401
except (ImportError, ModuleNotFoundError):
    print(f"ifckit >= 0.2.0 not found — installing now…")
    import subprocess
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "ifckit[ifc]>=0.2.1"],
        check=True,
    )
    import ifckit  # noqa: F401
    print("ifckit installed.")

try:
    import bonsai.tool as tool
    import bonsai.core.geometry as core_geometry
except ModuleNotFoundError:
    raise RuntimeError(
        "Bonsai (BlenderBIM) add-on not found. "
        "Install it and open an IFC project before running this script."
    )

# ---------------------------------------------------------------------------
# Step 1: wrap the active Bonsai IFC file with IfcModel.from_file()
# ---------------------------------------------------------------------------

from ifckit.model import IfcModel
from ifckit.handles import StoreyHandle, BuildingHandle
from ifckit.elements.building import PendingWall
from ifckit.elements.opening import PendingWindow, PendingDoor
from ifckit.elements.types import PendingWindowType, PendingDoorType
from ifckit.geometry import Plane, Vec

ifc = tool.Ifc.get()
if ifc is None:
    raise RuntimeError(
        "No active IFC project in Bonsai.\n"
        "Open a project first: File → Open, or File → New IFC Project."
    )

print("\n=== bonsai_hello_wall (ifckit) ===")
print(f"Active project: '{ifc.by_type('IfcProject')[0].Name}'  schema={ifc.schema}")

# Wrap without touching existing project structure
model = IfcModel.from_file(ifc)
print(f"IfcModel.from_file() OK  unit={model.unit.name}  schema={model.schema.value}")

# ---------------------------------------------------------------------------
# Step 2: find or create a building + storey to put our elements in
# ---------------------------------------------------------------------------

import ifcopenshell.api
import ifcopenshell.util.element

# Use the active Bonsai container when set, otherwise find/create a storey
container = tool.Root.get_default_container()

if container is not None and container.is_a("IfcBuildingStorey"):
    storey_entity = container
    print(f"Using active Bonsai container: '{storey_entity.Name}'")
else:
    # Find an existing storey with the target name
    storey_entity = next(
        (s for s in ifc.by_type("IfcBuildingStorey") if s.Name == STOREY_NAME),
        None,
    )
    if storey_entity is None:
        # Create a new building + storey under the first site
        sites = ifc.by_type("IfcSite")
        if not sites:
            raise RuntimeError(
                "No IfcSite found in the project. "
                "Add a site via Bonsai's Project Overview panel first."
            )
        site_handle = model.add_site.__func__  # we need the API, use raw call below
        # Find or create a building
        buildings = ifc.by_type("IfcBuilding")
        if buildings:
            building_entity = buildings[0]
        else:
            building_entity = ifcopenshell.api.run(
                "root.create_entity", ifc, ifc_class="IfcBuilding", name="Demo Building"
            )
            ifcopenshell.api.run(
                "aggregate.assign_object",
                ifc,
                products=[building_entity],
                relating_object=sites[0],
            )
        # Create the storey
        storey_entity = ifcopenshell.api.run(
            "root.create_entity", ifc, ifc_class="IfcBuildingStorey", name=STOREY_NAME
        )
        storey_entity.Elevation = 0.0
        ifcopenshell.api.run(
            "aggregate.assign_object",
            ifc,
            products=[storey_entity],
            relating_object=building_entity,
        )
        print(f"Created new storey: '{STOREY_NAME}'")
    else:
        print(f"Reusing existing storey: '{storey_entity.Name}'")

storey = StoreyHandle(storey_entity, model)

# ---------------------------------------------------------------------------
# Step 3: build the wall
# ---------------------------------------------------------------------------

world_xy = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))

wall_handle = storey.add(
    PendingWall(
        name=WALL_NAME,
        footprint=[
            Vec(0.0,            0.0,              0.0),
            Vec(WALL_LENGTH_MM, 0.0,              0.0),
            Vec(WALL_LENGTH_MM, WALL_THICKNESS_MM, 0.0),
            Vec(0.0,            WALL_THICKNESS_MM, 0.0),
        ],
        plane=world_xy,
        height=WALL_HEIGHT_MM,
    )
)
print(f"Wall created: #{wall_handle.entity.id()} '{wall_handle.entity.Name}'")

# ---------------------------------------------------------------------------
# Step 4: window type + Model B windows (component_graph drives openings)
# ---------------------------------------------------------------------------

def _wp(x_mm: float, z_mm: float) -> Plane:
    """Plane in the front face of the wall (XZ orientation)."""
    return Plane(Vec(x_mm, 0.0, z_mm), Vec(1, 0, 0), Vec(0, 0, 1))


# Window type
model.add_window_type(
    PendingWindowType(
        name="WT-2000x500",
        overall_width=2000.0,
        overall_height=500.0,
        lining_thickness=10.0,
        lining_depth=100.0,
        component_graph="fixed_casement",
    )
)

# Windows — identical to hello_wall.json
w1 = model.add(PendingWindow(
    name="W-1",
    overall_width=500.0,
    overall_height=2000.0,
    plane=_wp(1500.0, 500.0),
    component_graph="fixed_casement",
    parameters={"lining_depth": 300.0},
), wall_handle)

w2 = model.add(PendingWindow(
    name="W-2",
    overall_width=500.0,
    overall_height=2000.0,
    plane=_wp(2500.0, 500.0),
    component_graph="fixed_casement_component",
    parameters={"lining_depth": 300.0},
), wall_handle)

w3 = model.add(PendingWindow(
    name="W-3",
    overall_width=1000.0,
    overall_height=1000.0,
    plane=_wp(4000.0, 1500.0),
    component_graph="rounded_casement_component",
    parameters={"lining_depth": 300.0},
), wall_handle)

w4 = model.add(PendingWindow(
    name="W-4",
    overall_width=2000.0,
    overall_height=500.0,
    plane=_wp(4000.0, 500.0),
    component_graph="rounded_casement_component",
    parameters={"lining_depth": 300.0},
), wall_handle)

# ---------------------------------------------------------------------------
# Step 5: door
# ---------------------------------------------------------------------------

model.add_door_type(
    PendingDoorType(
        name="DT-1000x2300",
        overall_width=1000.0,
        overall_height=2300.0,
        lining_thickness=10.0,
        lining_depth=150.0,
        component_graph="fixed_casement",
    )
)

d1 = model.add(PendingDoor(
    name="D-1",
    overall_width=2000.0,
    overall_height=3000.0,
    plane=_wp(7000.0, 0.0),
    component_graph="fixed_casement",
    parameters={"lining_depth": 200.0},
), wall_handle)

print(f"Windows: {len(ifc.by_type('IfcWindow'))}  "
      f"Doors: {len(ifc.by_type('IfcDoor'))}  "
      f"Openings: {len(ifc.by_type('IfcOpeningElement'))}")

# ---------------------------------------------------------------------------
# Step 6: load the new elements into the Blender scene
# ---------------------------------------------------------------------------
# We import all newly created products as Blender mesh objects and link them
# to their IFC entities so Bonsai is aware of them.

import ifcopenshell.geom as _geom

settings = _geom.settings()
new_entities = [
    wall_handle.entity,
    w1.entity, w2.entity, w3.entity, w4.entity,
    d1.entity,
    # also import the opening elements so the wall cut-outs are visible
    *ifc.by_type("IfcOpeningElement"),
]
# Deduplicate (openings may already be in the list)
seen_ids: set[int] = set()
unique_entities = []
for e in new_entities:
    if e.id() not in seen_ids:
        seen_ids.add(e.id())
        unique_entities.append(e)

imported = 0
for entity in unique_entities:
    try:
        shape = _geom.create_shape(settings, entity)
        verts = list(zip(*[iter(shape.geometry.verts)] * 3))
        faces = list(zip(*[iter(shape.geometry.faces)] * 3))

        label = entity.Name or entity.is_a()
        mesh  = bpy.data.meshes.new(label)
        mesh.from_pydata(verts, [], faces)
        mesh.update()

        obj = bpy.data.objects.new(label, mesh)
        bpy.context.collection.objects.link(obj)

        # Link to IFC entity so Bonsai can manage it
        tool.Ifc.link(entity, obj)
        tool.Collector.assign(obj)
        imported += 1
    except Exception as exc:
        print(f"  skip {entity.is_a()} '{entity.Name}': {exc}")

print(f"Imported {imported} object(s) into Blender scene.")

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

print("\nDone.  Save with Ctrl+S to write changes to the .ifc file.")
print("Tip: reload the project (File → Revert) for full Bonsai BIM data.")
