Coordinate Systems & Placement Conventions
============================================

IFC uses a hierarchical placement chain. Every element sits inside a cascade of
local coordinate frames:

    World
     └── IfcSite
          └── IfcBuilding
               └── IfcBuildingStorey      ← "storey coordinates"
                    └── IfcWall           ← wall-local coordinates
                         └── IfcOpeningElement
                              └── IfcDoor / IfcWindow

Each level's ``ObjectPlacement`` is defined **relative to its parent**.  A
product's geometry is expressed in its own local frame, and the chain of
affine transforms maps it to world space.

1 – API Convention: storey coordinates
--------------------------------------

**All ``PendingElement`` planes in ifckit are expressed in the storey's
coordinate frame.**

This means you specify positions as if the storey were an absolute reference
frame.  You do **not** need to think about the wall's local orientation.

    # Correct:  plane in storey coordinates
    PendingWindow(
        path=outer,
        plane=Plane(Vec(2, 8, 1.5), Vec(1, 0, 0), Vec(0, 0, 1)),
        ...
    )

The origin ``(2, 8, 1.5)`` reads naturally: "2 m along the X-axis, 8 m along
the Y-axis, 1.5 m up" — all in the storey's coordinate system.

1.1 – Why storey coordinates?
-----------------------------

- Walls, slabs, windows and doors all share the same reference frame.
- You can place a window at ``(2, 8, 1.5)`` without knowing how the wall's
  coordinate axes are oriented.
- The internal transformation to wall-local coordinates happens automatically.

2 – Plane semantics
-------------------

An ifckit ``Plane`` stores three pieces of data:

    Plane(origin: Vec, x_axis: Vec, y_axis: Vec)

| Component | Meaning                                   |
|-----------|-------------------------------------------|
| origin    | Insertion point (metres)                  |
| x_axis    | Local X-direction (width for openings)    |
| y_axis    | Local Y-direction (height for openings)   |

The Z-axis is **derived** by the cross product ``z_axis = x_axis ** y_axis``
(right-handed).  It is **never stored** explicitly.

2.1 – Opening / Door / Window convention
-----------------------------------------

For openings (and their fill elements):

| Axis   | Direction                     |
|--------|-------------------------------|
| X      | Width direction (horizontal)  |
| Y      | Height direction (up)         |
| Z      | Extrusion / through-wall      |

This matches the IFC ``IfcAxis2Placement3D`` convention where ``Axis``
stores the Z-direction and ``RefDirection`` stores the X-direction.

3 – Wall placement
------------------

A ``PendingWallGraph`` uses its ``Plane`` to position the wall profile in the
storey.

    wall = PendingWallGraph(
        path=outer,
        plane=Plane(
            Vec(0, 8, 0),     # wall sits at Y = 8 in storey space
            Vec(1, 0, 0),     # width direction = storey X
            Vec(0, 0, 1),     # height direction = storey Z (up)
        ),
        offset_right=0,
        offset_left=0.3,
        height=8,
    )

The plane's Z-axis is computed as ``cross(X, Y) = (0, -1, 0)`` — the wall is
extruded 8 m in the storey -Y direction.

4 – Window / Door placement (Model B)
--------------------------------------

When a ``PendingWindow`` (or ``PendingDoor``) with a ``component_graph`` is
added to a wall host, the opening and fill are built together.  The flow is:

1. The storey is the container for the wall.
2. ``model.add(pending_window, wall_handle)`` triggers Model B.
3. ``_build_model_b()`` in ``builders/door_window.py``:
   a. Reads the **wall's ObjectPlacement** from the IFC entity via
      ``plane_from_local_placement()``.
   b. Transforms ``pending.plane`` from storey coordinates to
      **wall-local coordinates** using ``plane.in_frame(wall_plane)``.
   c. Uses the transformed plane for the opening ObjectPlacement and
      component evaluation.

This transformation is **automatic**.  The user never needs to manually convert
between coordinate frames.

4.1 – Diagram

    User specifies:
        window.plane.origin = (2, 8, 1.5)   ← storey coords
    
    _build_model_b() does:
        wall_plane = extract from host_entity.ObjectPlacement
        local_plane = window.plane.in_frame(wall_plane)
        # local_plane.origin is now in wall-local coords
    
    Opening placed:
        opening.ObjectPlacement = local_placement(local_plane, relative_to=wall)
    
    Result in storey coords:
        opening at (2, 8, 1.5)   ← exactly what user specified

5 – PathPui: path-based windows
-------------------------------

The ``PathPui`` component accepts an optional ``path`` argument.  When a path
is provided it defines the window outline (any closed shape).

The path's **own plane** is **independent** of the ``PendingWindow.plane``:

- ``path.plane`` = the profile plane of the path geometry (e.g. the gable
  wall's profile plane).
- ``pending.plane`` (Model B) = the window's **insertion plane** in storey
  coordinates, used for the opening ObjectPlacement.

The path's plane is used inside the component to construct the opening solid
and the frame/glazing geometry.  The opening's placement (from
``pending.plane`` transformed to wall-local) positions this geometry in the
model.

6 – Internal helpers
--------------------

### 6.1 – ``Plane.in_frame(target_frame)``

Expresses a plane in another plane's local coordinate system:

    # wall_plane is in storey coords; window_plane is also in storey coords
    local = window_plane.in_frame(wall_plane)
    # local is now in wall-local coords

Implementation (in ``ifckit/geometry/primitives.py``):

    def in_frame(self, target_frame):
        return Plane(
            target_frame.to_local(self.origin),         # point: world → local
            target_frame.to_local_vector(self.x_axis),  # vector: world → local
            target_frame.to_local_vector(self.y_axis),
        )

### 6.2 – ``Plane.to_local_vector(world_vec)``

Converts a direction vector from world coordinates to the plane's local frame:

    local_vec = target.to_local_vector(world_vec)
    # local_vec.x = dot(world_vec, target.x_axis)
    # local_vec.y = dot(world_vec, target.y_axis)
    # local_vec.z = dot(world_vec, target.z_axis)

### 6.3 – ``plane_from_local_placement(ifc_placement)``

Reconstructs an ifckit ``Plane`` from an IfcLocalPlacement entity (handles
optional Axis/RefDirection with IFC defaults):

    from ifckit.builders._geom import plane_from_local_placement
    
    wall_plane = plane_from_local_placement(host_entity.ObjectPlacement)

7 – Examples
------------

### 7.1 – Simple wall at origin

    wall = PendingWallGraph(
        path=...,     # profile in world-XY plane
        plane=Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
    )
    
    win = PendingWindow(
        path=outer,
        plane=Plane(Vec(2, 0, 1), Vec(1, 0, 0), Vec(0, 0, 1)),
        component_graph="path_pui",
        ...
    )

Here wall-local and storey coordinates are identical, so the transformation
is a no-op.  The window ends up at ``(2, 0, 1)`` in both frames.

### 7.2 – Gable wall at Y = 8 (tiny_house)

    wall = PendingWallGraph(
        path=outer,
        plane=Plane(Vec(0, 8, 0), Vec(1, 0, 0), Vec(0, 0, 1)),
    )
    
    win = PendingWindow(
        path=outer,
        plane=Plane(Vec(1, 8, 1.5), Vec(1, 0, 0), Vec(0, 0, 1)),
        component_graph="path_pui",
        ...
    )

The window is specified at ``(1, 8, 1.5)`` in storey coords.  The code
automatically transforms this to wall-local ``(1, 1.5, 0)`` before creating
the opening placement.  The result is the same window position in storey
space: ``(1, 8, 1.5)``.

8 – Common pitfalls
-------------------

### 8.1 – Do NOT use path.plane as the insertion plane

The path's plane is the **profile plane** of the outline geometry.  It is not
the insertion plane.  Setting ``pending.plane = path.plane`` will place the
window incorrectly because the profile plane and the insertion plane serve
different purposes.

### 8.2 – Do NOT manually specify wall-local coordinates

Users should **never** compute wall-local positions.  Always use storey
coordinates.  The ``in_frame`` transformation happens automatically in
``_build_model_b()``.

### 8.3 – Negative Z-axis workaround

If you see a plane like ``Plane(..., Vec(0, 0, -1))`` used as a Y-axis, this
is a symptom of manually compensating for a coordinate mismatch.  With storey
coordinates and the automatic ``in_frame`` transformation, this workaround
is unnecessary.

9 – File locations
------------------

| File                                     | Content                                  |
|------------------------------------------|------------------------------------------|
| ``ifckit/geometry/primitives.py``        | ``Plane.in_frame()``, ``to_local_vector()`` |
| ``ifckit/builders/_geom.py``             | ``plane_from_local_placement()``         |
| ``ifckit/builders/door_window.py``       | ``_build_model_b()`` coordinate transform |
| ``docs/COORDINATE_SYSTEMS.md``           | This document                            |
