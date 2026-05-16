"""
ifckit.bonsaikit
================

Bridge between Blender Bonsai (BlenderBIM) and ifckit.

Converts Blender/Python types (mathutils.Vector, bpy.Matrix) to ifckit
geometry types, and provides helper functions to create or replace IFC
products in the active Bonsai project from ifckit Pending* elements.

Usage in Blender Text Editor::

    import bpy
    from ifckit import PendingWall, bonsaikit as bk
    from ifckit.geometry import Vec, Plane

    wall = PendingWall(
        footprint=[Vec(0,0,0), Vec(5,0,0), Vec(5,4,0), Vec(0,4,0)],
        plane=Plane.world_xy(),
        height=3.0,
        name="MyWall",
    )

    obj = bk.add(wall)
    # or:  bk.add(wall, global_id="MyWall")
    # or:  bk.replace(wall, global_id="MyWall")
    # or:  bk.add_or_replace(wall, global_id="MyWall")  # idempotent
"""

from __future__ import annotations

from typing import Any, Optional

from ifckit.geometry import Plane, Vec
from ifckit.reload import reload_all  # noqa: F401

try:
    import bonsai.tool as tool
    import bpy
    import ifcopenshell
    import ifcopenshell.api
    import ifcopenshell.geom as _geom
    import mathutils

    _BONSAI_AVAILABLE = True
except ImportError:
    _BONSAI_AVAILABLE = False


def _require_bonsai(fn_name: str) -> None:
    if not _BONSAI_AVAILABLE:
        raise ImportError(
            f"ifckit.bonsaikit.{fn_name}() requires Blender with Bonsai "
            f"(BlenderBIM) and ifcopenshell \u2014 run inside Blender."
        )


# ---------------------------------------------------------------------------
# Type conversion: mathutils \u2194 ifckit
# ---------------------------------------------------------------------------


def vector_from_bpy(v: Any) -> Vec:
    """mathutils.Vector (or any sequence of 3 floats) to ifckit Vec."""
    return Vec(float(v[0]), float(v[1]), float(v[2]))


def vector_to_bpy(v: Vec) -> Any:
    """ifckit Vec to mathutils.Vector."""
    _require_bonsai("vector_to_bpy")
    return mathutils.Vector((v.x, v.y, v.z))


def matrix_to_plane(m: Any) -> Plane:
    """mathutils.Matrix (4x4) to ifckit Plane.

    Uses translation (origin) and the first two column vectors (x, y axes).
    """
    return Plane(
        origin=Vec(m[0][3], m[1][3], m[2][3]),
        x_axis=Vec(m[0][0], m[1][0], m[2][0]),
        y_axis=Vec(m[0][1], m[1][1], m[2][1]),
    )


def plane_to_matrix(p: Plane) -> Any:
    """ifckit Plane to mathutils.Matrix (4x4, column-major)."""
    _require_bonsai("plane_to_matrix")
    m = mathutils.Matrix.Identity(4)
    m[0][0], m[1][0], m[2][0] = p.x_axis.x, p.x_axis.y, p.x_axis.z
    m[0][1], m[1][1], m[2][1] = p.y_axis.x, p.y_axis.y, p.y_axis.z
    m[0][2], m[1][2], m[2][2] = p.z_axis.x, p.z_axis.y, p.z_axis.z
    m[0][3], m[1][3], m[2][3] = p.origin.x, p.origin.y, p.origin.z
    return m


def bpy_cursor() -> Vec:
    """Blender 3D cursor location as ifckit Vec."""
    _require_bonsai("bpy_cursor")
    return vector_from_bpy(bpy.context.scene.cursor.location)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_ifc_file():
    _require_bonsai("_get_ifc_file")

    ifc_file = tool.Ifc.get()
    if ifc_file is not None:
        return ifc_file

    from bonsai.bim.ifc import IfcStore

    ifc_file = IfcStore.get_file()
    if ifc_file is not None:
        return ifc_file

    raise RuntimeError(
        "No active IFC project in Bonsai.\n\n"
        "Save your IFC file first (Bonsai \u2192 File \u2192 Save IFC File),\n"
        "then close and reopen the .ifc file (Bonsai \u2192 File \u2192 Open).\n"
        "A .blend file alone does not reliably restore the IFC session."
    )


def _get_or_create_storey(ifc_file) -> Any:
    storeys = ifc_file.by_type("IfcBuildingStorey")
    if storeys:
        return storeys[0]

    projects = ifc_file.by_type("IfcProject")
    if not projects:
        raise RuntimeError("No IfcProject found in the active Bonsai file.")
    project = projects[0]

    sites = ifc_file.by_type("IfcSite")
    if sites:
        site = sites[0]
    else:
        site = ifcopenshell.api.run(
            "root.create_entity", ifc_file, ifc_class="IfcSite", name="Site"
        )
        ifcopenshell.api.run(
            "aggregate.assign_object",
            ifc_file,
            products=[site],
            relating_object=project,
        )

    buildings = ifc_file.by_type("IfcBuilding")
    if buildings:
        building = buildings[0]
    else:
        building = ifcopenshell.api.run(
            "root.create_entity", ifc_file, ifc_class="IfcBuilding", name="Building"
        )
        ifcopenshell.api.run(
            "aggregate.assign_object",
            ifc_file,
            products=[building],
            relating_object=site,
        )

    storey = ifcopenshell.api.run(
        "root.create_entity",
        ifc_file,
        ifc_class="IfcBuildingStorey",
        name="Storey",
    )
    ifcopenshell.api.run(
        "aggregate.assign_object",
        ifc_file,
        products=[storey],
        relating_object=building,
    )
    return storey


def _find_containing_storey(ifc_file: Any, entity: Any) -> Optional[Any]:
    for rel in ifc_file.by_type("IfcRelContainedInSpatialStructure"):
        if entity in list(rel.RelatedElements):
            return rel.RelatingStructure
    return None


def _remove_representation_chain(ifc_file: Any, entity: Any) -> None:
    """Detach and remove representation, placement, and containment references."""
    if entity.Representation:
        for rep in list(entity.Representation.Representations or []):
            for item in list(rep.Items or []):
                ifc_file.remove(item)
            ifc_file.remove(rep)
        ifc_file.remove(entity.Representation)
        entity.Representation = None

    if entity.ObjectPlacement:
        ifc_file.remove(entity.ObjectPlacement)
        entity.ObjectPlacement = None

    for rel in list(ifc_file.by_type("IfcRelContainedInSpatialStructure")):
        related = list(rel.RelatedElements)
        if entity in related:
            related.remove(entity)
            if related:
                rel.RelatedElements = related
            else:
                ifc_file.remove(rel)


def _create_mesh(entity: Any, name: str = "") -> Any:
    """Tessellate an IFC entity into a Blender mesh.

    Returns a ``bpy.types.Mesh`` or ``None`` on failure.
    """
    _require_bonsai("_create_mesh")
    try:
        settings = _geom.settings()
        shape = _geom.create_shape(settings, entity)
    except Exception:
        return None

    verts = shape.geometry.verts
    faces = shape.geometry.faces

    n = len(verts) // 3
    b_verts = [(verts[i * 3], verts[i * 3 + 1], verts[i * 3 + 2]) for i in range(n)]
    b_faces = [(faces[i * 3], faces[i * 3 + 1], faces[i * 3 + 2]) for i in range(len(faces) // 3)]

    mesh = bpy.data.meshes.new(name or entity.Name or "IFC")
    mesh.from_pydata(b_verts, [], b_faces)
    mesh.update()
    return mesh


def _by_guid_safe(ifc_file: Any, guid: str) -> Optional[Any]:
    """Look up entity by GlobalId, returning ``None`` (not raising) on miss."""
    try:
        return ifc_file.by_guid(guid)
    except RuntimeError:
        return None


def _link_entity(entity: Any, bpy_obj: Any) -> None:
    _require_bonsai("_link_entity")
    tool.Ifc.link(entity, bpy_obj)
    tool.Collector.assign(bpy_obj)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def add(
    pending: Any,
    *,
    global_id: Optional[str] = None,
    name: Optional[str] = None,
    storey: Optional[Any] = None,
    collection: Optional[Any] = None,
) -> Any:
    """Build a Pending* element into the active Bonsai project.

    Creates the IFC entity, generates a Blender mesh, links the two,
    and places the object in the active collection.

    Args:
        pending:   Any ``PendingElement`` subclass (PendingWall, PendingBeam, \u2026).
        global_id: Stable IFC GlobalId.  If omitted, ifcopenshell generates one.
                   Provide this to enable idempotent ``add_or_replace()``.
        name:      Optional name override for the Blender object.
        storey:    ``IfcBuildingStorey`` entity.  Defaults to the first
                   storey in the project (or auto-created).
        collection: Target Blender collection.  Defaults to active collection.

    Returns:
        The created ``bpy.types.Object``, or ``None`` if tessellation fails.
    """
    _require_bonsai("add")

    ifc_file = _get_ifc_file()
    from ifckit.handles import StoreyHandle
    from ifckit.model import IfcModel

    model = IfcModel.from_file(ifc_file)
    storey_entity = storey or _get_or_create_storey(ifc_file)
    storey_handle = StoreyHandle(storey_entity, model)

    entity_handle = storey_handle.add(pending)
    entity = entity_handle.entity

    if global_id is not None:
        entity.GlobalId = global_id

    mesh = _create_mesh(entity, name or pending.name)
    if mesh is None:
        return None

    obj_name = name or pending.name or entity.is_a()
    obj = bpy.data.objects.new(obj_name, mesh)

    col = collection or bpy.context.collection
    col.objects.link(obj)

    _link_entity(entity, obj)
    return obj


def _resolve_target(
    ifc_file: Any,
    bpy_obj: Optional[Any] = None,
    global_id: Optional[str] = None,
) -> tuple[Any, Any]:
    """Resolve (entity, Blender object) from either *bpy_obj* or *global_id*.

    Raises ``ValueError`` if neither is provided or the target is not found.
    """
    if bpy_obj is not None:
        entity = tool.Ifc.get_entity(bpy_obj)
        if entity is None:
            raise ValueError(f"Object {bpy_obj.name!r} has no associated IFC entity.")
        return entity, bpy_obj

    if global_id is not None:
        ifc_file = _get_ifc_file()
        entity = _by_guid_safe(ifc_file, global_id)
        if entity is None:
            raise ValueError(f"No IFC entity found with GlobalId {global_id!r}.")
        obj = tool.Ifc.get_object(entity)
        if obj is None:
            raise ValueError(
                f"IFC entity {global_id!r} has no linked Blender object. "
                f"Run bk.add() first to create one."
            )
        return entity, obj

    raise ValueError("Either bpy_obj or global_id is required.")


def replace(
    pending: Any,
    bpy_obj: Optional[Any] = None,
    *,
    global_id: Optional[str] = None,
    name: Optional[str] = None,
    collection: Optional[Any] = None,
) -> Any:
    """Replace the IFC geometry of an existing Blender object or GlobalId.

    The IFC entity is rebuilt from *pending* while preserving its
    ``GlobalId`` so that cross-references remain valid.

    Args:
        pending:   Any ``PendingElement`` subclass.
        bpy_obj:   Blender object carrying an IFC entity (has
                   ``BIMObjectProperties.ifc_definition_id``).  Omit when
                   using *global_id*.
        global_id: Stable IFC GlobalId to replace by.  Alternative to
                   *bpy_obj*.
        name:      Optional name override.  Falls back to the Blender
                   object's current name.
        collection: Target collection.  Defaults to active collection.

    Returns:
        The updated ``bpy.types.Object``, or ``None`` if tessellation fails.
    """
    _require_bonsai("replace")

    ifc_file = _get_ifc_file()
    old_entity, bpy_obj = _resolve_target(ifc_file, bpy_obj, global_id)
    old_global_id = old_entity.GlobalId
    old_storey = _find_containing_storey(ifc_file, old_entity)

    _remove_representation_chain(ifc_file, old_entity)
    ifc_file.remove(old_entity)

    from ifckit.handles import StoreyHandle
    from ifckit.model import IfcModel

    model = IfcModel.from_file(ifc_file)
    storey_entity = old_storey or _get_or_create_storey(ifc_file)
    storey_handle = StoreyHandle(storey_entity, model)

    entity_handle = storey_handle.add(pending)
    new_entity = entity_handle.entity
    new_entity.GlobalId = old_global_id

    mesh = _create_mesh(new_entity, name or bpy_obj.name or pending.name)
    if mesh is None:
        return None

    old_mesh = bpy_obj.data
    bpy_obj.data = mesh
    if old_mesh and old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)

    _link_entity(new_entity, bpy_obj)

    return bpy_obj


def add_or_replace(
    pending: Any,
    bpy_obj: Optional[Any] = None,
    *,
    global_id: Optional[str] = None,
    name: Optional[str] = None,
    collection: Optional[Any] = None,
) -> Any:
    """Add *pending* to Bonsai, or replace if target already exists.

    Idempotent: calling this twice with the same *global_id* only ever
    produces one entity.

    Args:
        pending:   Any ``PendingElement`` subclass.
        bpy_obj:   Blender object to replace (if it carries an IFC entity).
        global_id: Stable IFC GlobalId.  If an entity with this ID exists
                   it is replaced; otherwise a new entity is created with
                   this ID.
        name:      Optional name override.
        collection: Target Blender collection.

    Examples::

        bk.add_or_replace(wall)                              # always create
        bk.add_or_replace(wall, bpy_obj)                     # replace or create
        bk.add_or_replace(wall, global_id="MyWall")         # idempotent
    """
    _require_bonsai("add_or_replace")
    try:
        if bpy_obj is not None:
            return replace(pending, bpy_obj, name=name, collection=collection)
        if global_id is not None:
            return replace(pending, global_id=global_id, name=name, collection=collection)
        raise ValueError("bpy_obj or global_id required")
    except (ValueError, RuntimeError):
        return add(pending, global_id=global_id, name=name, collection=collection)
