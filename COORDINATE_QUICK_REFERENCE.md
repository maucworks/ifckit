# IFCKit Coordinate System - Quick Reference

## The Golden Rule
**All pending elements use world coordinates. Solids always have identity positioning. Orientation is encoded in ObjectPlacement only.**

---

## Coordinate Transformation Pipeline (All Builders)

```
┌─────────────────────────────────────────────────────────────┐
│ User creates PendingWall (world-space plane + footprint)   │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ WallBuilder._create_geometry()                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Step 1: Extract footprint as 2D                        │ │
│ │   pts_2d = [(p.x, p.y) for p in pending.footprint]    │ │
│ │   (footprint already in plane's local XY)             │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Step 2: Create solid with IDENTITY positioning        │ │
│ │   position = axis2placement3d(0,0,0, Z=(0,0,1), X=...)│ │
│ │   solid = extrude_profile(profile, height, pos)       │ │
│ │   ⚠️  ALWAYS identity! Never use pending.plane here   │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Step 3: Create ObjectPlacement (orientation)           │ │
│ │   wall.ObjectPlacement = local_placement(              │ │
│ │       pending.plane,              # World plane        │ │
│ │       relative_to=container.ObjectPlacement  # Storey  │ │
│ │   )                                                    │ │
│ └─────────────────────────────────────────────────────────┘ │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Result: IfcWall                                             │
│ - Representation: solid with identity placement            │
│ - ObjectPlacement: encodes plane (origin + rotation)       │
│ - PlacementRelTo: storey.ObjectPlacement                   │
│ - World position = storey.placement ⊕ wall.placement       │
└─────────────────────────────────────────────────────────────┘
```

---

## Four Coordinate Frames

### 1. World Frame (Input)
- Where user defines pending elements
- `Plane(origin, x_axis, y_axis)` in world coords
- Footprint points in plane-local 2D

### 2. Element-Local Frame (Solid)
- Where geometry lives (profile 2D, extrusion)
- **Always identity positioning** (no rotation)
- Solid's IfcAxis2Placement3D is (0,0,0) with standard axes

### 3. ObjectPlacement Frame
- Where orientation is encoded
- `IfcLocalPlacement(RelativePlacement=IfcAxis2Placement3D)`
- Includes plane origin + rotation axes

### 4. Storey-Local Frame
- Some builders reference storey elevation
- Usually NOT explicitly shifted (world coords work fine)
- Important for clipping plane transformations

---

## Transformation Functions by Use Case

### ✅ Creating ObjectPlacement (Most Common)
```python
from ifckit.builders._geom import local_placement
placement = local_placement(f, pending.plane, relative_to=storey.ObjectPlacement)
```

### ✅ World to Local Projection (Clipping, Profile Extraction)
```python
# Project world point onto plane's local coords
local_pt = plane.to_local(world_point)
# Returns Vec with (x, y, z) in plane's frame
```

### ✅ Local to World Projection (Rare)
```python
# Transform local coords back to world
world_pt = plane.transform_point(local_coords)
```

### ✅ Adjusting for Storey Elevation (Clipping Only)
```python
from ifckit.builders._geom import shift_plane_elevation
local_elev = storey_elevation(container)
shifted = shift_plane_elevation(clip_plane, local_elev)
```

---

## Architecture Pattern: Three-Part Pattern

Every builder follows this pattern:

| Part | What | Where | Example |
|------|------|-------|---------|
| **Data** | Pending element with world-space plane | Input | `PendingWall(footprint, plane, height)` |
| **Transform** | Extract plane-local coords using `to_local()` or direct indexing | Builder method | `pts_2d = [(p.x, p.y) for p in footprint]` |
| **Place** | Encode orientation in ObjectPlacement via `local_placement()` | IFC entity | `wall.ObjectPlacement = local_placement(plane, relative_to=storey)` |

---

## Key Points by Builder Type

### WallBuilder & SlabBuilder
- Solid position: **identity**
- ObjectPlacement: **relative to storey**
- Footprint: **already in plane's local XY**

### OpeningBuilder
- Solid position: **identity + shifted Z** (centred on face)
- ObjectPlacement: **relative to host wall** (not storey)
- Anchor: applies offset to rectangle

### Door/Window (Model A)
- Solid position: **identity**
- ObjectPlacement: **relative to opening** (identity relative placement)
- Profile: anchored rectangle

### Door/Window (Model B - Component Graph)
- Solid position: **identity + z_offset** (per component)
- ObjectPlacement: determined by caller (door_window.py)
- Geometry: XY-plane centric, extrude -Z

### ExtrudedElementBuilder (Beam/Column)
- Solid position: **identity**
- ObjectPlacement: **computed cross-section frame** (not from world plane)
- Profile: orthogonal to extrusion direction

---

## Common Gotchas & How to Avoid

### ❌ Mistake 1: Using plane rotation in solid position
```python
# WRONG ❌
solid = extrude_profile(profile, depth, position=pending.plane)

# RIGHT ✅
solid = extrude_profile(profile, depth, position=identity_placement)
```

### ❌ Mistake 2: Forgetting relative_to in ObjectPlacement
```python
# WRONG ❌
wall.ObjectPlacement = local_placement(pending.plane)  # No parent!

# RIGHT ✅
wall.ObjectPlacement = local_placement(pending.plane, relative_to=container.ObjectPlacement)
```

### ❌ Mistake 3: Not handling anchor for openings
```python
# WRONG ❌
rect = [Vec(0,0), Vec(w,0), Vec(w,h), Vec(0,h)]  # Assumes origin at corner

# RIGHT ✅
dx, dy = anchor_offset(anchor, w, h)  # Shift by anchor offset
rect = [Vec(dx,dy), Vec(dx+w,dy), Vec(dx+w,dy+h), Vec(dx,dy+h)]
```

### ❌ Mistake 4: Trying to shift pending.plane to storey-local
```python
# WRONG ❌
local_plane = shift_plane_elevation(pending.plane, storey_elev)
# Breaks the whole system!

# RIGHT ✅
# Just use pending.plane directly
# The ObjectPlacement chain handles elevation
```

---

## Testing Coordinate System Changes

### Key Assertion
All tests should verify that solid positioning is identity:
```python
solid = ifc_file.by_type("IfcExtrudedAreaSolid")[0]
axis = solid.Position.Axis.DirectionRatios
assert list(axis) == pytest.approx([0.0, 0.0, 1.0])  # ALWAYS!
```

### Placement Chain
Verify that placement references are correct:
```python
# Wall should reference storey
assert wall.ObjectPlacement.PlacementRelTo == storey.ObjectPlacement

# Opening should reference wall (host)
assert opening.ObjectPlacement.PlacementRelTo == wall.ObjectPlacement

# Fill should reference opening
assert fill.ObjectPlacement.PlacementRelTo == opening.ObjectPlacement
```

---

## File Navigation Shortcuts

**Need to**... | **Go to**...
---|---
Add a new builder | `/ifckit/builders/<builder_name>.py` (copy wall.py pattern)
Fix coordinate math | `/ifckit/geometry/primitives.py` (Plane class)
Understand transformation | `/ifckit/builders/_geom.py` (local_placement, to_local, etc.)
Debug wall placement | `/ifckit/builders/wall.py` lines 39-93
Debug opening geometry | `/ifckit/builders/opening.py` lines 48-143
Debug clipping | `/ifckit/builders/extruded.py` lines 186-244
See real examples | `/tests/builders/test_wall_builder.py`

---

## Mathematical Foundation

### Plane.to_local() - Orthogonal Projection
```
Given: plane with origin O, x_axis X, y_axis Y, z_axis Z (= X × Y)
Point in plane's local coords: (u, v, w) = 
  u = (P - O) · X
  v = (P - O) · Y
  w = (P - O) · Z
```

### Plane.transform_point() - Inverse
```
Given: local coords (u, v, w)
World point P = O + u*X + v*Y + w*Z
```

### local_placement() - IFC Encoding
```
IfcLocalPlacement(
  PlacementRelTo=parent,           # Reference frame
  RelativePlacement=IfcAxis2Placement3D(
    Location=(O.x, O.y, O.z),     # Plane origin
    Axis=(Z.x, Z.y, Z.z),         # Z direction (normal)
    RefDirection=(X.x, X.y, X.z)  # X direction (reference)
  )
)
```

---

## Design Rationale

### Why Identity Solid Positioning?
Prevents **double rotation** - if solid Position had plane rotation AND ObjectPlacement had plane rotation, geometry would rotate twice.

### Why World Coordinates for Input?
Users think in world coords. Converting to storey-local at input time would be confusing.

### Why ObjectPlacement.PlacementRelTo?
Implements **hierarchical transforms** - storey's ObjectPlacement → container's ObjectPlacement → element's world position.

### Why No Explicit Storey Elevation Shift?
The placement chain handles it automatically. Storey elevation is encoded in storey.ObjectPlacement.RelativePlacement.Location.

---

## Related Documentation
- Full analysis: `COORDINATE_SYSTEM_ANALYSIS.md` (this directory)
- Architecture overview: `ARCHITECTURE.md`
- Contribution guidelines: `AGENTS.md`
- See docstrings in `/ifckit/builders/_geom.py` and `/ifckit/geometry/primitives.py`

