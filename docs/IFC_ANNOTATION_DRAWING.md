# IFC Annotation & Drawing Research

## Goal

Generate plan-view symbol geometry for IfcDoor/IfcWindow that renders in
viewers (Bonsai, ODA Open IFC Viewer, FreeCAD, web-ifc).

## What We Tried (Failed)

1. **FootPrint / GeometricCurveSet** — spec-correct IFC4.  Renders
   nowhere: ifcopenshell 0.8.x C++ kernel skips curve-only geometry on
   building elements (`dimensionality=1` default), ODA viewer ignores it,
   Bonsai requires Blender mesh for SVG projection.

2. **Thin-strip mesh on Body** — 10 mm IfcTriangulatedFaceSet strip
   appended to Body rep.  Renders in ifcopenshell geom engine, **not**
   in ODA Open IFC Viewer.

3. **IfcAnnotation proxy** — separate entity with IfcRelAssignsToProduct.
   Causes Bonsai import errors (`Instance #X not found`).

## ifcopenshell API — Annotation Support

`ifcopenshell.api.geometry.add_representation()` supports:

- `"IfcTextLiteral"` → `IfcTextLiteralWithExtent` in `Annotation2D/3D`
- `"IfcGeometricCurveSet/IfcTextLiteral"` → curves + text
- `FootPrint + PLAN_VIEW` → `GeometricCurveSet` (same as our approach)
- `Annotation` context → `IfcAnnotationFillArea` for meshes, `IfcGeometricCurveSet` for curves

`ifcopenshell.api.drawing` module:
- `edit_text_literal()` — set attributes on IfcTextLiteral
- `assign_product()` / `unassign_product()` — link IfcAnnotation to IfcProduct

## Bonsai Drawing Pipeline

Bonsai generates SVG by **projecting Blender mesh geometry onto a camera
plane** (`svgwriter.py`, 1700 lines).  It does **not** read FootPrint or
Annotation curves for linework — it uses the 3D Body mesh projected onto
the drawing view.

Annotation types (18): DIMENSION, ANGLE, TEXT, SYMBOL, STAIR_ARROW,
SECTION_LEVEL, PLAN_LEVEL, BREAKLINE, FILL_AREA, BATTING, etc.

- Curve types → `draw_line_annotation` / `draw_edge_annotation`
- Mesh types → `draw_misc_annotation` (face projection)
- Empty types (TEXT, SYMBOL) → SVG `<symbol>` references or text overlays

SVG symbols file: `bonsai/bim/data/assets/symbols.svg` — contains
`door-tag`, `window-tag`, but these are **drawing labels** (circles with
text tags), not plan-view footprint symbols.

## Key Insight

**No viewer renders curve-only geometry on products or annotations.**

- Bonsai SVG linework comes from 3D mesh → camera projection, not from
  FootPrint/Annotation curves
- ODA Viewer, FreeCAD, web-ifc all require triangulated face geometry
- IfcTextLiteral is a special rendering case in Bonsai (text overlay)

Only reliable path to visible plan-view symbols: **thin triangulated mesh
in Body representation**.  This works in ifcopenshell-based tools but not
in ODA's viewer.

## Our Solution: `ifckit.draw`

**Headless SVG generation** — no Rhino, no Blender, no viewer dependency.

### Pipeline

```
IFC model → ifcopenshell.draw (headless) → SVG → inject_symbols() → final SVG
                                              ↑
                                   Footprint.door_swing() in world coords,
                                   transformed to SVG space
```

### Module: `ifckit/draw/__init__.py`

Public API:
- `generate_svg(ifc_model, drawing_guid, ...) → bytes` — headless SVG via `ifcopenshell.draw`
- `inject_symbols(svg_bytes, ifc_file) → bytes` — inject door swing arcs into SVG XML
- `save_svg(svg_bytes, path) → None`

### Module: `ifckit/draw/_svg.py`

SVG utilities:
- `curves_to_svg_d(curves, plane_mat, svg_transform) → str` — Line/Arc → SVG `d` string
- `world_to_svg(world_pt, plane_mat_inv, sc, tx, ty) → (x, y)`
- `parse_matrix3()` / `parse_plane_attr()` — SVG attribute parsing
- `parse_path_d(d) → segments` — SVG path parser (moved from `rhino_import.py`)

### How `inject_symbols` works

1. Parse SVG XML from `ifcopenshell.draw`
2. Find `<g>` with `ifc:matrix3` attribute (handles both `<g class="section">` and `<g class="IfcBuildingStorey">`)
3. Extract `ifc:matrix3` (scale/translate) and `ifc:plane` (section plane matrix)
4. Detect IFC project length unit (e.g. MILLI → mm→m conversion)
5. For each `IfcDoor`:
   - Get world placement via `placement_util.get_local_placement()`
   - Build world-space Plane: origin=col3, x_axis=col0, swing_dir=col2 (Z-axis, through-wall)
   - `Footprint.door_swing(world_plane, leaf_w)` → 2 curves (line + arc)
   - Transform curve points: world → SVG coords
   - Inject as `<path class="IfcDoor" ifc:guid="..." />` in `<g class="projection">`
6. Return modified SVG bytes (clean namespace serialization)

### Key details

- **Unit conversion**: Placement coordinates are in IFC file units (e.g. mm). SVG `ifc:matrix3` expects metres. `_ifc_unit_factor()` detects the project unit and converts.
- **Swing direction**: Uses matrix column 2 (Z-axis = through-wall) as swing direction, not column 1 (Y-axis = up).
- **Namespace**: `ET.register_namespace("", svg_ns)` ensures clean `xmlns="..."` output without `ns0:` prefixes.
- **`door_arcs=True`**: `ifcopenshell.draw`'s built-in door arc support is enabled. Our injection is supplementary.

### File changes

| File | Change |
|---|---|
| `ifckit/draw/__init__.py` | NEW — `generate_svg()`, `inject_symbols()`, `save_svg()` |
| `ifckit/draw/_svg.py` | NEW — SVG path utilities, coordinate transforms |
| `ifckit/rhino_import.py` | `_generate_svg()` → thin wrapper for `ifckit.draw.generate_svg()`; `import_model()` calls `inject_symbols()` before `_process_svg()` |
| `grasshopper/src/gh_drawing.py` | Uses `IfcSvgImporter` which delegates to `ifckit.draw` |
