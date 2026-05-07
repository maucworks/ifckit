# Bonsai Compatibility Issue: Pure-Pythonic IFC Generation

## Problem

IFC files generated using `ifcopenshell.file(schema='IFC4')` with manual entity creation (pure-pythonic) hang Bonsai (Blender addon) on import. The Blender process shows 0.1% CPU usage (stuck/idle).

## What Works

- **web-ifc** renders the geometry correctly
- **IfcOpenShell Python** (`geom.create_shape()`) converts geometry instantly
- **Blender Python console** importing via `bpy.data.meshes.new()` works fine
- **Reference files** (e.g., hello-wall.ifc generated via JSON builder) import correctly in Bonsai

## Test Files

All of the following hang Bonsai:
- `test_sectioned_spine_basic.ifc` — IfcPolygonalFaceSet box
- `test_triangulated.ifc` — IfcTriangulatedFaceSet box
- `test_spatial_structure.ifc` — with Site/Building/Storey hierarchy
- `test_placement.ifc` — with ObjectPlacement on all elements
- `test_extruded.ifc` — IfcExtrudedAreaSolid (standard geometry type)
- `test_ref_geom.ifc` — geometry copied from reference file into our structure

## Suspected Cause

The difference between working files (JSON builder via `IfcModel`) and hanging files (manual entity creation) is likely in how `ifcopenshell.api.run()` sets up internal relationships/attributes that Bonsai's import code depends on.

When using the API layer (`ifcopenshell.api.run("root.create_entity", ...)`), ifcopenshell may:
- Set up internal caches or indices
- Create implicit relationships
- Populate derived attributes
- Set flags that Bonsai checks during import

Manual entity creation via `model.create_entity()` bypasses this API layer and may produce structurally valid but "incomplete" IFC files from Bonsai's perspective.

## Workaround

For now, geometry can be viewed via:
1. **web-ifc** (online viewer)
2. **Blender Python console** (bypass Bonsai IFC import)
3. **JSON builder pipeline** (`build_from_json()` with `IfcModel`)

## Related Issues

- **IfcArbitraryProfileDefWithVoids bug**: When Bonsai rebuilds geometry (e.g., TAB cycling through compound subobjects), holes in `IfcArbitraryProfileDefWithVoids` disappear. This is a separate Bonsai bug tracked at: https://github.com/IfcOpenShell/IfcOpenShell/issues/8043

## Resolution Path

To make pure-pythonic IFC files Bonsai-compatible, we likely need to:
1. Use `ifcopenshell.api.run()` for all entity creation instead of `model.create_entity()`
2. Or find the specific missing API-side setup and replicate it manually
3. Or update Bonsai to be more tolerant of manually-created IFC files

## Files

- `output/test_*.ifc` — hanging test files
- `output/import_to_blender.py` — Blender Python script for direct mesh import

## Additional Finding: IfcArbitraryProfileDefWithVoids Not Closed

**Observation**: `IfcArbitraryProfileDefWithVoids` profiles (used for window openings with holes) appear as **not-closed** in Bonsai's geometry viewer, even though the `IfcPolyline` has `First == Last` point in the IFC file.

**Verification**:
- IFC file: `OuterCurve.Points[0] == OuterCurve.Points[-1]` ✓ (closed)
- Bonsai display: Profile shown as open curve ✗

**Workaround**: Manually close the profile curves in Blender's edit mode.

**Impact**: This affects all window/door components that use `IfcArbitraryProfileDefWithVoids` for frame-with-hole geometry.
