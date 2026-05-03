# IFC Doors and Windows (Typed) — Implementation Plan

## Purpose

This document defines an implementation plan for adding **IFC-compliant doors and windows with type support** to `ifckit`.

Target outcome:
- Doors and windows are modeled semantically with proper IFC relationships.
- Openings, fills, and type assignment are explicit and testable.
- Output is compatible with Bonsai workflows (authoring, review, scheduling, drawing generation).


## Scope

### In Scope

- New pending element families:
  - `PendingOpening`
  - `PendingDoor`
  - `PendingWindow`
  - `PendingDoorType`
  - `PendingWindowType`
- IFC relationship creation:
  - `IfcRelVoidsElement` (host -> opening)
  - `IfcRelFillsElement` (opening -> door/window)
  - `IfcRelDefinesByType` (door/window occurrence -> type)
- Type lifecycle and reuse:
  - deterministic type key/signature
  - type cache / reuse per model
- Storey containment for opening and fill products.
- JSON build support for new entities and references.
- Grasshopper components for opening, door, and window creation.
- Validation, tests, documentation.

### Out of Scope (Initial Typed Release)

- Full vendor-level family libraries.
- Complex frame/panel parametrics beyond a strict initial subset.
- Automatic host inference from spatial proximity.
- Multi-host openings (e.g., one opening voiding multiple walls) as a first-class feature.


## IFC Semantics (Canonical Model)

Doors and windows must follow this graph:

`IfcWall|IfcSlab|IfcRoof|IfcPlate`
-> `IfcRelVoidsElement`
-> `IfcOpeningElement`
-> `IfcRelFillsElement`
-> `IfcDoor|IfcWindow`
-> `IfcRelDefinesByType`
-> `IfcDoorType|IfcWindowType`

This is non-negotiable for strong BIM interoperability.


## Compatibility Targets

- Primary target: **IFC4**.
- Secondary target: **IFC2X3** compatibility pass after IFC4 stabilizes.
- Bonsai target behavior:
  - opening visible as opening semantic,
  - fill object linked to opening,
  - reusable type objects visible for schedule logic.


## Data Model Design

### 1) PendingOpening

Suggested fields:
- `element_type = "basic_opening"`
- `name: str`
- `host_ref: str | None` (reference to host entity handle id in JSON workflows)
- `footprint: list[Vec]` and `plane: Plane` and `height: float`
- `clips: list[Plane]` (inherits existing clip strategy)
- `style: RenderStyle | None`
- `properties: dict[str, Any]`

Notes:
- Geometry strategy should match wall/slab extrusion approach for consistency.
- Opening geometry should be local to host placement semantics where possible.

### 2) PendingDoor / PendingWindow

Suggested fields (occurrence-level):
- `element_type = "basic_door" | "basic_window"`
- `name: str`
- `opening_ref: str | None`
- `placement_plane: Plane` (or local offset from opening)
- `overall_width: float`
- `overall_height: float`
- `type_ref: str | None` (optional explicit type key)
- `style: RenderStyle | None`
- `properties: dict[str, Any]`

### 3) PendingDoorType / PendingWindowType

Suggested fields (type-level minimal subset):
- `element_type = "door_type" | "window_type"`
- `type_key: str` (deterministic signature or user override)
- `name: str`
- `operation_type: str` (strict enum subset)
- `overall_width: float`
- `overall_height: float`
- `lining_params: dict[str, float]` (subset)
- `panel_params: dict[str, float]` (subset)
- `properties: dict[str, Any]`

Type key policy:
- If user provides `type_key`, use it.
- Else derive key from normalized parameter tuple.


## API Design

Current `IfcModel.add(pending, container)` is single-element oriented and does not encode host/opening links robustly.
Add explicit relationship-aware APIs:

- `IfcModel.add_opening(pending_opening, host: EntityHandle, container: StoreyHandle) -> EntityHandle`
- `IfcModel.add_door(pending_door, opening: EntityHandle, container: StoreyHandle, door_type: EntityHandle | None = None) -> EntityHandle`
- `IfcModel.add_window(pending_window, opening: EntityHandle, container: StoreyHandle, window_type: EntityHandle | None = None) -> EntityHandle`
- `IfcModel.add_door_type(pending_type) -> EntityHandle`
- `IfcModel.add_window_type(pending_type) -> EntityHandle`

Handle convenience methods:
- `EntityHandle.add_opening(...)`
- `EntityHandle.add_door(...)` and `EntityHandle.add_window(...)` (only valid when entity is opening)

Behavior rules:
- Fail fast on incompatible host/opening types.
- Ensure containment is assigned.
- Ensure relationship cardinality is valid.


## Builder Design

### OpeningBuilder

Responsibilities:
- Create `IfcOpeningElement` geometry and placement.
- Assign `IfcRelVoidsElement` linking host and opening.
- Assign spatial containment.
- Apply style and EPset handling (reuse base pattern).

### DoorBuilder / WindowBuilder

Responsibilities:
- Create occurrence geometry and placement.
- Assign `IfcRelFillsElement` from opening to fill.
- Assign containment.
- Assign type relation if type provided/resolved.

### DoorTypeBuilder / WindowTypeBuilder

Responsibilities:
- Create and cache `IfcDoorType` / `IfcWindowType`.
- Set supported minimal attributes and psets.
- Return existing type when key already exists.


## Type Reuse Strategy

Implement a model-local type registry:
- internal map: `{type_key: ifc_entity_instance}`
- strict key normalization to avoid accidental duplicates.

Deterministic key format example:
- `door:{operation}:{w}:{h}:{lining_hash}:{panel_hash}`
- `window:{operation}:{w}:{h}:{lining_hash}:{panel_hash}`

Rules:
- same key => same type entity reused.
- incompatible explicit key collisions => raise `ValueError`.


## JSON Schema and Build Pipeline

Update `ifckit/json_build.py` and JSON validation to support:

Root-level optional sections:
- `door_types: []`
- `window_types: []`

Storey-level elements include reference fields:
- opening entries reference host by temporary id or explicit handle token.
- door/window entries reference opening and optional type key.

Implementation approach:
- two-pass (or three-pass) build order:
  1. create host elements,
  2. create openings linked to hosts,
  3. create door/windows linked to openings and types.

Validation must verify that referenced ids exist and are compatible.


## Grasshopper Plan

Add components:
- `gh_create_opening.py`
- `gh_create_door.py`
- `gh_create_window.py`

Input strategy (first release):
- explicit host/opening JSON references rather than auto-detection.
- optional `type_key` plus minimal type params.

Output strategy:
- JSON payload includes stable local ids for chaining in GH graphs.

Rebuild `ifckit-components.gh` via existing `build_gh.py` flow.


## Validation Plan

Add validators for each new pending class:

- `PendingOpening`
  - positive height
  - valid footprint/plane
  - valid host reference at model-add stage

- `PendingDoor` / `PendingWindow`
  - positive width/height
  - valid opening reference at model-add stage
  - operation type in allowed subset

- `PendingDoorType` / `PendingWindowType`
  - non-empty operation type and valid enum
  - non-negative numeric parameters

Warnings (non-fatal):
- unusual dimensions,
- missing optional lining/panel parameters falling back to defaults.


## Milestones and Phasing

This section is the executable roadmap. Each milestone has explicit TODOs and hard exit gates.

### M0 - Design Lock (Phase 0)

Objective:
- freeze v1 typed scope so implementation does not drift.

TODOs:
- [ ] Freeze door/window operation enum subset for v1.
- [ ] Freeze required and optional type parameters (lining/panel fields).
- [ ] Freeze allowed opening host classes in v1 (`IfcWall` first; optional `IfcSlab`).
- [ ] Freeze JSON reference strategy (`id`, `host_ref`, `opening_ref`, `type_key`).
- [ ] Sign off this plan.

Exit gate:
- no unresolved schema questions remain for core implementation.

### M1 - Core Pending Models (Phase 1A)

Objective:
- add new pending classes with stable serialization.

TODOs:
- [ ] Add `ifckit/elements/opening.py`.
- [ ] Implement `PendingOpening`, `PendingDoor`, `PendingWindow`.
- [ ] Implement `PendingDoorType`, `PendingWindowType`.
- [ ] Add `to_dict()`/`from_dict()` roundtrip tests.
- [ ] Export symbols from `ifckit/elements/__init__.py` and `ifckit/__init__.py`.

Exit gate:
- element roundtrip tests pass with 100 percent coverage for new classes.

### M2 - Core Builders and Relationships (Phase 1B)

Objective:
- produce IFC entities and semantic relationships.

TODOs:
- [ ] Add `OpeningBuilder`.
- [ ] Add `DoorBuilder` and `WindowBuilder`.
- [ ] Create `IfcRelVoidsElement` from host to opening.
- [ ] Create `IfcRelFillsElement` from opening to door/window.
- [ ] Ensure containment assignment for opening and fill products.
- [ ] Register builders in `ifckit/builders/__init__.py`.

Exit gate:
- integration tests confirm `RelVoids` and `RelFills` entities exist and point to correct instances.

### M3 - Model and Handle APIs (Phase 1C)

Objective:
- expose safe relationship-aware authoring APIs.

TODOs:
- [ ] Add `IfcModel.add_opening(...)`.
- [ ] Add `IfcModel.add_door(...)` and `IfcModel.add_window(...)`.
- [ ] Add `IfcModel.add_door_type(...)` and `IfcModel.add_window_type(...)`.
- [ ] Add convenience methods on `EntityHandle` / `StoreyHandle` where useful.
- [ ] Add explicit type and cardinality checks with clear errors.

Exit gate:
- direct API usage can build host -> opening -> fill chain with no raw ifcopenshell calls.

### M4 - Type Reuse System (Phase 2)

Objective:
- deterministic type creation and reuse.

TODOs:
- [ ] Implement model-local type cache (`type_key -> IfcTypeObject`).
- [ ] Add canonical type signature normalization.
- [ ] Add `IfcRelDefinesByType` assignment for door/window occurrences.
- [ ] Detect and reject incompatible explicit type key collisions.
- [ ] Add tests for reuse across multiple occurrences and storeys.

Exit gate:
- repeated equal type definitions resolve to one IFC type entity.

### M5 - JSON Build Pipeline (Phase 3A)

Objective:
- support typed openings/doors/windows in JSON workflows.

TODOs:
- [ ] Extend `validate_json()` with new sections and refs.
- [ ] Extend `build()` with multi-pass relationship construction.
- [ ] Add root-level type sections (`door_types`, `window_types`).
- [ ] Add robust unresolved-reference errors.
- [ ] Keep backward compatibility for existing JSON inputs.

Exit gate:
- JSON fixture with walls/openings/doors/windows/types builds valid IFC and passes integration assertions.

### M6 - Grasshopper Components (Phase 3B)

Objective:
- expose new feature set in GH authoring flow.

TODOs:
- [ ] Add `gh_create_opening.py`.
- [ ] Add `gh_create_door.py`.
- [ ] Add `gh_create_window.py`.
- [ ] Wire stable ids and refs in JSON payloads.
- [ ] Rebuild `grasshopper/ifckit-components.gh` via `build_gh.py`.

Exit gate:
- reference GH graph builds semantic opening/fill/type IFC chain.

### M7 - IFC2X3 Compatibility Pass (Phase 4A)

Objective:
- keep behavior predictable under IFC2X3 constraints.

TODOs:
- [ ] Run full IFC2X3 integration scenarios for openings/doors/windows.
- [ ] Add schema-conditional handling where attributes differ.
- [ ] Document unsupported type attributes if needed.
- [ ] Ensure errors are explicit when IFC2X3 lacks requested semantics.

Exit gate:
- compatibility matrix is documented and automated tests are green.

### M8 - Hardening and Release (Phase 4B)

Objective:
- production-ready quality and docs.

TODOs:
- [ ] Add regression tests for existing 689 baseline plus new features.
- [ ] Update docs (`ARCHITECTURE.md`, `DESIGN.md`, README examples).
- [ ] Add changelog entry.
- [ ] Verify Bonsai manual smoke checklist.

Exit gate:
- all tests green, docs updated, and manual Bonsai validation complete.


## TODO Tracker by Workstream

### Workstream A - Data and Serialization
- [ ] Add new pending element and type classes.
- [ ] Add strict field defaults and constructors.
- [ ] Add roundtrip tests and negative deserialization tests.

### Workstream B - IFC Construction
- [ ] Add builders for opening/door/window/type.
- [ ] Add relationship helper utilities if repeated.
- [ ] Add placement consistency checks with host/opening planes.

### Workstream C - API Surface
- [ ] Add `IfcModel` relationship-aware creation methods.
- [ ] Add handle convenience methods.
- [ ] Keep `model.add()` behavior stable for existing element types.

### Workstream D - JSON and GH
- [ ] Extend JSON schema/build with reference resolution.
- [ ] Add GH nodes and metadata annotations.
- [ ] Rebuild GH package and validate node signatures.

### Workstream E - Quality and Compatibility
- [ ] Add unit + integration + regression tests.
- [ ] Add IFC4 and IFC2X3 behavior matrix.
- [ ] Add Bonsai smoke-test checklist and findings.


## Test Plan and Matrix

### Test Layers

1) Unit tests
- pending classes
- validators
- type-key normalization
- builder-level relationship creation

2) Integration tests
- full model builds through `IfcModel`
- JSON build path through `json_build.build()`
- schema-specific paths (IFC4 and IFC2X3)

3) Manual smoke tests
- Bonsai semantic behavior and schedule reuse checks

### Required Test Files

- `tests/elements/test_opening.py`
- `tests/elements/test_doors_windows.py`
- `tests/builders/test_opening_builder.py`
- `tests/builders/test_door_window_builder.py`
- `tests/builders/test_type_builders.py`
- `tests/test_model_doors_windows.py`
- `tests/test_json_build_doors_windows.py`
- extend `tests/ifc/test_ifc_output.py`

### Scenario Matrix

- S1: wall + opening + door
  - assert `IfcOpeningElement`, `IfcRelVoidsElement`, `IfcRelFillsElement`
- S2: wall + opening + window
  - same assertions as S1 with window classes
- S3: 10 doors with same type params
  - assert single `IfcDoorType`, multiple `IfcRelDefinesByType`
- S4: 10 windows with same type params
  - assert single `IfcWindowType`, multiple `IfcRelDefinesByType`
- S5: mixed storeys and containers
  - assert containment in expected storey
- S6: invalid references
  - host/opening/type reference errors are deterministic and clear
- S7: IFC2X3 mode
  - assert supported relation graph and documented schema limitations

### Test Gates per Milestone

- Gate M1: new element tests green.
- Gate M2: relation-creation integration tests green.
- Gate M4: type reuse and collision tests green.
- Gate M5: JSON integration tests green.
- Gate M6: GH smoke workflow green.
- Gate M7: IFC2X3 matrix green.
- Gate M8: full suite green, no regressions.


## Definition of Done

Done means all are true:
- milestones M0 through M8 closed,
- IFC semantic chain is present and verified,
- type reuse is deterministic,
- JSON and GH support reference-based authoring,
- IFC4 and IFC2X3 behavior is documented and tested,
- Bonsai smoke tests pass.


## File-Level Change Plan

### New files

- `ifckit/elements/opening.py`
- `ifckit/builders/opening.py`
- `ifckit/builders/door_window.py`
- `grasshopper/src/gh_create_opening.py`
- `grasshopper/src/gh_create_door.py`
- `grasshopper/src/gh_create_window.py`
- tests listed above

### Modified files

- `ifckit/elements/__init__.py`
- `ifckit/__init__.py`
- `ifckit/builders/__init__.py`
- `ifckit/model.py`
- `ifckit/handles.py`
- `ifckit/json_build.py`
- `ifckit/validator.py`
- `grasshopper/script/build_gh.py` (only if metadata wiring needed)


## Risk Register

1) **Schema drift between IFC4 and IFC2X3**
- Mitigation: IFC4-first implementation, then controlled compatibility layer.

2) **Reference resolution complexity in JSON/GH**
- Mitigation: explicit local ids, deterministic build pass order, strict validation.

3) **Type explosion from weak key normalization**
- Mitigation: canonical signature function + tests for key stability.

4) **Bonsai behavior mismatch**
- Mitigation: maintain relationship semantics, run manual Bonsai smoke checks per milestone.

5) **Regression risk to existing element flow**
- Mitigation: isolate new APIs, avoid breaking `model.add()`, keep backwards-compatible JSON where possible.


## Acceptance Criteria

Feature is complete when:
- doors/windows/openings are created with valid IFC relationships,
- type entities are reused deterministically,
- JSON and GH workflows can author the full chain,
- full automated test suite passes,
- Bonsai can read and treat elements semantically.


## Suggested Commit Plan

1. `feat(elements): add opening door window pending models`
2. `feat(builders): add opening and fill builders`
3. `feat(model): add relationship-aware opening and fill APIs`
4. `feat(types): add door/window type builders and reuse cache`
5. `feat(json): add typed openings/doors/windows build support`
6. `feat(gh): add opening door window GH components`
7. `test(ifc): add opening fill type integration scenarios`
8. `docs: add typed doors/windows implementation notes`


## Immediate Next Step

Before coding, freeze the initial typed parameter subset:
- operation enums to support,
- required vs optional lining/panel fields,
- host classes allowed for openings in v1.


---

# Addendum: Type Factory Module (Userland)

This addendum defines the userland type factory module that provides programmatic creation of door and window types with FootPrint geometry generation. This module is independent from the core pending/builder work and outputs JSON-serializable types.

## Overview

The type factory module (`ifckit/types/`) provides high-level factory classes for creating door and window types:

- `Door.create_type()` — creates door type with operation, lining, panel parameters
- `Window.create_type()` — creates window type with partitioning, operation, lining parameters
- FootPrint generation — creates 2D swing arc geometry for plan views

Output integrates with the core pending types from M1 workstream.

## Scope

| In Scope | Out of Scope |
|----------|-------------|
| `Door.create_type()` | Occurrence creation |
| `Window.create_type()` | Opening creation |
| FootPrint generation | GH components |
| JSON-serializable output | IFC2X3 support |
| Optional direct IFC entity | External library files |

## Architecture

```
ifckit/types/                 Core (M1-M3 workstream)
─────────────────           ────────────────────────
Door.create_type()         →  PendingDoorType (consumes)
Window.create_type()      →  PendingWindowType (consumes)
footprint.generate()      →  (local, no dependency)
```

No coupling to core — this module outputs pending types that the core pipeline consumes.

## API Design

### Door Factory

```python
class Door:
    """Door type factory."""
    
    @staticmethod
    def create_type(
        operation: DoorOperation = DoorOperation.SINGLE_SWING_LEFT,
        lining_thickness: float = 0.05,
        lining_depth: float = 0.10,
        panel_depth: float = 0.04,
        panel_width_ratio: float = 1.0,
    ) -> PendingDoorType:
        """Create door type (JSON-serializable)."""
        
    @staticmethod
    def create_footprint(
        width: float,
        height: float,
        operation: DoorOperation,
    ) -> list[Curve]:
        """Generate 2D swing arc for plan view."""
```

### Window Factory

```python
class Window:
    """Window type factory."""
    
    @staticmethod
    def create_type(
        partitioning: WindowPartitioning = WindowPartitioning.SINGLE_PANEL,
        operation: WindowOperation = WindowOperation.FIXED,
        lining_thickness: float = 0.05,
        lining_depth: float = 0.05,
        mullion_thickness: float = 0.05,
    ) -> PendingWindowType:
        """Create window type (JSON-serializable)."""
        
    @staticmethod
    def create_footprint(
        width: float,
        height: float,
        partitioning: WindowPartitioning,
    ) -> list[Curve]:
        """Generate 2D opening symbol for plan view."""
```

### Dual Output

Each factory method returns pending types (JSON-serializable). Optionally accepts an `IfcModel` and returns actual IFC entities:

```python
# Returns pending (JSON-serializable)
pending_type = Door.create_type(operation="SINGLE_SWING_LEFT")

# Returns IFC entity (if model provided)
entity = Door.create_type(operation="SINGLE_SWING_LEFT", ifc_model=model)
```

## Enums

### DoorOperation

Based on `IfcDoorTypeOperationEnum` (IFC4 spec):

```python
class DoorOperation(Enum):
    SINGLE_SWING_LEFT = "SINGLE_SWING_LEFT"
    SINGLE_SWING_RIGHT = "SINGLE_SWING_RIGHT"
    DOUBLE_DOOR_SINGLE_SWING = "DOUBLE_DOOR_SINGLE_SWING"
    DOUBLE_DOOR_DOUBLE_SWING = "DOUBLE_DOOR_DOUBLE_SWING"
    SLIDING_TO_LEFT = "SLIDING_TO_LEFT"
    SLIDING_TO_RIGHT = "SLIDING_TO_RIGHT"
    FOLDING_TO_LEFT = "FOLDING_TO_LEFT"
    FOLDING_TO_RIGHT = "FOLDING_TO_RIGHT"
    REVOLVING = "REVOLVING"
```

### WindowOperation

Based on `IfcWindowPanelOperationEnum` (IFC4 spec):

```python
class WindowOperation(Enum):
    FIXED = "FIXED"
    SIDE_HUNG_LEFT = "SIDE_HUNG_LEFT"
    SIDE_HUNG_RIGHT = "SIDE_HUNG_RIGHT"
    TOP_HUNG = "TOP_HUNG"
    BOTTOM_HUNG = "BOTTOM_HUNG"
    PIVOT_HORIZONTAL = "PIVOT_HORIZONTAL"
    PIVOT_VERTICAL = "PIVOT_VERTICAL"
    SLIDING_HORIZONTAL = "SLIDING_HORIZONTAL"
    SLIDING_VERTICAL = "SLIDING_VERTICAL"
```

### WindowPartitioning

Based on `IfcWindowTypePartitioningEnum` (IFC4 spec):

```python
class WindowPartitioning(Enum):
    SINGLE_PANEL = "SINGLE_PANEL"
    DOUBLE_PANEL_HORIZONTAL = "DOUBLE_PANEL_HORIZONTAL"
    DOUBLE_PANEL_VERTICAL = "DOUBLE_PANEL_VERTICAL"
    TRIPLE_PANEL_HORIZONTAL = "TRIPLE_PANEL_HORIZONTAL"
    TRIPLE_PANEL_VERTICAL = "TRIPLE_PANEL_VERTICAL"
    TRIPLE_PANEL = "TRIPLE_PANEL"
```

## FootPrint Generation

### Mapping: Operation → FootPrint Geometry

| Operation | FootPrint |
|-----------|----------|
| SINGLE_SWING_LEFT | Quarter arc from left hinge (90°) |
| SINGLE_SWING_RIGHT | Quarter arc from right hinge (90°) |
| DOUBLE_DOOR_SINGLE_SWING | Two symmetric quarter arcs |
| DOUBLE_DOOR_DOUBLE_SWING | Two symmetric half arcs (180°) |
| SLIDING_* | No arc (straight slide) |
| FOLDING_* | No arc |
| FIXED | No arc |
| SIDE_HUNG_* | Quarter arc from hinge |
| TOP_HUNG / BOTTOM_HUNG | Horizontal arc |
| PIVOT_* | Half arc |
| SLIDING_* | No arc |

### Output Format

FootPrint returns a list of curves:
- Base rectangle (door/window outline in 2D)
- Arc segment (if swinging operation)
- Optional: panel edge line

## Data Model Design

### PendingDoorType

Fields (subclass of PendingElement):

```python
@dataclass
class PendingDoorType(PendingElement):
    element_type: str = "door_type"
    name: str = ""
    operation_type: str = "SINGLE_SWING_LEFT"
    lining_thickness: float = 0.05
    lining_depth: float = 0.10
    panel_depth: float = 0.04
    panel_width_ratio: float = 1.0
    # From base:
    style: RenderStyle | None = None
    properties: dict[str, Any] = field(default_factory=dict)
```

### PendingWindowType

```python
@dataclass
class PendingWindowType(PendingElement):
    element_type: str = "window_type"
    name: str = ""
    partitioning_type: str = "SINGLE_PANEL"
    operation_type: str = "FIXED"
    lining_thickness: float = 0.05
    lining_depth: float = 0.05
    mullion_thickness: float = 0.05
    # From base:
    style: RenderStyle | None = None
    properties: dict[str, Any] = field(default_factory=dict)
```

## Milestones

### T0 — Setup

- [ ] Create directory `ifckit/types/`
- [ ] Create `ifckit/types/__init__.py`

### T1 — Enums

- [ ] Create `ifckit/types/enums.py`
- [ ] Define `DoorOperation` enum
- [ ] Define `WindowOperation` enum
- [ ] Define `WindowPartitioning` enum

### T2 — Door Factory

- [ ] Create `ifckit/types/door.py`
- [ ] Implement `Door.create_type()` 
- [ ] Implement `PendingDoorType` dataclass
- [ ] Implement `to_dict()` / `from_dict()` roundtrip

### T3 — Window Factory

- [ ] Create `ifckit/types/window.py`
- [ ] Implement `Window.create_type()`
- [ ] Implement `PendingWindowType` dataclass  
- [ ] Implement `to_dict()` / `from_dict()` roundtrip

### T4 — FootPrint Generation

- [ ] Create `ifckit/types/footprint.py`
- [ ] Implement `door_footprint()` → arc + rectangle
- [ ] Implement `window_footprint()` → opening symbol
- [ ] Map operation enum → FootPrint geometry

### T5 — Integration

- [ ] Update `ifckit/__init__.py` to export types
- [ ] Document module in `ARCHITECTURE.md`

### T6 — Testing

- [ ] `tests/types/test_door.py`
- [ ] `tests/types/test_window.py`
- [ ] `tests/types/test_footprint.py`
- [ ] `tests/types/test_roundtrip.py`

## File Structure

```
ifckit/types/
├── __init__.py         # exports Door, Window, enums
├── enums.py            # DoorOperation, WindowOperation, WindowPartitioning
├── door.py            # Door class + create_type() + dataclass
├── window.py          # Window class + create_type() + dataclass
└── footprint.py      # 2D geometry generation
```

```
tests/types/
├── __init__.py
├── test_door.py
├── test_window.py
├── test_footprint.py
└── test_roundtrip.py
```

## Test Scenarios

| ID | Description |
|----|-------------|
| T1 | `Door.create_type()` returns valid `PendingDoorType` |
| T2 | `Window.create_type()` returns valid `PendingWindowType` |
| T3 | Door operation maps to correct FootPrint arc |
| T4 | Window partitioning maps to correct FootPrint |
| T5 | `to_dict()` → `from_dict()` roundtrips |
| T6 | Multiple operations generate correct arcs |

## Dependencies

- `ifckit.geometry` (Vec, Plane, Arc for FootPrint)
- `ifckit.elements.base` (PendingElement, RenderStyle)
- `ifcopenshell` (runtime, for optional direct entity)

No coupling to core builders — outputs integrate via pending types.

## Type Reuse Note

This module does NOT implement caching. Each call to `create_type()` creates a new entity. External caching is the user's responsibility:

```python
# User controls reuse
door_type_1 = Door.create_type(operation="SINGLE_SWING_LEFT")
door_type_2 = Door.create_type(operation="SINGLE_SWING_LEFT")
# → Two entities — user decides to reuse or not
```

This differs from the core's type reuse (M4) which is model-level.

## Exit Gates

- T1 Gate: enums match IFC4 spec
- T2 Gate: Door.create_type() roundtrips correctly  
- T3 Gate: Window.create_type() roundtrips correctly
- T4 Gate: FootPrint geometry correct for all operations
- T5 + T6 Gate: All tests pass
