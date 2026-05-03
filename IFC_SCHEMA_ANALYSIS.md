# IFC Schema Analysis for ifckit Codebase Architecture

## Executive Summary

This analysis examines the differences between **IFC2X3**, **IFC4**, and **IFC4X3** schemas relevant to the ifckit codebase. The key finding is that **ifckit deliberately supports only IFC4 and IFC4X3**, explicitly excluding IFC2X3 due to API incompatibilities.

---

## 1. Entity Differences

### 1.1 Entity Availability Matrix

| Entity | IFC2X3 | IFC4 | IFC4X3 | Notes |
|--------|---------|------|---------|-------|
| **IfcWall** | YES | YES | YES | Core building element |
| **IfcSlab** | YES | YES | YES | Core building element |
| **IfcBeam** | YES | YES | YES | Core building element |
| **IfcColumn** | YES | YES | YES | Core building element |
| **IfcBuildingStorey** | YES | YES | YES | Spatial structure |
| **IfcBuilding** | YES | YES | YES | Spatial structure |
| **IfcSite** | YES | YES | YES | Spatial structure |
| **IfcProject** | YES | YES | YES | Root entity |
| **IfcBridge** | NO | NO | **YES** | New in IFC4X3 |
| **IfcAlignment** | NO | NO | **YES** | New in IFC4X3 |
| **IfcBridgePart** | NO | NO | **YES** | New in IFC4X3 |
| **IfcCivilElement** | NO | YES | YES | New in IFC4 |
| **IfcRail** | NO | NO | **YES** | New in IFC4X3 |
| **IfcRailway** | NO | NO | **YES** | New in IFC4X3 |
| **IfcRoad** | NO | NO | **YES** | New in IFC4X3 |
| **IfcFacility** | NO | NO | **YES** | New in IFC4X3 |
| **IfcGeographicElement** | NO | YES | YES | New in IFC4 |

### 1.2 Key Findings

**Entities in IFC2X3 but NOT in IFC4/IFC4X3:** None significant for ifckit

**Entities in IFC4 but NOT in IFC2X3:** 
- IfcCivilElement
- IfcGeographicElement

**Entities in IFC4X3 but NOT in earlier versions:**
- IfcBridge, IfcBridgePart (infrastructure)
- IfcAlignment (enhanced for infrastructure)
- IfcRail, IfcRailway, IfcRoad (transport infrastructure)
- IfcFacility, IfcFacilityPart (new spatial structure)

### 1.3 `ifc_file.by_type()` Behavior

**Critical Finding for IFC4X3:**
```python
# IFC4: Works
file.by_type('IfcBuildingElement')  # Returns building elements

# IFC4X3: FAILS with error
file.by_type('IfcBuildingElement')  # Entity with name 'IfcBuildingElement' not found
```

**Explanation:** IFC4X3 removed some abstract parent types like `IfcBuildingElement`. Use `IfcElement` or `IfcProduct` instead.

**Consistent behavior across all schemas:**
- `by_type('IfcWall')` - Returns entity instances
- `by_type('IfcElement')` - Returns all elements (works in all schemas)
- `by_type('IfcProduct')` - Returns all products (works in all schemas)
- `by_type('IfcRoot')` - Returns all root entities

---

## 2. API Compatibility (`ifcopenshell.api.run()`)

### 2.1 Test Results

| API Call | IFC2X3 | IFC4 | IFC4X3 |
|----------|---------|------|---------|
| `root.create_entity` | **BROKEN** | OK | OK |
| `aggregate.assign_object` | Untested* | OK | OK |
| `spatial.assign_container` | Untested* | OK | OK |
| `unit.add_si_unit` | OK | OK | OK |
| `context.add_context` | **BROKEN** | OK | OK |

*IFC2X3 fails at `root.create_entity`, so subsequent calls weren't tested.

### 2.2 IFC2X3 API Issues

**Problem:** `ifcopenshell.api.run("root.create_entity", ...)` fails with:
```
Please create a user to continue. See the owner.create_owner_history docs...
```

**Root Cause:** IFC2X3 requires `IfcOwnerHistory` to be set up before creating entities via the API. IFC4+ handles this automatically.

**Workaround (if supporting IFC2X3):**
```python
# Must create OwnerHistory manually for IFC2X3
person = file.create_entity("IfcPerson", FamilyName="Developer")
organization = file.create_entity("IfcOrganization", Name="ifckit")
# ... create owner history ...
```

### 2.3 ifckit's Approach

ifckit uses `ifcopenshell.api.run()` for:
- Entity creation (`root.create_entity`)
- Spatial containment (`spatial.assign_container`)
- Aggregation (`aggregate.assign_object`)

This works seamlessly for **IFC4 and IFC4X3**, but would require a compatibility layer for IFC2X3.

---

## 3. Property Sets

### 3.1 Property Set Entity Comparison

| Aspect | IFC2X3 | IFC4 | IFC4X3 |
|--------|---------|------|---------|
| `IfcPropertySet` | YES | YES | YES |
| `IfcPropertySet.HasProperties` | YES | YES | YES |
| `IfcElementQuantity` | YES | YES | YES |
| `IfcElementQuantity.Quantities` | YES | YES | YES |
| `IfcPropertySingleValue` | YES | YES | YES |

### 3.2 Key Findings

**No differences found:** Property sets work identically across all three schemas.

- `IfcPropertySet` - Same attributes and behavior
- `IfcElementQuantity` - Same structure (note: `IfcQuantitySet` was the abstract type in early IFC)
- Property value types (`IfcPropertySingleValue`, etc.) - Identical

**ifckit Impact:** Property set implementation (if added) would work across IFC4 and IFC4X3 without schema-specific code.

---

## 4. Spatial Hierarchy Differences

### 4.1 IFC4 Spatial Structure (Buildings)

```
IfcProject
└─ IfcSite
   └─ IfcBuilding
      └─ IfcBuildingStorey
         └─ IfcWall, IfcBeam, IfcSlab, etc.
```

### 4.2 IFC4X3 Spatial Structure (Buildings + Infrastructure)

```
IfcProject
└─ IfcSite
   ├─ IfcBuilding        (traditional buildings)
   │  └─ IfcBuildingStorey
   │     └─ IfcWall, IfcBeam, etc.
   ├─ IfcBridge          (NEW - infrastructure)
   │  └─ IfcBridgePart (DECK, SUBSTRUCTURE, ABUTMENT, PIER)
   ├─ IfcRailway         (NEW - rail infrastructure)
   ├─ IfcRoad            (NEW - road infrastructure)
   └─ IfcAlignment       (NEW - horizontal alignment)
```

### 4.3 ifckit Implementation

**Current support (from `ifckit/model.py`):**

```python
class IfcModel:
    # IFC4 methods
    add_site() → IfcSite
    add_building() → IfcBuilding
    add_storey() → IfcBuildingStorey
    
    # IFC4X3 methods (require schema=IfcSchema.IFC4X3)
    add_bridge() → IfcBridge
    add_bridge_part() → IfcBridgePart
    add_alignment() → IfcAlignment
```

**Schema validation:**
```python
def _require_schema(self, required: IfcSchema, method: str) -> None:
    if self.schema != required:
        raise ValueError(f"IfcModel.{method}() requires schema {required.value}")
```

---

## 5. Geometry Differences

### 5.1 Geometry Entity Comparison

| Entity | IFC2X3 | IFC4 | IFC4X3 | Notes |
|--------|---------|------|---------|-------|
| `IfcExtrudedAreaSolid` | YES | YES | YES | Identical attributes |
| `IfcRevolvedAreaSolid` | YES | YES | YES | Identical attributes |
| `IfcShapeRepresentation` | YES | YES | YES | Same structure |
| `IfcProductDefinitionShape` | YES | YES | YES | Same structure |
| `IfcAxis2Placement3D` | YES | YES | YES | Same structure |

### 5.2 Key Findings

**No schema-specific differences:** Core geometry entities are identical across all versions.

**ifckit approach (from `ifckit/builders/_geom.py`):**
- Uses low-level `ifcopenshell.file.create_entity()` for geometry
- This is **schema-agnostic** - works identically for IFC4 and IFC4X3
- No schema checks needed in builder code

**Example (from `extruded.py`):**
```python
def extrude_profile(ifc_file, profile, depth, position=None, extrude_direction=(0,0,1)):
    return ifc_file.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=position,
        ExtrudedDirection=dir3(ifc_file, *extrude_direction),
        Depth=float(depth),
    )
```

---

## 6. PredefinedType Handling

### 6.1 PredefinedType Attribute Availability

| Entity | IFC2X3 | IFC4 | IFC4X3 |
|--------|---------|------|---------|
| IfcWall | **NO** | YES | YES |
| IfcBeam | **NO** | YES | YES |
| IfcColumn | **NO** | YES | YES |
| IfcSlab | YES | YES | YES |
| IfcBuilding | **NO** | YES | YES |

**Note:** IFC2X3 has inconsistent PredefinedType support - some entities have it, most don't.

### 6.2 ifckit Current Implementation

**Finding:** ifckit builders do NOT set PredefinedType:

```python
# WallBuilder (ifckit/builders/wall.py)
wall = ifcopenshell.api.run(
    "root.create_entity", ifc_file, ifc_class="IfcWall", name=pending.name
)
# Note: No PredefinedType set
```

**Impact:**
- IFC4/IFC4X3: Entities default to `PredefinedType = None` (often means NOTDEFINED)
- If IFC2X3 support added: PredefinedType would be silently ignored (attribute doesn't exist)

---

## 7. ifckit Codebase Architecture Summary

### 7.1 Current Schema Support

**From `ifckit/schema/__init__.py`:**
```python
class IfcSchema(enum.Enum):
    """Supported IFC schema versions."""
    IFC4 = "IFC4"
    IFC4X3 = "IFC4X3"
    # IFC2X3 is NOT included
```

### 7.2 Builder Architecture

**Key files:**
- `ifckit/builders/base.py` - `IIfcBuilder` protocol, `BaseBuilder` abstract class
- `ifckit/builders/wall.py` - `WallBuilder` for IfcWall
- `ifckit/builders/extruded.py` - `ExtrudedElementBuilder` for IfcBeam, IfcColumn
- `ifckit/builders/_geom.py` - Low-level geometry helpers

**Schema handling:**
- Builders use `ifcopenshell.api.run()` for entity creation (high-level)
- Geometry uses `ifc_file.create_entity()` (low-level, schema-agnostic)
- No schema-specific conditional code in builders

### 7.3 Model Architecture

**From `ifckit/model.py`:**
- `IfcModel` class manages spatial hierarchy
- Schema set at creation time: `IfcModel(schema=IfcSchema.IFC4)`
- Schema-aware methods via `_require_schema()` validation
- IFC4X3 methods fail explicitly if used with IFC4 schema

---

## 8. Recommendations for ifckit

### 8.1 Keep Current Approach (Recommended)

**Maintain IFC4 + IFC4X3 only:**
- IFC2X3 has significant API incompatibilities
- Most modern workflows use IFC4 or IFC4X3
- Reduces testing burden and code complexity

### 8.2 If Adding IFC2X3 Support in Future

1. Add `IfcSchema.IFC2X3 = "IFC2X3"` to enum
2. Create compatibility layer for `ifcopenshell.api`:
   - Auto-create `IfcOwnerHistory` for IFC2X3
   - Handle missing `PredefinedType` attributes
3. Test all builders with IFC2X3 schema
4. Add schema checks in builders if needed

### 8.3 IFC4X3 Infrastructure Enhancements

Consider adding builders for:
- `RailBuilder` → IfcRail
- `RoadBuilder` → IfcRoad
- Enhanced `AlignmentBuilder` (currently basic)

### 8.4 PredefinedType Handling

Consider setting PredefinedType for IFC4/IFC4X3 compliance:
```python
# In builders, after entity creation:
entity.PredefinedType = "STANDARD"  # or appropriate value
```

### 8.5 Testing Strategy

Add schema regression tests:
- Test all builders with both IFC4 and IFC4X3
- Verify `by_type()` works with appropriate parent classes
- Test spatial hierarchy creation for both schemas

---

## 9. Quick Reference: Key Differences at a Glance

```
┌─────────────────────────┬────────────┬────────────┬────────────┐
│ Feature                 │ IFC2X3     │ IFC4       │ IFC4X3     │
├─────────────────────────┼────────────┼────────────┼────────────┤
│ IfcWall, IfcBeam        │ YES        │ YES        │ YES        │
│ IfcBridge               │ NO         │ NO         │ YES        │
│ IfcAlignment            │ NO         │ NO         │ YES        │
│ PredefinedType support  │ Limited    │ Full       │ Full       │
│ ifcopenshell.api works  │ BROKEN     │ YES        │ YES        │
│ ifckit support          │ NONE       │ YES        │ YES        │
│ IfcBuildingElement type │ YES        │ YES        │ NO*        │
└─────────────────────────┴────────────┴────────────┴────────────┘

*Removed in IFC4X3 - use IfcElement instead
```

---

## Appendix A: Test Scripts Used

The analysis was performed using Python scripts that:
1. Created ifcopenshell files with different schemas
2. Tested entity creation and availability
3. Verified API compatibility
4. Checked `by_type()` behavior
5. Examined property set and geometry handling

All tests confirm that **ifckit's decision to support only IFC4 and IFC4X3 is well-founded** and avoids significant compatibility issues with IFC2X3.

---

**Analysis Date:** May 2026  
**ifcopenshell Version:** (installed in `/opt/miniconda3/envs/standard`)  
**Test Environment:** macOS Darwin, Python 3.12
