# ifckit — Implementation Plan

## Vision

`ifckit` is a framework-agnostic Python library for constructing IFC files.
It has one external dependency: `ifcopenshell`.
It knows nothing about Rhino, Grasshopper, FastAPI, or any other frontend.

Frontends (Grasshopper Python, FastAPI, CLI) are thin adapters that convert
their own geometry types to `ifckit` primitives and call the library API.

```
┌─────────────────────────────────────────────────────────────────────┐
│                           FRONTENDS                                 │
│  GH Python node   │  FastAPI endpoint  │  CLI script  │  pytest     │
│  rg → primitives  │  JSON → primitives │  dict input  │  direct     │
└─────────┬─────────┴────────┬───────────┴──────────────┴────────────┘
          │                  │   ifckit primitives (Vec, Plane, …)
┌─────────▼──────────────────▼───────────────────────────────────────┐
│                          ifckit                                     │
│                                                                     │
│  geometry/     Vec, Plane, Line, Arc, Polyline, Path           │
│  elements/     PendingWall, PendingBeam, PendingSlab, …             │
│                PendingBridge, PendingBridgePart, PendingAlignment   │
│  builders/     per-type ifcopenshell entity construction            │
│  model.py      IfcModel: hierarchy, IFC4 + IFC4x3, export          │
│  validator.py  structural validation of pending elements            │
│  schema.py     IFC schema version management (IFC4 / IFC4x3)       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │  ifcopenshell
                               ▼
                         .ifc file / string
```

---

## Repository Structure (target)

```
L140-py-ifckit/
├── ifckit/
│   ├── __init__.py              public API surface
│   ├── schema.py                IFC4 / IFC4x3 schema switching
│   ├── model.py                 IfcModel: hierarchy + export
│   ├── validator.py             PendingElement validation
│   ├── geometry/
│   │   └── __init__.py          Vec, Plane, Line, Arc, Polyline, Path
│   │                            parallel_transport_frames()
│   ├── elements/
│   │   ├── __init__.py          re-exports all pending types
│   │   ├── building.py          PendingWall, PendingSlab
│   │   ├── structural.py        PendingBeam, PendingColumn, PendingRevolvedBeam
│   │   └── bridge.py            PendingBridge, PendingBridgePart,
│   │                            PendingAlignment, PendingAlignmentSegment
│   └── builders/
│       ├── __init__.py          BuilderRegistry
│       ├── base.py              IIfcBuilder protocol
│       ├── wall.py              WallBuilder
│       ├── slab.py              SlabBuilder
│       ├── beam.py              BeamBuilder
│       ├── column.py            ColumnBuilder
│       ├── revolved_beam.py     RevolvedBeamBuilder
│       └── bridge.py            BridgeBuilder, BridgePartBuilder,
│                                AlignmentBuilder
├── tests/
│   ├── conftest.py              shared fixtures
│   ├── geometry/
│   │   ├── test_vec3.py
│   │   ├── test_plane.py
│   │   ├── test_curves.py       Line, Arc, Polyline, Path
│   │   └── test_frames.py       parallel_transport_frames
│   ├── elements/
│   │   ├── test_building.py     PendingWall, PendingSlab
│   │   ├── test_structural.py   PendingBeam, PendingColumn
│   │   └── test_bridge.py       PendingBridge, PendingAlignment
│   ├── builders/
│   │   ├── test_wall_builder.py
│   │   ├── test_beam_builder.py
│   │   └── test_bridge_builder.py
│   ├── test_model.py            IfcModel full hierarchy round-trips
│   ├── test_validator.py        validation rules
│   └── ifc/
│       └── test_ifc_output.py   parse output .ifc with ifcopenshell,
│                                check entity counts, hierarchy, geometry
├── docs/
│   ├── architecture.md          this diagram in detail
│   ├── ifc4x3_bridge.md         IFC4x3 bridge entity notes
│   └── adapters.md              how to write a frontend adapter
├── pyproject.toml
├── PLAN.md                      this file
├── CHANGELOG.md
└── README.md
```

---

## Milestones

### M0 — Scaffold  ✅ DONE
**Commit:** `chore: scaffold project structure and geometry primitives`

---

### M1 — Geometry layer complete  ✅ DONE (99 tests, 100% coverage)
**Commit:** `feat(geometry): geometry tests at 100% coverage (M1)`

---

### M2 — Elements layer  ✅ DONE (63 tests, 100% coverage)
**Commit:** `feat(elements): PendingWall, Slab, Beam, Column, RevolvedBeam, Bridge, Alignment (M2)`

---

### M3 — Model + Schema layer  ✅ DONE (41 tests, 100% coverage)
**Commit:** `feat(schema,model): IfcSchema, LengthUnit, IfcModel IFC4+IFC4X3 hierarchy (M3)`

---

### M4 — Builders layer  ✅ DONE (259 tests total, 100% builders coverage)
**Commit:** `feat(builders): builder protocol, registry, and all element builders (M4)`

Builders implemented:
- `IIfcBuilder` protocol + `BuilderRegistry`
- `_geom.py`: low-level helpers (pt2/pt3/dir3, profiles, extrude, placement)
- `WallBuilder`, `SlabBuilder`
- `BeamBuilder`, `ColumnBuilder`, `RevolvedBeamBuilder`
- `AlignmentBuilder` (IFC4X3)

---

### M5 — Validator  ✦ target: 1 commit
*Goal: all structural errors caught before ifcopenshell is called.*

- [x] `validate(pending) -> ValidationResult(ok, errors, warnings)`
- [x] Per-type rules:
  - Wall/Slab: footprint closed, plane valid, height > 0
  - Beam/Column: axis length > tol, profile closed
  - RevolvedBeam: arc angle != 0, profile closed
  - Alignment: at least 1 segment, consecutive segments share endpoints
  - Bridge: at least 1 part, all parts valid
- [x] Tests: `tests/test_validator.py`
  - valid element passes
  - each invalid condition triggers correct error message
  - warnings for near-degenerate geometry (very short axis, tiny profile)

**Commit:** `feat(validator): structural validation for all pending types` ✅

---

### M6 — Public API + IFC output tests  ✦ target: 1–2 commits
*Goal: clean public API, integration tests that parse output IFC.*

#### M6.1 Public API surface
- [ ] `ifckit/__init__.py` exports:
  ```python
  from ifckit import (
      IfcModel, IfcSchema,
      PendingWall, PendingSlab, PendingBeam, PendingColumn,
      PendingRevolvedBeam, PendingBridge, PendingBridgePart,
      PendingAlignment,
  )
  from ifckit.geometry import Vec, Plane, Line, Arc, Polyline, Path
  ```
- [ ] Docstrings on all public symbols

**Commit:** `feat: public API surface and docstrings`

#### M6.2 IFC output integration tests
- [ ] `tests/ifc/test_ifc_output.py` — each test:
  1. builds a model via `IfcModel` API
  2. calls `to_string()` or `save(tmp_path)`
  3. re-opens with `ifcopenshell.open()`
  4. asserts entity counts, relationship types, geometry presence
- [ ] Scenarios:
  - minimal IFC4 building: 1 wall, 1 slab, 1 storey
  - IFC4 multi-storey: 3 storeys, mixed elements
  - IFC4x3 bridge: 1 bridge, 2 parts, alignment with 2 segments
  - IFC4x3 bridge with beams placed along alignment

**Commit:** `test(ifc): integration tests for IFC4 and IFC4x3 output`

---

### M7 — Adapter examples  ✦ target: 1 commit
*Goal: show how frontends use the library.*

- [ ] `docs/adapters.md` — adapter pattern description
- [ ] `examples/grasshopper_adapter.py` — converts `rg.Line`, `rg.Arc`,
       `rg.Curve` to `ifckit` primitives; no actual Rhino import (pseudocode
       with comments)
- [ ] `examples/fastapi_adapter.py` — Pydantic models → `ifckit` primitives,
       `to_string()` as response body
- [ ] `examples/simple_building.py` — runnable example, no frontend
- [ ] `examples/simple_bridge.py` — IFC4x3 bridge, runnable

**Commit:** `docs: adapter examples for Grasshopper, FastAPI, and standalone`

---

## Commit Discipline

| When | Rule |
|---|---|
| After each milestone step | One focused commit per `feat/fix/test/docs/chore` |
| Never | Commit broken tests or failing build |
| Always | `pytest` green before commit |
| Commit message format | `type(scope): short description` (Conventional Commits) |
| Body | Only when the *why* is not obvious from the diff |
| Max subject length | 50 chars |

**Types:** `feat`, `fix`, `test`, `docs`, `chore`, `refactor`

**Scopes:** `geometry`, `elements`, `builders`, `model`, `validator`, `schema`, `ifc`

---

## Test Suite Coverage Targets

| Module | Target |
|---|---|
| `geometry/` | 100% — pure math, no excuses |
| `elements/` | 100% — dataclasses + round-trip |
| `validator.py` | 100% — every rule explicitly tested |
| `builders/` | ≥ 90% — ifcopenshell calls may have edge cases |
| `model.py` | ≥ 90% |
| `schema.py` | 100% |
| **Overall** | **≥ 95%** |

Coverage is measured with `pytest-cov`:
```bash
pytest --cov=ifckit --cov-report=term-missing
```

Uncovered lines must be explicitly `# pragma: no cover` with a comment
explaining why (e.g. defensive error branch that cannot be triggered from
public API).

---

## Test Fixture Strategy

```python
# tests/conftest.py
import pytest
import ifcopenshell

@pytest.fixture
def tmp_ifc_path(tmp_path):
    return str(tmp_path / "test.ifc")

@pytest.fixture
def ifc4_model():
    """Minimal IFC4 model with project + owner history."""
    from ifckit import IfcModel, IfcSchema
    return IfcModel(name="Test", schema=IfcSchema.IFC4, author="pytest")

@pytest.fixture
def ifc4x3_model():
    from ifckit import IfcModel, IfcSchema
    return IfcModel(name="Test", schema=IfcSchema.IFC4X3, author="pytest")

@pytest.fixture
def simple_wall():
    from ifckit import PendingWall
    from ifckit.geometry import Vec, Plane
    return PendingWall(
        footprint=[Vec(0,0,0), Vec(5,0,0), Vec(5,0.3,0), Vec(0,0.3,0)],
        plane=Plane.world_xy(),
        height=3.0,
        name="TestWall",
    )
```

IFC output tests parse the saved file with `ifcopenshell.open()` and use
helper assertions:

```python
def assert_entity_count(model, ifc_type, expected):
    entities = model.by_type(ifc_type)
    assert len(entities) == expected, (
        f"Expected {expected} {ifc_type}, found {len(entities)}"
    )

def assert_hierarchy(model, parent_type, child_type, rel_type="IfcRelAggregates"):
    rels = model.by_type(rel_type)
    assert any(
        isinstance(r.RelatingObject, model.schema(parent_type))
        and any(isinstance(c, model.schema(child_type)) for c in r.RelatedObjects)
        for r in rels
    )
```

---

## IFC4x3 Bridge Notes

Key entities (see `docs/ifc4x3_bridge.md` for full reference):

| ifckit concept | IFC4x3 entity |
|---|---|
| `PendingBridge` | `IfcBridge` |
| `PendingBridgePart` | `IfcBridgePart` (DECK / SUBSTRUCTURE / etc.) |
| `PendingAlignment` | `IfcAlignment` |
| `AlignmentSegment` (Line) | `IfcAlignmentHorizontalSegment` (LINE) |
| `AlignmentSegment` (Arc) | `IfcAlignmentHorizontalSegment` (CIRCULARARC) |
| Spatial decomposition | `IfcRelAggregates` |
| Element containment | `IfcRelContainedInSpatialStructure` |
| Linear placement | `IfcLinearPlacement` (optional, M5+) |

Hierarchy in IFC4x3:
```
IfcProject
  └─ IfcSite
      ├─ IfcAlignment          (the path)
      └─ IfcBridge
          └─ IfcBridgePart (DECK)
              └─ IfcBeam / IfcSlab / IfcPlate / …
```

---

## Dependencies

```toml
[project]
dependencies = ["ifcopenshell>=0.7.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0", "pytest-cov", "ruff", "mypy"]
```

No other runtime dependencies.
`Vec`, `Plane`, and all curve classes live inside `ifckit.geometry` —
they are not imported from any external geometry library.

---

## Definition of Done (per milestone)

A milestone is done when:
1. All checkboxes in the milestone are ticked
2. `pytest` passes with 0 failures, 0 errors
3. Coverage target for that module is met
4. Code passes `ruff check ifckit/`
5. Commit is made with the specified message

The overall library is done (v0.1.0) when M0–M6 are complete.
M7 (adapter examples) is v0.2.0.
