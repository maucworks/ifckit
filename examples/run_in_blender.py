"""
ifckit Blender Example
======================
Run this script directly in Blender's Scripting workspace.

Builds the same model as examples/hello_wall.json using the Python API:
  - 1 IfcWall (8000 × 300 × 3000 mm)
  - 4 IfcWindow via Model B component_graph (openings auto-generated)
  - 1 IfcDoor via Model B component_graph

Saves the result to OUTPUT_PATH, then imports it into the current Blender
scene via two methods (in order of preference):

  1. Bonsai (BlenderBIM) — full BIM import via bpy.ops.bim.load_project()
  2. Direct mesh import — ifcopenshell.geom.create_shape() → bpy mesh
     (geometry-only fallback, no BIM data, but no Bonsai required)

Requirements
------------
Install ifckit in Blender's Python environment.  Open Blender's Scripting
editor, paste and run once:

    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pip", "install", "ifckit[ifc]"], check=True)

ifcopenshell is bundled with Blender when Bonsai is installed.
If Bonsai is not installed, install ifckit[ifc] which pulls in ifcopenshell.

Usage
-----
Paste this file into Blender's Scripting editor and press Run Script.
Adjust OUTPUT_PATH below if needed.
"""

from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# Configuration — edit this path if needed
# ---------------------------------------------------------------------------

OUTPUT_PATH = os.path.expanduser("~/ifckit_blender_demo.ifc")

# ---------------------------------------------------------------------------
# Prerequisites check
# ---------------------------------------------------------------------------

try:
    import bpy  # noqa: F401 — confirms we are inside Blender
except ModuleNotFoundError:
    raise RuntimeError(
        "bpy not found. Run this script inside Blender's Scripting workspace."
    )

try:
    import ifckit  # noqa: F401
except ModuleNotFoundError:
    # Auto-install ifckit in Blender's own Python, then re-import.
    print("ifckit not found — installing now (this may take a minute)…")
    import subprocess
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "ifckit[ifc]"],
        check=True,
    )
    import importlib
    import ifckit  # noqa: F401  # second attempt after install
    print("ifckit installed successfully.")

try:
    import ifcopenshell
    import ifcopenshell.geom as _geom
except ModuleNotFoundError:
    raise RuntimeError(
        "ifcopenshell not found — install Bonsai (BlenderBIM) add-on, "
        "or re-run this script after ifckit[ifc] has been installed "
        "(the ifckit install block above should have pulled it in)."
    )

# ---------------------------------------------------------------------------
# Build IFC model (Python API — equivalent to hello_wall.json)
# ---------------------------------------------------------------------------

from ifckit import IfcModel, LengthUnit
from ifckit.elements.opening import PendingWindow, PendingDoor
from ifckit.elements.types import PendingWindowType, PendingDoorType
from ifckit.elements.building import PendingWall
from ifckit.geometry import Plane, Vec
from ifckit.schema import IfcSchema

print("\n=== ifckit Blender Demo ===\n")
print("Building IFC model…")

model = IfcModel(
    name="Blender Demo",
    schema=IfcSchema.IFC4,
    author="ifckit",
    unit=LengthUnit.MILLIMETRE,
)

site     = model.add_site("Example Site")
building = site.add_building("Demo Building")
storey   = building.add_storey("Ground Floor", elevation=0.0)

# --- Wall -------------------------------------------------------------------

world_xy = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))

wall_handle = storey.add(
    PendingWall(
        name="Simple Wall",
        footprint=[
            Vec(0.0, 0.0, 0.0),
            Vec(8000.0, 0.0, 0.0),
            Vec(8000.0, 300.0, 0.0),
            Vec(0.0, 300.0, 0.0),
        ],
        plane=world_xy,
        height=3000.0,
    )
)

# --- Window type ------------------------------------------------------------

wt_handle = model.add_window_type(
    PendingWindowType(
        name="WT-2000x500",
        overall_width=2000.0,
        overall_height=500.0,
        lining_thickness=10.0,
        lining_depth=100.0,
        component_graph="fixed_casement",
    )
)

# --- Door type --------------------------------------------------------------

dt_handle = model.add_door_type(
    PendingDoorType(
        name="DT-1000x2300",
        overall_width=1000.0,
        overall_height=2300.0,
        lining_thickness=10.0,
        lining_depth=150.0,
        component_graph="fixed_casement",
    )
)

# --- Windows (Model B: component_graph drives opening + geometry) -----------

# Helper: plane in the wall face (XZ-plane of the wall)
def _wall_plane(x_origin: float, z_origin: float) -> Plane:
    return Plane(
        Vec(x_origin, 0.0, z_origin),
        Vec(1.0, 0.0, 0.0),   # x_axis → along wall length
        Vec(0.0, 0.0, 1.0),   # y_axis → up
    )


model.add(
    PendingWindow(
        name="W-1",
        overall_width=500.0,
        overall_height=2000.0,
        plane=_wall_plane(1500.0, 500.0),
        component_graph="fixed_casement",
        parameters={"lining_depth": 300.0},
    ),
    wall_handle,
)

model.add(
    PendingWindow(
        name="W-2",
        overall_width=500.0,
        overall_height=2000.0,
        plane=_wall_plane(2500.0, 500.0),
        component_graph="fixed_casement_component",
        parameters={"lining_depth": 300.0},
    ),
    wall_handle,
)

model.add(
    PendingWindow(
        name="W-3",
        overall_width=1000.0,
        overall_height=1000.0,
        plane=_wall_plane(4000.0, 1500.0),
        component_graph="rounded_casement_component",
        parameters={"lining_depth": 300.0},
    ),
    wall_handle,
)

model.add(
    PendingWindow(
        name="W-4",
        overall_width=2000.0,
        overall_height=500.0,
        plane=_wall_plane(4000.0, 500.0),
        component_graph="rounded_casement_component",
        parameters={"lining_depth": 300.0},
    ),
    wall_handle,
)

# --- Door -------------------------------------------------------------------

model.add(
    PendingDoor(
        name="D-1",
        overall_width=2000.0,
        overall_height=3000.0,
        plane=_wall_plane(7000.0, 0.0),
        component_graph="fixed_casement",
        parameters={"lining_depth": 200.0},
    ),
    wall_handle,
)

# --- Save -------------------------------------------------------------------

os.makedirs(os.path.dirname(OUTPUT_PATH) or ".", exist_ok=True)
model.save(OUTPUT_PATH)
print(f"IFC saved to: {OUTPUT_PATH}")

ifc = model.ifc_file
print(f"  IfcWall:           {len(ifc.by_type('IfcWall'))}")
print(f"  IfcWindow:         {len(ifc.by_type('IfcWindow'))}")
print(f"  IfcDoor:           {len(ifc.by_type('IfcDoor'))}")
print(f"  IfcOpeningElement: {len(ifc.by_type('IfcOpeningElement'))}")

# ---------------------------------------------------------------------------
# Import into Blender — method 1: Bonsai (BlenderBIM)
# ---------------------------------------------------------------------------

_imported_via_bonsai = False

if hasattr(bpy.ops, "bim") and hasattr(bpy.ops.bim, "load_project"):
    print("\nImporting via Bonsai (BlenderBIM)…")
    try:
        bpy.ops.bim.load_project(filepath=OUTPUT_PATH)
        _imported_via_bonsai = True
        print("  Bonsai import done.")
    except Exception as exc:  # pragma: no cover
        print(f"  Bonsai import failed ({exc}), falling back to direct mesh import.")

# ---------------------------------------------------------------------------
# Import into Blender — method 2: direct mesh (fallback / always available)
# ---------------------------------------------------------------------------

if not _imported_via_bonsai:
    print("\nImporting via direct mesh (ifcopenshell.geom)…")

    # Clear existing scene objects
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    settings = _geom.settings()
    loaded_ifc = ifcopenshell.open(OUTPUT_PATH)

    n_ok = 0
    n_err = 0

    for product in loaded_ifc.by_type("IfcProduct"):
        if not getattr(product, "Representation", None):
            continue
        try:
            shape   = _geom.create_shape(settings, product)
            verts   = list(zip(*[iter(shape.geometry.verts)] * 3))
            faces   = list(zip(*[iter(shape.geometry.faces)] * 3))

            label   = product.Name or product.is_a()
            mesh    = bpy.data.meshes.new(name=label)
            mesh.from_pydata(verts, [], faces)
            mesh.update()

            obj = bpy.data.objects.new(label, mesh)
            bpy.context.collection.objects.link(obj)
            n_ok += 1
        except Exception as exc:
            n_err += 1
            print(f"  skip {product.is_a()} '{product.Name}': {exc}")

    print(f"  Imported {n_ok} mesh(es), {n_err} skipped.")

print("\nDone. Open the IFC in Bonsai via: File → Import → IFC")
print(f"  Path: {OUTPUT_PATH}")
