# Parametric Detail System — Plan

## Core Insight

Every element connects to something. The current "host" exception (window/door in
wall) is actually the rule: all element-to-element interfaces need resolution.

IFC can store *that* elements connect (`IfcRelConnectsElements`,
`IfcRelConnectsWithRealizingElements`) but not *what the connection means* —
its quality, load path, tolerance, or detail type. The Python layer carries that
semantics; IFC is the standardised export.

## Architecture

### Element → Interface → Contact → Detail

- **`ElementInterface`**: declares a connection face/surface on a `PendingElement`
  (plane, type enum, host ref). Default empty list on base class; subclasses
  override (start/end face for beams, edges for walls, etc.).

- **`ContactPair`**: two `ElementInterface` instances that contact in space
  (contact plane, angle, offset). Detection can be explicit (user pairs them) or
  inferred from geometry. Allows flagging non‑orthogonal / non‑standard contacts.

- **`Detail` (ABC)**: resolves a `ContactPair` into IFC elements. `build(ifc_file,
  contact, params) → DetailResult`. Polymorphic per connection type.

- **`DetailComponent`**: reusable sub‑building‑block (RectPlate, BoltGroup,
  WeldBead, ClipPlane). Composed inside `Detail.build()`.

- **`DetailResult`**: `elements` (new IFC elements), `modifications` (clips/cuts
  on hosts), `connection_geometry`, `connection_type` label.

### Registration

Same pattern as `COMPONENT_REGISTRY`: `DETAIL_REGISTRY = {}`, auto‑discovery
of `detail/*.py` files, JSON/preset fallback.

### Output in IFC

- New elements: `IfcPlate`, `IfcMechanicalFastener`, `IfcDiscreteAccessory`
- Grouping: `IfcElementAssembly(PredefinedType="CONNECTION_ASSEMBLY")`
- Relationship: `IfcRelConnectsWithRealizingElements` + `ConnectionGeometry`
- Host modifications: `IfcBooleanClippingResult`, `IfcRelVoidsElement`

## Decisions Made

1. **Generator, not constraint solver**: solveSpace/OCAF constraints are 2D →
   unnecessary complexity for 90 % of building connections. Declarative parameter
   resolution (JSON‑DAG style) suffices.

2. **Additive, not refactor**: `ifckit/details/` is new. `FillComponent`, Model B,
   builders untouched. Only `IfcModel.connect()` added (~1 method).

3. **Opening‑fill ≠ connection**: `FillComponent` handles
   `IfcRelVoidsElement+IfcRelFillsElement` (window/door in wall). `Detail` handles
   `IfcRelConnectsWithRealizingElements` (beam‑column, wall‑wall, etc.).
   Separate ABCs, no forced unification.

4. **First target: steel structure**: beam‑column (BoltedEndPlate, WeldedFinPlate),
   column‑foundation (BasePlate), bracing (GussetPlate). Geometry is well‑known
   and parameterisable.

## Open Questions (for later)

- Interface detection: automatic (geometric overlap) or explicit (user pairs)?
- Host modifications: clip‑planes or full boolean cuts?
- Strict typed params per `Detail` subclass or generic `dict`?
- JSON preset format for details (parallel to component‑graph JSON)?
