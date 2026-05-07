# Window and Door Component Graph — JSON Format Reference

Each `.json` file in this directory defines a **component graph** for a window
or door type. The graph is a declarative, parametric recipe that the
`evaluate_component_graph` / `evaluate_opening_nodes` engine turns into IFC
geometry at build time.

---

## File structure

```json
{
  "version": 1,
  "parameters": { ... },
  "opening_nodes": [ ... ],
  "nodes": [ ... ]
}
```

| Key | Required | Purpose |
|-----|----------|---------|
| `version` | yes | Must be `1`. |
| `parameters` | yes | Default values for every parameter the graph uses. All values are in **millimetres**. |
| `opening_nodes` | yes | Nodes that produce the `IfcOpeningElement` void geometry (the hole cut into the wall). |
| `nodes` | yes | Nodes that produce the fill element geometry (the actual door or window body). |

---

## Parameters

Parameters are referenced in expressions as `$name`. Every parameter used
anywhere in the graph must have a default value in `parameters`. The builder
injects the following runtime parameters automatically — do not declare them as
defaults:

| Injected parameter | Value |
|--------------------|-------|
| `$w` | `overall_width` of the occurrence (mm) |
| `$h` | `overall_height` of the occurrence (mm) |
| `$wall_thickness` | Extracted from the host wall at build time (mm) |

Type-level parameters (`lining_depth`, `lining_thickness`, `panel_depth`, etc.)
are merged from the type entity and injected into the parameter set before
evaluation. Occurrence-level `parameters` override type-level values, which
override JSON defaults.

### Expression syntax

Parameter values and geometry coordinates accept arithmetic expressions:

```
"$lining_depth / 2 - $panel_depth / 2"
"2 * $wall_thickness"
"$lining_thickness + $door_width"
```

Supported operators: `+`, `-`, `*`, `/`, unary `-`, parentheses.
Operator precedence is standard (`*`/`/` before `+`/`-`).

### Coordinate scaling

In `p0` / `p1` arrays:
- **Literal numbers** (e.g. `0`, `50`) are in the **reference frame** of the
  profile and scale proportionally if the profile is scaled.
- **Variable expressions** (e.g. `"$lining_thickness"`) are already in mm
  and are **not** additionally scaled.

---

## Coordinate system

All 2D profile coordinates are in the **XY plane**, in millimetres:

- **X** = horizontal (width direction, left to right)
- **Y** = vertical (height direction, bottom to top)
- **Origin** = bottom-left corner of the bounding box before anchor offset

The anchor offset is applied automatically by the builder. The default anchor
for both windows and doors is `"s"` (bottom-centre), which shifts solids by
`-w/2` on X so the origin lands at the bottom midpoint of the frame.

Extrusions always go in the **−Z direction** (into the wall). `z_offset` is a
positive value that moves the solid away from the wall face (toward the
interior).

---

## Node types

### `rect`

Defines a closed rectangular 2D profile.

```json
{
  "id": "my_rect",
  "op": "rect",
  "p0": [0, 0],
  "p1": ["$w", "$h"]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `p0` | yes | Bottom-left corner `[x, y]` |
| `p1` | yes | Top-right corner `[x, y]` |
| `holes` | no | List of hole nodes (see below) |

A `rect` with `holes` produces an `IfcArbitraryProfileDefWithVoids` when
extruded. Without holes it produces an `IfcArbitraryClosedProfileDef`.

**IFC constraint**: IFC only supports one level of void depth. Holes of holes
are silently ignored by the IFC spec.

#### Hole types inside `rect.holes`

**`rect` hole** — a rectangular cutout:

```json
{
  "id": "door_opening",
  "op": "rect",
  "p0": ["$lining_thickness", 0],
  "p1": ["$lining_thickness + $door_width", "$door_height"]
}
```

The `id` is optional but allows other nodes (e.g. `extrude`) to reference this
hole profile by id.

**`offset` hole** — insets the outer profile by a uniform distance:

```json
{
  "op": "offset",
  "dist": "$lining_thickness"
}
```

---

### `polygon`

Arbitrary 2D polygon from explicit point list. More flexible than `rect` for creating
L-shapes, U-shapes, or any non-rectangular profile outline.

```json
{
  "id": "L_shaped_frame",
  "op": "polygon",
  "points": [
    [0, 0],
    [100, 0],
    [100, 50],
    [50, 50],
    [50, 3000],
    [0, 3000]
  ],
  "holes": [...]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `points` | yes | List of `[x, y]` coordinates in CCW order |
| `holes` | no | List of hole nodes |

Supports the same hole types as `rect`: `rect`, `polygon`, and `offset`.

---

### `difference`

2D profile boolean: outer path minus inner path → profile with a hole.

```json
{
  "id": "frame_profile",
  "op": "difference",
  "a": "outer_rect",
  "b": "inner_rect"
}
```

Both `a` and `b` must be `rect` nodes defined earlier in the same list.
The result is equivalent to adding `b` as a hole inside `a`. This is a **2D
operation** — it produces a profile, not a solid.

---

### `extrude`

Extrudes a 2D profile into a 3D solid.

```json
{
  "id": "lining",
  "op": "extrude",
  "profile": "lining_profile",
  "depth": "$lining_depth",
  "z_offset": 0,
  "output": true,
  "role": "Lining",
  "material": { ... }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `profile` | yes | Id of a `rect` or `difference` node |
| `depth` | yes | Extrusion depth in mm (expression allowed) |
| `z_offset` | no | Offset along Z (into wall) before anchor; default `0` |
| `output` | no | If `true`, include in the fill representation; default `false` |
| `role` | no | Semantic role string (`"Lining"`, `"Glazing"`, `"Panel"`, …) used for material inheritance |
| `material` | no | Inline material definition (see below) |

Produces an `IfcExtrudedAreaSolid`. Always goes into a `SweptSolid`
representation — the most robustly supported rep type in all IFC viewers.

---

### `boolean_cut` / `boolean_union` / `boolean_intersection`

3D solid boolean operations. Produce an `IfcBooleanResult`.

```json
{
  "id": "lining",
  "op": "boolean_cut",
  "base": "lining_base",
  "tool": "lining_cutter",
  "output": true,
  "role": "Lining",
  "material": { ... }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `base` | yes | Id of an `extrude` node (the solid being operated on) |
| `tool` | yes | Id of an `extrude` node (the cutting / joining solid) |
| `output` | no | Include in fill representation; default `false` |
| `role` | no | Semantic role string |
| `material` | no | Inline material definition |

When any output node is a `boolean_cut`/`union`/`intersection`, the fill
representation type is promoted from `SweptSolid` to `SolidModel` (mixed) or
`CSG` (all boolean results).

#### Boolean limitations in IFC viewers

3D booleans are **significantly less robustly supported** than extruded profiles
across IFC viewers. The following cases are known to **fail** in Bonsai
(BlenderBIM) while succeeding in web-ifc:

1. **Base has a profile with holes** (`IfcArbitraryProfileDefWithVoids`) — the
   boolean fails entirely. The lining geometry will not appear.
2. **Tool path shares an edge with the base path** — e.g. a cutter whose bottom
   edge coincides with the bottom edge of the base profile.
3. **Tool path extends outside the base path** — e.g. a cutter that crosses
   the XY boundary of the base solid.

**Safe boolean usage** (works in Bonsai):
- Base is a simple closed profile (`IfcArbitraryClosedProfileDef`) with no holes.
- Tool profile is entirely contained inside the base profile boundary, with no
  shared edges.
- The tool does not reach the exterior faces of the base solid.

**Preferred alternative**: for frame profiles with rectangular openings, declare
the openings as **holes in the `rect` node** rather than using `boolean_cut`.
This keeps the representation as `SweptSolid` with `IfcArbitraryProfileDefWithVoids`,
which all viewers handle robustly. See `fixed_casement.json` (offset hole) and
`door_flush.json` (rect holes) for examples.

---

## `opening_nodes`

Same node types as `nodes`, but used to build the `IfcOpeningElement` void that
is cut into the host wall. Nodes with `"output": true` and `"role": "Opening"`
contribute to the opening solid.

The opening void should be slightly oversized (deeper than the wall) to ensure a
clean boolean cut by the IFC viewer. Use `"depth": "2 * $wall_thickness"` as a
safe default.

**Opening solids must not be styled** — applying an `IfcStyledItem` to an
opening solid breaks geometry processing in ifcopenshell/Bonsai. The builder
enforces this automatically.

---

## Material definition

Any `extrude` or boolean node with `"output": true` can carry a material:

```json
"material": {
  "color": {"r": 0.8, "g": 0.8, "b": 0.8},
  "transparency": 0.0,
  "name": "Aluminum frame"
}
```

| Field | Range | Description |
|-------|-------|-------------|
| `color.r/g/b` | 0.0 – 1.0 | RGB diffuse colour |
| `transparency` | 0.0 – 1.0 | 0 = fully opaque, 1 = fully transparent |
| `name` | string | Material name (shown in viewer) |

Materials are applied as `IfcSurfaceStyleRendering` with `Side=BOTH`, which is
supported by Bonsai, web-ifc, and FreeCAD. If no material is defined on an
output node, a neutral grey (`0.75, 0.75, 0.75`, fully opaque) is used as
fallback.

Material can be **overridden at the type or occurrence level** in the JSON build
file using `material_overrides` keyed by role name.

---

## Roles

The `role` field on output nodes is a free string that:
1. Groups components semantically (`"Lining"`, `"Glazing"`, `"Panel"`, `"Opening"`)
2. Is the key used for `material_overrides` in the type / occurrence JSON

There is no enforced vocabulary, but conventional values are:

| Role | Used for |
|------|----------|
| `Lining` | Frame / surround |
| `Glazing` | Glass pane |
| `Panel` | Opaque door leaf |
| `Opening` | Opening void (opening_nodes only) |

---

## Representation types

The builder selects the `IfcShapeRepresentation.RepresentationType` automatically:

| Condition | Rep type |
|-----------|----------|
| All output solids are `IfcExtrudedAreaSolid` | `SweptSolid` |
| Mix of `IfcExtrudedAreaSolid` and `IfcBooleanResult` | `SolidModel` |
| All output solids are `IfcBooleanResult` | `CSG` |

`SweptSolid` is the most universally supported. Avoid `CSG` and `SolidModel`
unless the boolean limitations above are fully understood and tested.

---

## Example: fixed_casement.json

Simple window with an inset glazing pane. Lining uses an `offset` hole — the
cleanest possible frame definition.

## Example: door_flush.json

Door with lining frame, door panel, and two glazing panels (top light and side
light). Lining uses explicit `rect` holes for the door opening, top glazing, and
side glazing. All output solids are `IfcExtrudedAreaSolid` → `SweptSolid` rep.
