# IFCKit Coordinate System Research Summary

## Overview
IFCKit uses a consistent coordinate transformation pattern across all builders. The key insight is that **all pending elements are defined in world coordinates, and the local placement (ObjectPlacement) encodes position and orientation relative to the storey**.

---

## 1. Wall Positioning Relative to Storey

### PendingWall Structure
- **File**: `ifckit/elements/building.py`
- **Key Fields**:
  - `footprint`: List[Vec] - closed polygon in plane's local XY coordinates
  - `plane`: Plane - world-space placement (origin + x_axis + y_axis)
  - `height`: float - extrusion along plane.z_axis

### WallBuilder Coordinate Pipeline
- **File**: `ifckit/builders/wall.py`

```
PendingWall (world-space plane) 
    ↓
Extract footprint as 2D (x, y) coordinates from plane's local XY
    ↓
Create IfcExtrudedAreaSolid with:
  - Solid position: IDENTITY (0,0,0) with axes (1,0,0), (0,0,1), (1,0,0)
  - Extrusion direction: (0, 0, 1) in local frame
  - Extrusion depth: pending.height
    ↓
wall.ObjectPlacement = local_placement(ifc_file, pending.plane, relative_to=container.ObjectPlacement)
    ↓
Result: Wall's world position comes from ObjectPlacement chain
```

**Critical Pattern**: The solid's extrusion is ALWAYS identity-positioned along local Z. The plane orientation is encoded **solely in ObjectPlacement**, avoiding double rotation.

### Storey Integration
- Wall is assigned to storey via `spatial.assign_container()`
- Storey's ObjectPlacement elevation is captured via `storey_elevation()` function
- Walls reference storey's placement: `ObjectPlacement.PlacementRelTo = storey.ObjectPlacement`

---

## 2. Opening Positioning (IfcOpeningElement)

### PendingOpening Structure
- **File**: `ifckit/elements/opening.py`
- **Key Fields**:
  - `plane`: Plane - world-space insert plane (origin = insert point at bottom-left corner)
  - `width`, `height`: dimensions (metres)
  - `anchor`: position of plane.origin relative to opening bbox (default "sw" = southwest/bottom-left)
  - `opening_depth`: thickness penetration (default 10m)

### Opening Geometry Convention
Per spec (IFC + Bonsai compatibility):
- Plane local X-axis = width direction (horizontal)
- Plane local Y-axis = height direction (UP)
- Plane local Z-axis = outward normal (through wall body)

### build_opening() Pipeline
- **File**: `ifckit/builders/opening.py` lines 48-143

```
PendingOpening (with world-space plane)
    ↓
Calculate profile rectangle using anchor_offset()
    → Shift profile by (dx, dy) so plane.origin is at requested anchor
    ↓
Create IfcExtrudedAreaSolid:
  - Profile: 2D rectangle in local XY (anchored by dx, dy)
  - Solid Position: IDENTITY with:
      - Origin shifted by -depth/2 along local Z (centres on wall face)
      - Axes identity (1,0,0), (0,0,1)
  - Depth: opening_depth
    ↓
opening.ObjectPlacement = local_placement(
    ifc_file, 
    pending.plane, 
    relative_to=host_entity.ObjectPlacement
)
    ↓
IfcRelVoidsElement links: host → opening (NOT spatial containment)
```

**Key Insight**: Opening is placed relative to **host wall**, not storey.

---

## 3. Window/Door Positioning (Fill Elements)

### PendingWindow / PendingDoor Structure
- **File**: `ifckit/elements/opening.py` (lines 180+, 309+)
- **Key Fields for Model A**:
  - `overall_width`, `overall_height`
  - `operation_type` / `window_type`
  - No explicit plane (positioned relative to opening)
  
- **Key Fields for Model B** (graph-based):
  - `plane`: Plane - explicit insert plane for component graph
  - `component_graph`: preset name (e.g., "fixed_casement")

### build_window() / build_door() Pipeline (Model A)
- **File**: `ifckit/builders/door_window.py` lines 241-395

```
PendingWindow (no explicit plane)
    ↓
Create fill solid geometry:
  - Identity placement: axis2placement3d(Vec(0,0,0), Vec(0,0,1), Vec(1,0,0))
  - Profile: 2D rectangle with anchor offset (dx, dy)
  - For windows with lining:
      - Outer solid: full width × height extruded by lining_depth
      - Inner void: inset by lining_thickness on all sides
      - Boolean difference → hollow frame
    ↓
fill.ObjectPlacement = _relative_to_opening(opening.ObjectPlacement)
    → Creates IfcLocalPlacement with identity relative placement
    → PlacementRelTo = opening.ObjectPlacement
    ↓
Spatial containment: fill assigned to storey (not opening)
    ↓
IfcRelFillsElement links: opening → fill
```

**Key Pattern**: 
- Fill inherits opening's local frame via identity relative placement
- Fill profile (x, y) corresponds to opening's local coordinates
- Anchor shift applied to profile so fill sits flush inside void

---

## 4. Coordinate Transformations & Utilities

### Core Transformation Functions

#### a) `local_placement()` - **Most Used**
- **File**: `ifckit/builders/_geom.py` lines 74-81
- **Purpose**: Convert pending element's world-space Plane to IfcLocalPlacement
```python
def local_placement(f, plane: Plane, relative_to=None) -> IfcLocalPlacement:
    ax = axis2placement3d(f, plane.origin, plane.z_axis, plane.x_axis)
    return f.create_entity(
        "IfcLocalPlacement", 
        PlacementRelTo=relative_to,  # Relative to storey or host
        RelativePlacement=ax
    )
```

#### b) `Plane.to_local()` - **World to Local Conversion**
- **File**: `ifckit/geometry/primitives.py` lines 360-363
- **Purpose**: Express a world point in plane's local coordinates
```python
def to_local(self, world_pt: Vec) -> Vec:
    """Express world point in local frame coordinates."""
    d = world_pt - self.origin
    return Vec(
        d @ self.x_axis,  # project onto x_axis
        d @ self.y_axis,  # project onto y_axis
        d @ self.z_axis   # project onto z_axis
    )
```

#### c) `Plane.transform_point()` - **Local to World**
- **File**: `ifckit/geometry/primitives.py` lines 347-349
- **Purpose**: Convert local coords to world coords
```python
def transform_point(self, local: Vec) -> Vec:
    return (self.origin + 
            self.x_axis * local.x + 
            self.y_axis * local.y + 
            self.z_axis * local.z)
```

#### d) `shift_plane_elevation()` - **Storey Elevation Adjustment**
- **File**: `ifckit/builders/_geom.py` lines 84-93
- **Purpose**: Convert world-space plane to storey-local coords
```python
def shift_plane_elevation(plane: Plane, elev: float) -> Plane:
    """Shift plane origin by -elev in Z (for storey-local coords)."""
    local_origin = Vec(plane.origin.x, plane.origin.y, plane.origin.z - elev)
    return plane.__class__(local_origin, plane.x_axis, plane.y_axis)
```
- **Usage**: Rarely used currently - most builders keep everything in world space

#### e) `storey_elevation()` - **Extract Storey Z**
- **File**: `ifckit/builders/_geom.py` lines 267-277
- **Purpose**: Get Z-elevation from storey's ObjectPlacement
```python
def storey_elevation(container) -> float:
    try:
        coords = container.ObjectPlacement.RelativePlacement.Location.Coordinates
        return float(coords[2]) if len(coords) > 2 else 0.0
    except AttributeError:
        return 0.0
```

#### f) `project_profile_to_plane()` - **3D Points to Plane 2D**
- **File**: `ifckit/builders/_geom.py` lines 214-225
- **Purpose**: Project world 3D points onto a plane's local 2D coords
```python
def project_profile_to_plane(points: List[Vec], plane: Plane) -> List[tuple]:
    result = []
    for p in points:
        local = plane.to_local(p)
        result.append((local.x, local.y))
    return result
```

### Clipping Plane Transformation (Critical Pattern)
- **File**: `ifckit/builders/extruded.py` lines 186-244
- **Function**: `_apply_clip()`

```python
def _apply_clip(ifc_file, solid, clip_plane: Plane, op_plane: Plane, elev: float):
    """Transform clip plane from world to ObjectPlacement local space."""
    
    # Step 1: Shift clip plane to storey-local space
    world_origin = Vec(
        clip_plane.origin.x,
        clip_plane.origin.y,
        clip_plane.origin.z - elev  # Subtract storey elevation
    )
    
    # Step 2: Transform to ObjectPlacement local coordinates
    local_origin = op_plane.to_local(world_origin)
    local_normal = Vec(
        clip_plane.z_axis @ op_plane.x_axis,  # dot product
        clip_plane.z_axis @ op_plane.y_axis,
        clip_plane.z_axis @ op_plane.z_axis
    )
    
    # Step 3: Create IfcHalfSpaceSolid in local coords
    ...
```

**Key Insight**: Clip planes are defined in world space and transformed into the element's ObjectPlacement local frame.

---

## 5. Wall Graph Coordinate Handling

### WallGraphBuilder Pattern
- **File**: `ifckit/builders/wall_graph.py` lines 156-220

Two modes:
1. **Closed path mode**: Offset centerline, create annular profile
2. **Open path mode**: Sample path, offset left/right, create footprint

**Coordinate Flow**:
```
PendingWallGraph (path in world space)
    ↓
Extract pending.plane for placement
    ↓
Compute footprint in plane's local XY:
    local_footprint = [(plane.to_local(v).x, plane.to_local(v).y) for v in footprint]
    ↓
Create extrusion with identity solid position
    ↓
wall.ObjectPlacement = local_placement(pending.plane, relative_to=storey.ObjectPlacement)
```

---

## 6. Component Graph (Model B) Coordinate System

### evaluate_component_graph()
- **File**: `ifckit/builders/component_graph.py` lines 440-512

```python
def evaluate_component_graph(
    preset_name: str,
    ifc_file,
    context,
    params,  # Must include "w" (width) and "h" (height)
    plane=None,  # Reference plane for transformations
    path=None,   # Optional closed Path
):
    """Evaluate JSON/Python component graph."""
```

### Key Assumptions
- All profiles created in XY plane (local to component)
- Extrusion direction: -Z (backward through wall) for door/window linings
- z_offset in JSON: positive = distance into wall from outer face
- **Plane is provided but geometry is evaluated in local XY coords**
- Plane transformations happen at component build level, not in graph evaluation

### Convention: Extrusion & z_offset
- **File**: `ifckit/builders/component_graph.py` lines 386-409
```python
# Extrusion ALWAYS in -Z (backward through wall)
depth = eval_expr(node.get("depth", 0.1), resolved)
z_offset_raw = node.get("z_offset", 0)
z_offset = -z_offset_raw  # NEGATE: positive JSON → -Z direction

placement = axis2placement3d(ifc_file, Vec(0, 0, z_offset), Vec(0, 0, 1), Vec(1, 0, 0))

solid = extrude_profile(
    ifc_file,
    ifc_profile,
    depth,
    position=placement,
    extrude_direction=(0.0, 0.0, -1.0)  # Always -Z
)
```

---

## 7. Current Coordinate System Assumptions

### Global Assumptions (All Builders)
1. **Pending elements are world-space**: All Plane, Vec coordinates are in world frame
2. **Identity solid positioning**: Solids always have identity IfcAxis2Placement3D
3. **Orientation in ObjectPlacement only**: Plane rotation is encoded in ObjectPlacement, not solid
4. **Storey contains elements**: Elements reference storey via ObjectPlacement.PlacementRelTo
5. **No explicit storey elevation shift**: World coords are used directly (storey elevation handled by placement chain)

### Per-Builder Patterns

| Builder | Solid Position | ObjectPlacement | Notes |
|---------|---|---|---|
| **WallBuilder** | Identity | local_placement(pending.plane, relative_to=storey) | Footprint extracted as 2D from plane |
| **SlabBuilder** | Identity | local_placement(pending.plane, relative_to=storey) | Same as wall |
| **WallGraphBuilder** | Identity | local_placement(pending.plane, relative_to=storey) | Path converted to local coords |
| **OpeningBuilder** | Identity -depth/2 Z shift | local_placement(pending.plane, relative_to=host) | Relative to wall, not storey |
| **build_door/window** | Identity | _relative_to_opening() = identity LocalPlacement(PlacementRelTo=opening) | Fill inherits opening frame |
| **ExtrudedElementBuilder** | Identity | local_placement(op_plane, relative_to=storey) | Cross-section frame computed from axis + profile |
| **Component Graph** | Identity + z_offset | Placed by caller (door_window.py) | Geometry in local XY, extrude -Z |

---

## 8. Where Transformations Happen

### Transformations Occur In:
1. **Pending → Builder**: `local_placement()` converts pending.plane to IfcLocalPlacement
2. **Clipping**: `_apply_clip()` transforms world clip planes to element-local coords
3. **Profile Extraction**: `plane.to_local()` used to extract 2D coords from world points
4. **Component Graphs**: Implicit local frame (no explicit plane transforms in JSON evaluation)

### Transformations DON'T Occur In:
- Solid geometry (always identity positioning)
- Profile creation (already in local coords)
- Extrusion setup (uses identity axes)

---

## 9. Key Files Involved in Coordinate Pipeline

### Coordinate Math
- `/ifckit/geometry/primitives.py` - Vec, Plane (to_local, transform_point, etc.)
- `/ifckit/geometry/transform.py` - 4×4 Transform matrices (less used)

### IFC Geometry Creation
- `/ifckit/builders/_geom.py` - axis2placement3d, local_placement, shift_plane_elevation
- `/ifckit/builders/_geom.py` - storey_elevation, project_profile_to_plane

### Builder Implementations
- `/ifckit/builders/wall.py` - WallBuilder (lines 39-93)
- `/ifckit/builders/opening.py` - build_opening, build_opening_from_solids
- `/ifckit/builders/door_window.py` - build_door, build_window (lines 241-395)
- `/ifckit/builders/extruded.py` - _apply_clip (lines 186-244)
- `/ifckit/builders/wall_graph.py` - WallGraphBuilder (lines 101-220)
- `/ifckit/builders/component_graph.py` - evaluate_component_graph (lines 440-512)

### Element Definitions
- `/ifckit/elements/building.py` - PendingWall, PendingSlab
- `/ifckit/elements/opening.py` - PendingOpening, PendingWindow, PendingDoor

---

## 10. Summary of Coordinate Assumptions

### Current Design
- **All pending elements use world coordinates**
- **Placement hierarchy**: Element → Storey → Building → Site
- **Solid geometry uses identity positioning** to avoid double rotation
- **Orientation encoded in ObjectPlacement only**
- **Storey elevation handled by placement chain**, not explicit shifting

### Implications
- Simple, consistent pattern across all builders
- No need to convert plane coords to storey-local (world coords work directly)
- Opening placed relative to wall, fill placed relative to opening
- Clipping planes transformed to element-local coords on demand

### Potential Issues (Not Currently Addressed)
- Component graphs assume opening local XY, but provide limited plane access
- Clip plane transformation could be more documented
- Storey elevation getter exists but not widely used (coord system doesn't require it)

---

## 11. Testing & Validation

### Test Files Covering Coordinates
- `/tests/builders/test_wall_builder.py` - Wall placement + non-XY planes
- `/tests/builders/test_opening_builder.py` - Opening placement relative to wall
- `/tests/test_model_doors_windows.py` - Fill element integration

### Key Test Pattern (test_wall_builder.py:87-94)
```python
def test_xz_plane_solid_position_is_identity():
    """Solid extrusion axis must be (0,0,1) — not world plane.z_axis."""
    footprint = [Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 0, 0.3), Vec(0, 0, 0.3)]
    pending = PendingWall(footprint, Plane.world_xz(), 3.0)
    WallBuilder().build(...)
    solid = ifc_file.by_type("IfcExtrudedAreaSolid")[0]
    axis = solid.Position.Axis.DirectionRatios
    assert list(axis) == pytest.approx([0.0, 0.0, 1.0])  # Always identity!
```

---

## References

### Code Locations
- Core coordinate functions: `ifckit/builders/_geom.py` (lines 59-94, 214-277)
- Plane implementation: `ifckit/geometry/primitives.py` (lines 243-410)
- Wall building: `ifckit/builders/wall.py` (lines 39-93)
- Opening building: `ifckit/builders/opening.py` (lines 48-203)
- Door/window building: `ifckit/builders/door_window.py` (lines 241-414)
- Clipping: `ifckit/builders/extruded.py` (lines 186-244)
- Component graphs: `ifckit/builders/component_graph.py` (lines 440-588)

### Documentation
- See AGENTS.md for contribution guidelines
- See ARCHITECTURE.md for system overview
- See inline docstrings in _geom.py and primitives.py

