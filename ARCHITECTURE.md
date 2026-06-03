# ifckit Architecture

## Overview

ifckit is a framework-agnostic IFC builder library for architecture and infrastructure. It provides a clean separation between:
- **Data** - Plain Python objects representing IFC elements
- **Validation** - Geometry and structural checks
- **Building** - Conversion to ifcopenshell entities
- **Model** - IFC spatial hierarchy management

## Core Concepts

### Pending Elements

Pending elements are plain Python data containers with no external dependencies:

```python
from ifckit import PendingWall, Vec, Plane

wall = PendingWall(
    footprint=[Vec(0,0,0), Vec(1000,0,0), Vec(1000,200,0), Vec(0,200,0)],
    plane=Plane.world_xy(),
    height=3000,
    name="Exterior Wall"
)
```

All pending elements inherit from `PendingElement` which provides:
- `to_dict()` - Serialize to Python dict
- `to_json()` - Serialize to JSON string  
- `from_dict()` / `from_json()` - Deserialize

### Element Type Registry

All pending element types are automatically registered via metaclass:

```python
# Element types register themselves when defined
class PendingWall(PendingElement):
    element_type = "basic_wall"  # Auto-registered
```

The registry (`ElementRegistry`) provides:
- `get(type_str)` - Get class by type string
- `types()` - List all registered types
- Aliases (e.g., "beam" → "basic_beam")

## Module Structure

```
ifckit/
├── __init__.py           # Public API exports
├── __main__.py           # CLI entry point
├── model.py              # IfcModel, spatial hierarchy handles
├── handles.py            # SiteHandle, BuildingHandle, StoreyHandle, etc.
├── validator.py          # Validation with auto-registration
│
├── elements/
│   ├── base.py           # PendingElement base class (metaclass: RegisterElementType)
│   ├── registry.py       # ElementRegistry (auto-registration)
│   ├── building.py       # PendingWall, PendingSlab
│   ├── structural.py     # PendingBeam, PendingColumn
│   ├── bridge.py         # PendingBridge, PendingBridgePart, PendingAlignment
│   ├── space.py          # PendingSpace
│   ├── opening.py        # PendingOpening, PendingDoor, PendingWindow
│   ├── sectioned_spine.py# PendingSectionedSpine
│   ├── wall_graph.py     # PendingWallGraph
│   ├── style.py          # RenderStyle
│   └── types.py          # PendingTypeObject, PendingDoorType, PendingWindowType
│
├── components/
│   ├── __init__.py       # FillComponent ABC, COMPONENT_REGISTRY, evaluators
│   ├── bootstrap.py      # Component file-generation utilities
│   ├── materials.py      # Material presets
│   ├── HOWTO.md          # Usage guide
│   ├── json/             # JSON-preset component definitions
│   │   ├── door_flush.json
│   │   └── fixed_casement.json
│   └── pythonic/         # Pythonic component definitions
│       ├── curved_casement_component.py
│       ├── fixed_casement_component.py
│       ├── simple_door_component.py
│       └── simple_window_component.py
│
├── geometry/
│   ├── __init__.py       # Vec, Plane, Line, Arc, Polyline, Path, etc.
│   ├── primitives.py     # Vec, Plane, Line, Arc, Polyline
│   ├── curve.py          # Curve (NURBS spline helpers)
│   ├── surface.py        # Surface (NURBS surface helpers, patches)
│   ├── biarc.py          # Biarc fitting (solve_biarc, fit_biarcs)
│   ├── path.py           # Path assembly, PathType
│   ├── frames.py         # FrameField, transport_frames, fixed_ref_frames
│   ├── intersection.py   # Intersection helpers
│   ├── subdivision.py    # Catmull-Clark subdivision
│   └── transform.py      # Transform
│
├── profiles/
│   ├── __init__.py       # Profile, steel lookup (SteelProfile.from_name)
│   ├── base.py           # Profile ABC
│   ├── derived.py        # DerivedProfile, PolygonProfile, RoundedPolygonProfile
│   ├── shapes.py         # RectangleProfile, CircleProfile, HollowCircleProfile
│   ├── i_beam.py         # IBeamProfile
│   ├── l_beam.py         # LBeamProfile
│   ├── sections.py       # TShapeProfile, ZShapeProfile, CShapeProfile, etc.
│   ├── steel.py          # EN steel database lookup
│   └── anchor.py         # Profile anchor points
│
├── types/
│   ├── __init__.py       # Footprint, curves_to_ifc
│   ├── footprint.py      # 2D footprint / symbol primitives
│   └── ifc_curves.py     # Curve conversion utilities
│
├── builders/
│   ├── __init__.py       # BuilderRegistry, default_registry, public API
│   ├── base.py           # IIfcBuilder interface
│   ├── _geom.py          # Shared geometry helpers for builders
│   ├── wall.py           # WallBuilder
│   ├── wall_graph.py     # WallGraphBuilder
│   ├── slab.py           # SlabBuilder
│   ├── space.py          # SpaceBuilder
│   ├── extruded.py       # ExtrudedElementBuilder
│   ├── revolved_beam.py  # RevolvedBeamBuilder
│   ├── sectioned_spine.py# SectionedSpineBuilder
│   ├── tapered.py        # TaperedExtrusionBuilder
│   ├── door_window.py    # WindowBuilder, DoorBuilder
│   ├── opening.py        # OpeningBuilder
│   ├── bridge.py         # BridgeBuilder, BridgePartBuilder
│   ├── beam_factory.py   # build_beam convenience function
│   ├── component_graph.py# Component-graph-based building
│   ├── psets.py          # Property set helpers
│   └── types.py          # TypeObjectBuilder
│
├── schema/
│   └── __init__.py       # IfcSchema, LengthUnit enums, TessellationDetail
│
├── draw/
│   ├── __init__.py       # SVG generation from IFC
│   └── _svg.py           # SVG floorplan generation, symbol injection
│
├── bonsaikit.py          # Blender/Bonsai integration bridge (lazy-loaded as ifckit.bk)
├── rhinokit.py           # Rhino geometry conversion / SDK helpers (lazy-loaded as ifckit.rk)
├── json_build.py         # JSON → IFC build function (CLI/API entry point)
├── paper.py              # ISO 216 A-series paper sizes
├── preview.py            # Rhino preview without writing IFC
├── reload.py             # Live code reload for Grasshopper/Blender
├── rhino_import.py       # Import IFC into Rhino (meshes, SVG curves, spaces)
└── ...
```

## Auto-Registration Pattern

Both elements and validators use a registration pattern that requires no manual registration when adding new types:

### Elements (Metaclass)

```python
class PendingElement(metaclass=RegisterElementType):
    element_type: str  # Auto-registered on class definition
```

### Validators (Decorator)

```python
from ifckit.validator import register_validator, validate

@register_validator(PendingWall)
def _validate_wall(w: PendingWall) -> ValidationResult:
    # validation logic
    ...

# Usage
result = validate(wall)
```

## Adding New Element Types

1. Define the pending element class:
```python
class PendingNewElement(PendingElement):
    element_type = "new_element"
    # ... fields and methods
```

2. Implement `to_dict()` and `from_dict()`:
```python
def to_dict(self) -> Dict[str, Any]:
    d = super().to_dict()
    d["custom_field"] = self.custom_field
    return d

@classmethod
def from_dict(cls, d: Dict[str, Any]) -> "PendingNewElement":
    return cls(custom_field=d["custom_field"], ...)
```

3. Add a validator (optional but recommended):
```python
from ifckit.validator import register_validator

@register_validator(PendingNewElement)
def _validate_new_element(e: PendingNewElement) -> ValidationResult:
    # validation logic
    ...
```

4. Add a builder (required for IFC output):
```python
class NewElementBuilder(IIfcBuilder):
    def build(self, file, pending, container, ctx):
        # ifcopenshell API calls
        ...

# Register in ifckit/builders/__init__.py
registry.register(NewElementBuilder())
```

## Components System

ifckit provides a `FillComponent` system for parametric windows, doors, and other building
components that are too complex to express as simple extrusions.

### Architecture

```
components/
├── __init__.py           # FillComponent ABC, COMPONENT_REGISTRY
├── bootstrap.py          # Scaffold new component definitions
├── materials.py          # Material presets (glass, timber, etc.)
├── HOWTO.md              # Usage guide
├── json/                 # JSON-serialized component definitions
│   ├── door_flush.json
│   └── fixed_casement.json
└── pythonic/             # Pythonic component definitions
    ├── curved_casement_component.py
    ├── fixed_casement_component.py
    ├── simple_door_component.py
    └── simple_window_component.py
```

### Two Flavours

| | JSON | Pythonic |
|---|---|---|
| Storage | Declarative JSON with bounding-box math | Python classes, methods, arbitrary logic |
| Use case | Simple doors / fixed windows | Complex geometry (curved, multi-panel) |
| Registration | Loaded by `get_component()` | Auto-discovered from `pythonic/` folder |
| Evaluation | JSON → FillComponent at load time | Full Python execution |

### FillComponent Protocol

Every component subclasses `FillComponent` and implements:

- `evaluate(params) → EvaluatedComponent` — Compute geometry (sub-fill extrusions, voids, materials)
- `display_name()` / `description()` — Human-readable metadata
- `parameters()` — Exposed parameter definitions (width, height, etc.)

Components are consumed by `WindowBuilder` / `DoorBuilder` in `builders/door_window.py`.

## Profiles System

Cross-section profiles for structural elements (beams, columns) are defined in `profiles/`.

```
profiles/
├── __init__.py           # Public API: Profile, SteelProfile.from_name(), etc.
├── base.py               # Profile ABC (area, centroid, to_ifc, to_dict)
├── derived.py            # DerivedProfile, PolygonProfile, RoundedPolygonProfile
├── shapes.py             # RectangleProfile, CircleProfile, HollowCircleProfile
├── i_beam.py             # IBeamProfile
├── l_beam.py             # LBeamProfile
├── sections.py           # TShapeProfile, ZShapeProfile, CShapeProfile, TrapeziumProfile, CompositeProfile
├── steel.py              # EN 10365 steel section database + lookup
└── anchor.py             # Anchor-point positioning helpers
```

All profile classes have a unified API:
- `to_ifc(file)` — Create an IfcParameterizedProfileDef
- `to_dict()` / `from_dict()` — Serialization
- `area`, `centroid`, `bounding_box` — Geometric properties

Steel sections (IPE, HEA, HEB, etc.) are looked up by name:
```python
from ifckit import SteelProfile
profile = SteelProfile.from_name("IPE 300")
```

## Geometry Module

### Primitives (`geometry/primitives.py`)

```python
from ifckit import Vec, Plane, Line, Arc, Polyline

wall = PendingWall(
    footprint=[Vec(0,0,0), Vec(1000,0,0), Vec(1000,200,0), Vec(0,200,0)],
    plane=Plane.world_xy(),
    height=3000,
)
```

- `Vec` — 3D vector with arithmetic, rotation, projection
- `Plane` — Plane from origin + normal; `.world_xy()`, `.world_xz()`, `.world_yz()`
- `Line` — Ray with origin + direction; `.intersect_plane()`, `.project()`
- `Arc` — Circular arc (center, radius, start/end angles, orientation)
- `Polyline` — Segmented polyline with `.simplify()`

### Paths (`geometry/path.py`)

`Path` represents a spine/reference line for bridge and road elements. Supports path
classifiers (straight, arc, clothoid, cubic) via `PathType` enum.

```python
from ifckit import Path, PathType, classify_path
```

### NURBS Curves (`geometry/curve.py`)

`Curve` — NURBS curve representation for complex alignments and non-linear elements.
Supports `.evaluate()`, `.derivative()`, `.to_ifc()`.

### Biarcs (`geometry/biarc.py`)

Biarc fitting (G1-continuous arc pairs through points with tangents):
```python
from ifckit import solve_biarc, fit_biarcs
```

### Surfaces (`geometry/surface.py`)

`Surface` — NURBS surface representation for complex geometry (bridge decks,
roofs, terrain patches). Supports `.evaluate(u, v)`, `.to_ifc()`.

### Frame Fields (`geometry/frames.py`)

`FrameField` generates transport frames along a path for reinforcement and
parametric cross-section placement:
- `transport_frames(path, sections)` — Constant-reference frames
- `fixed_ref_frames(path, sections, up)` — Fixed-up-vector frames
- `upvector_frames(path, sections)` — Swept frames

### Transforms (`geometry/transform.py`)

`Transform` — Affine 3D transformation (translation, rotation, scale, shear)
matrix with inversion, composition, and IFC export.

### Other Modules

- `geometry/intersection.py` — Curve/plane intersection helpers
- `geometry/subdivision.py` — Catmull-Clark subdivision surface extraction

## JSON Workflow

ifckit supports a complete JSON → IFC workflow:

```python
# Build from JSON
from ifckit import build_from_json, validate_json

# Validate
result = validate_json(project_dict)
if result.ok:
    model = build_from_json(project_dict, "output.ifc")

# CLI
# ifckit build input.json -o output.ifc
```

JSON Schema:
```json
{
  "ifc_version": "IFC4",
  "project": {"name": "...", "author": "..."},
  "unit": "MILLIMETRE",
  "site": {"name": "..."},
  "buildings": [{
    "name": "...",
    "storeys": [{
      "name": "Ground Floor",
      "elevation": 0.0,
      "elements": [
        {"type": "basic_wall", "data": {...}}
      ]
    }]
  }]
}
```

Elements are resolved via `ElementRegistry`, so any registered `element_type` string
(including components) can appear in JSON.

## Integration Modules

### Rhinokit (`rhinokit.py`)

Lazy-loaded as `ifckit.rk`. Rhino API helpers for geometry conversion
(Rhino.Geometry → ifckit Vec/Plane/Curve, and vice versa). Used in
Grasshopper components and Rhino scripts.

### Bonsaikit (`bonsaikit.py`)

Lazy-loaded as `ifckit.bk`. Blender/Bonsai integration bridge for
geometry extraction and IFC manipulation in the Blender environment.

### Preview (`preview.py`)

Generates Rhino preview meshes from pending elements without writing an
IFC file — useful for Grasshopper real-time feedback.

### Bonsai IFC Import (`rhino_import.py`)

Import IFC geometry into Rhino: meshes, SVG-curve annotations, and spaces.

### Draw (`draw/`)

IFC → SVG floorplan generation using `ifcopenshell.draw`. Used for
annotated 2D output.

## Design Principles

1. **No external dependencies in data classes** — Pending elements work without Rhino, ifcopenshell, etc.
2. **Auto-registration** — New element types require minimal boilerplate
3. **Clear separation** — Model doesn't know about geometry; validators don't know about IFC
4. **Python-first** — No code generation; pure Python data structures
5. **Schema flexibility** — IFC4 and IFC4X3 support via schema enum
6. **Component-based** — Complex building products (windows, doors) are defined composably via FillComponent
7. **Profile-driven** — Structural cross-sections are reusable profile objects with steel database lookup