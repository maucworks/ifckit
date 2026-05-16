"""
bonsai_add_wall.py — add an IfcWall to a running Bonsai project
================================================================
Run this in Blender's **Scripting** workspace while a Bonsai IFC project
is already open (File → Open or File → New IFC Project).

The script:
  1. Reads the active IFC file from Bonsai's IfcStore
  2. Finds (or falls back to) an IfcBuildingStorey to contain the wall
  3. Builds an IfcWall using ifcopenshell.api  (no ifckit dependency needed)
  4. Creates a matching Blender mesh object and links it to the IFC entity
  5. Reloads the Bonsai representation so the wall appears in the 3-D view

Requires: Bonsai (BlenderBIM) add-on installed in Blender 4+
No extra pip installs needed — everything is bundled with Bonsai.

Configuration
-------------
Edit the constants below before running.
"""

# ---------------------------------------------------------------------------
# Configuration — edit these values
# ---------------------------------------------------------------------------

WALL_NAME   = "ifckit-scripted-wall"

# Wall geometry (Bonsai uses metres internally)
WALL_LENGTH    = 5.0    # metres along X
WALL_HEIGHT    = 3.0    # metres
WALL_THICKNESS = 0.2    # metres

# World-space start position of the wall (x, y, z) in metres
WALL_ORIGIN = (0.0, 0.0, 0.0)

# Rotation around Z in radians (0 = wall runs along +X)
import math
WALL_ROTATION_Z = 0.0

# ---------------------------------------------------------------------------
# Imports — all bundled with Bonsai
# ---------------------------------------------------------------------------

import bpy
import mathutils

try:
    import ifcopenshell
    import ifcopenshell.api
    import ifcopenshell.api.geometry
    import ifcopenshell.api.root
    import ifcopenshell.api.spatial
    import ifcopenshell.util.representation
    import ifcopenshell.util.placement
except ModuleNotFoundError:
    raise RuntimeError(
        "ifcopenshell not found. Install the Bonsai (BlenderBIM) add-on first."
    )

try:
    import bonsai.tool as tool
    import bonsai.core.geometry as core_geometry
except ModuleNotFoundError:
    raise RuntimeError(
        "bonsai not found. This script must run inside Blender with the "
        "Bonsai (BlenderBIM) add-on installed and enabled."
    )

# ---------------------------------------------------------------------------
# Step 1: get the active IFC file from Bonsai
# ---------------------------------------------------------------------------

ifc = tool.Ifc.get()
if ifc is None:
    raise RuntimeError(
        "No active IFC project found in Bonsai.\n"
        "Open a project first via File → Open, or create one via "
        "File → New IFC Project."
    )

print(f"\n=== bonsai_add_wall ===")
print(f"Active IFC schema: {ifc.schema}")

# ---------------------------------------------------------------------------
# Step 2: resolve geometric representation context (Body/Model/MODEL_VIEW)
# ---------------------------------------------------------------------------

body_context = ifcopenshell.util.representation.get_context(ifc, "Model", "Body", "MODEL_VIEW")
if body_context is None:
    # Fallback: first Model context
    body_context = next(
        (c for c in ifc.by_type("IfcGeometricRepresentationSubContext")
         if c.ContextIdentifier == "Body"),
        None,
    )
if body_context is None:
    raise RuntimeError(
        "No 'Model/Body/MODEL_VIEW' representation context found in the IFC file."
    )

# ---------------------------------------------------------------------------
# Step 3: find a storey to put the wall in
# ---------------------------------------------------------------------------

# Use Bonsai's active container (the storey selected in the UI) if available.
container = tool.Root.get_default_container()

if container is None:
    # Fall back: first IfcBuildingStorey in the file
    storeys = ifc.by_type("IfcBuildingStorey")
    if storeys:
        container = storeys[0]
        print(f"No active container set — using first storey: '{container.Name}'")
    else:
        raise RuntimeError(
            "No IfcBuildingStorey found in the IFC project.\n"
            "Add at least one storey (Project Overview panel → Add Storey) "
            "before running this script."
        )
else:
    print(f"Using active Bonsai container: '{container.Name}' ({container.is_a()})")

# ---------------------------------------------------------------------------
# Step 4: create the IfcWall entity in the IFC file
# ---------------------------------------------------------------------------

element = ifcopenshell.api.run(
    "root.create_entity",
    ifc,
    ifc_class="IfcWall",
    name=WALL_NAME,
)

# Contain the wall inside the storey
ifcopenshell.api.run(
    "spatial.assign_container",
    ifc,
    products=[element],
    relating_structure=container,
)
print(f"Created {element.is_a()} #{element.id()} '{element.Name}'")

# ---------------------------------------------------------------------------
# Step 5: build the wall geometry (IfcExtrudedAreaSolid via the API)
# ---------------------------------------------------------------------------

representation = ifcopenshell.api.geometry.add_wall_representation(
    ifc,
    context=body_context,
    length=WALL_LENGTH,
    height=WALL_HEIGHT,
    thickness=WALL_THICKNESS,
)

ifcopenshell.api.run(
    "geometry.assign_representation",
    ifc,
    product=element,
    representation=representation,
)
print(f"Wall representation created (length={WALL_LENGTH}m, height={WALL_HEIGHT}m, thickness={WALL_THICKNESS}m)")

# ---------------------------------------------------------------------------
# Step 6: set ObjectPlacement on the IFC entity
#         (rotation around Z + translation)
# ---------------------------------------------------------------------------

# Compute a 4×4 matrix: Rz(rotation) + translation
rot   = mathutils.Matrix.Rotation(WALL_ROTATION_Z, 4, "Z")
trans = mathutils.Matrix.Translation(mathutils.Vector(WALL_ORIGIN))
matrix_world = trans @ rot

# Convert mathutils.Matrix to a flat 4×4 list for ifcopenshell
mat_list = [list(row) for row in matrix_world]

ifcopenshell.api.run(
    "geometry.edit_object_placement",
    ifc,
    product=element,
    matrix=mat_list,
    is_si=True,
)

# ---------------------------------------------------------------------------
# Step 7: create a Blender object and link it to the IFC entity
# ---------------------------------------------------------------------------

# Build a mesh from the IFC geometry using ifcopenshell.geom
settings = ifcopenshell.geom.settings()
try:
    shape   = ifcopenshell.geom.create_shape(settings, element)
    verts   = list(zip(*[iter(shape.geometry.verts)] * 3))
    faces   = list(zip(*[iter(shape.geometry.faces)] * 3))
    mesh    = bpy.data.meshes.new(WALL_NAME)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    print(f"Mesh created: {len(verts)} verts, {len(faces)} faces")
except Exception as exc:
    # Geometry tessellation failed — create an empty mesh (still shows in IFC tree)
    print(f"Warning: could not tessellate geometry ({exc}) — creating empty mesh")
    mesh = bpy.data.meshes.new(WALL_NAME)

obj = bpy.data.objects.new(WALL_NAME, mesh)

# Set the Blender world matrix to match the IFC placement
obj.matrix_world = matrix_world

# Register the object in the active view-layer collection
bpy.context.collection.objects.link(obj)

# Link the IFC entity to the Blender object so Bonsai knows about it
tool.Ifc.link(element, obj)

# Place the object in the correct Bonsai spatial collection
tool.Collector.assign(obj)

# ---------------------------------------------------------------------------
# Step 8: reload the representation in Bonsai so it shows the IFC geometry
# ---------------------------------------------------------------------------

try:
    core_geometry.switch_representation(
        tool.Ifc,
        tool.Geometry,
        obj=obj,
        representation=representation,
    )
    print("Bonsai representation reloaded.")
except Exception as exc:
    # Non-fatal: the wall is in the IFC file; visual refresh may need manual F12 / reload
    print(f"Note: could not auto-switch Bonsai representation ({exc}).")
    print("Tip: select the wall object and press F12, or reload the project.")

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------

# Select the new object in the Blender scene
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

print(f"\nDone — '{WALL_NAME}' added to storey '{container.Name}'.")
print(f"IFC entity: {element.is_a()} GlobalId={element.GlobalId}")
print("Save the project with Ctrl+S to persist changes to the .ifc file.")
