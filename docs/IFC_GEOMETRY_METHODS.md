# IFC Generatieve Geometrie Methodes - Bevindingen

## Probleem
Bonsai viewer bug: na TAB cycling door compound subobjects verdwijnt de hole in `IfcArbitraryProfileDefWithVoids` en wordt een bounding box getoond.

## Schema Support Matrix

| Methode | IFC2X3 | IFC4 | IFC4X3_ADD2 |
|---------|--------|------|-------------|
| `IfcExtrudedAreaSolid` | ✅ | ✅ | ✅ |
| `IfcRevolvedAreaSolid` | ✅ | ✅ | ✅ |
| `IfcBooleanResult` | ✅ | ✅ | ✅ |
| `IfcFacetedBrepWithVoids` | ✅ | ✅ | ✅ |
| `IfcTriangulatedFaceSet` | ❌ | ✅ | ✅ |
| `IfcPolygonalFaceSet` | ❌ | ❌ | ✅ |
| `IfcFaceBasedSurfaceModel` | ✅ | ✅ | ✅ |
| `IfcMappedItem` | ✅ | ✅ | ✅ |

## Methodes Beschikbaar

### 1. SweptSolid (huidige methode)
- `IfcExtrudedAreaSolid` — profile extruderen
- `IfcRevolvedAreaSolid` — profile roteren om as

### 2. Boolean (CSG)
- `IfcBooleanResult` — union/difference/intersection
- **Probleem:** CGAL kan instabiel zijn bij complexe vormen

### 3. Tessellated (Mesh)
- `IfcTriangulatedFaceSet` — alleen driehoeken (IFC4+)
- `IfcPolygonalFaceSet` — willekeurige veelhoeken (alleen 4X3)

### 4. Brep
- `IfcFacetedBrepWithVoids` — boundary representation met gaten

### 5. Mapped/Reusable
- `IfcMappedItem` + `IfcRepresentationMap`
- Reference file gebruikt dit!

## Referentie File (hello-wall.ifc)
Gebruikt:
- `IfcShapeRepresentation` met `MappedRepresentation` type
- `IfcPolygonalFaceSet` (Tessellation representation type)
- `IfcMappedItem` → `IfcRepresentationMap`

## Workarounds

1. **Separate stukken** — lining als losse fragmenten maken (geen profile-with-voids)
2. **TriangulatedFaceSet** — IFC4 gebruiken met mesh geometry
3. **FacetedBrepWithVoids** — IFC2X3 compatible

## Volgende Stappen
- Testen welke methode het beste werkt in Bonsai viewer
- Bug report: https://github.com/IfcOpenShell/IfcOpenShell/issues/8043