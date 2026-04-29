# ifckit — Design Document

## Purpose

`ifckit` is a Python library for authoring IFC files. It targets the preliminary and schematic design phases (LOD 100–200): massing, structural skeleton, alignment geometry, and parametric assemblies. The consumer is a designer or engineer writing Python, not a BIM technician filling out a schema by hand.

The library has one runtime dependency: `ifcopenshell`. Everything else — geometry primitives, validation, pending element data — is pure Python.

---

## Problem Statement

`ifcopenshell` is excellent at what it was built for: parsing, converting, and querying IFC files. Authoring is a secondary concern. Writing a valid IFC wall with correct geometry, unit assignment, spatial containment, owner history, and body context requires twenty or more API calls and a working knowledge of the IFC entity graph. The `ifcopenshell.api` module reduces some of that burden, but the mental model it demands is still the IFC schema, not the designer's intent.

`ifckit` inverts this. The designer expresses intent in Python terms. The library translates that intent into the correct IFC entity graph. The IFC schema is an implementation detail, not the interface.

---

## Design Principles

**Separation of data and construction.** A `PendingElement` is a plain Python dataclass. No `ifcopenshell` import, no IFC knowledge, no side effects. It can be created, inspected, serialized, and validated without touching a file. Construction — the translation to IFC entities — happens in a `Builder`, only when explicitly requested.

**Validation before construction.** The validator catches structural errors before any IFC entity is created. A zero-length beam axis, a degenerate profile, a misaligned alignment segment — all raise `ValueError` from `model.add()`, not buried deep in an `ifcopenshell` stack trace.

**Framework agnosticism.** The geometry layer owns its own types: `Vec`, `Plane`, `Line`, `Arc`, `Polyline`, `Path`. No numpy, no Rhino, no Shapely. Host applications (Grasshopper, FastAPI, Three.js, a CLI script) are thin adapter layers that convert their native geometry to `ifckit` primitives. The library does not know and does not care which host is calling it.

**One schema, two dialects.** Buildings use IFC4. Infrastructure uses IFC4X3. Both are supported in the same library. The `IfcModel` chooses the schema at construction time. Element types that belong only to IFC4X3 (bridges, alignments) raise a schema mismatch error if called on an IFC4 model.

**Handle chaining.** The spatial hierarchy is built through fluent method calls on handle objects. Adding a building to a site returns a `BuildingHandle`. Adding a storey to that handle returns a `StoreyHandle`. Elements are added to handles, not to the model directly. The pattern is readable, the coupling is explicit, and the hierarchy is enforced at the call site.

```python
floor = model.add_site("S").add_building("B").add_storey("Ground Floor")
floor.add(PendingBeam(axis, profile, name="Girder"))
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                          HOST APPLICATIONS                       │
│  Grasshopper / Rhino   FastAPI service   Three.js   CLI script   │
│  convert native geometry to ifckit primitives, call model.add()  │
└────────────────────────────┬─────────────────────────────────────┘
                             │  Vec, Plane, Line, Arc, Path, …
┌────────────────────────────▼─────────────────────────────────────┐
│                            ifckit                                │
│                                                                  │
│  geometry/      Vec  Plane  Line  Arc  Polyline  Path            │
│                 Alignment (planned)                               │
│                 parallel_transport_frames()                       │
│                                                                  │
│  elements/      PendingWall  PendingSlab                         │
│                 PendingExtrudedElement                            │
│                   PendingBeam  PendingColumn                     │
│                 PendingSweptBeam  PendingRevolvedBeam             │
│                 PendingBridge  PendingBridgePart                  │
│                 PendingAlignment                                  │
│                 PendingLoftedBeam (planned)                       │
│                 PendingPier  PendingAbutment (planned)            │
│                                                                  │
│  profiles/      IBeamProfile  LBeamProfile                       │
│                 BoxGirderProfile  TBeamProfile (planned)          │
│                                                                  │
│  builders/      ExtrudedElementBuilder  SweptElementBuilder      │
│                 WallBuilder  SlabBuilder  RevolvedBeamBuilder     │
│                 AlignmentBuilder                                  │
│                 LoftedBeamBuilder (planned)                       │
│                                                                  │
│  validator.py   validate(pending) → ValidationResult             │
│  model.py       IfcModel  Handle  StoreyHandle  BridgePartHandle  │
│  schema.py      IfcSchema  LengthUnit                            │
└────────────────────────────┬─────────────────────────────────────┘
                             │  ifcopenshell
                             ▼
                       .ifc file / string
```

### Layer responsibilities

**`geometry/`** — Framework-agnostic primitives. No IFC knowledge. Pure math. `Vec` is a 3D vector with operator overloads (`+`, `-`, `*`, `@` for dot, `**` for cross). `Plane` is a right-handed frame (origin, x\_axis, y\_axis; z\_axis derived). `Line`, `Arc`, and `Path` carry geometric length as a `@property`. `Path` composes `Line` and `Arc` segments into a G1-continuous curve. `parallel_transport_frames()` propagates rotation-minimizing frames along a `Path` (Bishop frames), used for swept solid orientation.

**`elements/`** — Data containers. Each `PendingElement` subclass declares `element_type: str` as a class variable used by the builder registry for dispatch. No ifcopenshell import. Subclasses are serializable to/from plain dicts for JSON transport across process boundaries (FastAPI, Grasshopper scripting).

**`profiles/`** — Parametric cross-section generators. A profile class produces a list of `Vec` points in the local XY plane (X = horizontal, Y = vertical up). The profile is closed and wound counter-clockwise. Profile classes do not create IFC entities.

**`builders/`** — One builder class per element family. Each implements `build(ifc_file, pending, container, context) → IfcEntity`. The `BuilderRegistry` maps `element_type` strings to builder instances. `default_registry()` returns a pre-populated registry with all built-in builders. Custom builders can be registered for project-specific element types.

**`validator.py`** — All structural validation. Validators run before any IFC entity is created. They return a `ValidationResult(ok, errors, warnings)`. `model.add()` raises `ValueError` on errors and emits `warnings.warn()` on warnings.

**`model.py`** — The public authoring surface. `IfcModel` owns an `ifcopenshell.file`, a `BuilderRegistry`, and the spatial hierarchy. Handles wrap IFC spatial structure entities and expose fluent child-creation methods. The raw `ifc_file` is accessible for callers who need to drop down to ifcopenshell directly.

---

## Geometry Layer

### Vec

A 3D vector and point type. Supports:

```python
a + b          # addition
a - b          # subtraction
a * scalar     # scale
a @ b          # dot product
a ** b         # cross product
abs(a)         # length
a.normalized() # unit vector
a.equals(b, tol=1e-6)
a.rotate_around(axis, angle)  # Rodrigues
```

The same type serves as both point and vector. No separate `Point3` class. This matches how IFC represents geometry internally.

### Plane

A right-handed coordinate frame: `origin`, `x_axis`, `y_axis`. `z_axis` is derived as `x_axis × y_axis`. Used for local placements, clip planes, and profile orientation.

Construction helpers:
- `Plane.world_xy()` — standard XY plane at origin
- `Plane.from_origin_and_normal(origin, normal)` — derives x and y from the normal
- `Plane.from_tangent(origin, tangent, world_up)` — frame for beam placement along a path

### Line, Arc

`Line` is a finite segment with `start`, `end`, `direction`, `length`, `midpoint`.

`Arc` is a circular arc defined by `center`, `normal`, `start`, `angle` (radians, signed). `end`, `radius`, `length`, `tangent_at_start()`, `tangent_at_end()` are all derived. Arc is right-handed: positive angle sweeps counter-clockwise around the normal.

Both expose `length` as a `@property`. This uniformity matters for the validator and for any code that processes a mixed sequence of segments.

### Path

A G1-continuous path of `Line` and `Arc` segments. Built incrementally:

```python
path = Path().add_line(a, b).add_arc(center, normal, start, angle)
```

`path.length` — total arc length (property).
`path.start_tangent()` / `path.end_tangent()` — return `Optional[Vec]`; `None` for empty paths.
`path.sample(angle_step_deg)` — returns a `Polyline` approximation.

`Path` is a generic geometric type. It is used for swept beam paths today. The planned `Alignment` type (see below) will extend or wrap `Path` with stationing semantics.

### Alignment (planned)

A bridge alignment carries more than geometry. It has stationing: a scalar chainage along the curve from which element positions are derived. The current `Path` does not support this.

The planned `Alignment` type will provide:

```python
alignment.point_at(chainage) -> Vec
alignment.tangent_at(chainage) -> Vec
alignment.normal_at(chainage) -> Vec   # horizontal normal (superelevation reference)
alignment.frame_at(chainage) -> Plane  # full 3D frame
```

The design decision is to keep `Path` as a pure geometric type and introduce `Alignment` as a separate class that owns a horizontal `Path`, an optional vertical profile (gradient + parabolic curves), and a start chainage. This keeps `Path` simple and lets `Alignment` carry the infrastructure-specific semantics without polluting the geometry layer.

The `IfcAlignment` builder will then produce both `IfcAlignmentHorizontal` and `IfcAlignmentVertical` sub-entities from the single `Alignment` object.

---

## Element Layer

### Hierarchy

```
PendingElement (ABC)
├── PendingExtrudedElement
│   ├── PendingBeam         element_type = "basic_beam"
│   └── PendingColumn       element_type = "basic_column"
├── PendingSweptBeam        element_type = "swept_beam"
├── PendingRevolvedBeam     element_type = "revolved_beam"
├── PendingWall             element_type = "basic_wall"
├── PendingSlab             element_type = "basic_slab"
├── PendingBridge           element_type = "bridge"
├── PendingBridgePart       element_type = "bridge_part"
├── PendingAlignment        element_type = "alignment"
└── PendingLoftedBeam       element_type = "lofted_beam"  [planned]
```

`element_type` is a plain class variable. The builder registry uses it for dispatch. Subclasses that omit it will raise `AttributeError` at construction time.

### PendingExtrudedElement

The shared base for `PendingBeam` and `PendingColumn`. Holds `axis` (a `Line`), `profile` (a list of `Vec`), `up` (optional guide-up vector), `start_clip` and `end_clip` (optional `Plane` objects for miter cuts). `PendingBeam` adds `ref_line` for web orientation. `PendingColumn` adds nothing beyond the base.

The profile is drawn in the local XY plane: X is horizontal relative to the beam direction, Y is vertical up. `_coerce_profile()` accepts `Vec` objects, `(x, y)` tuples, `(x, y, z)` tuples, or any object with a `get_profile_points()` method.

### PendingSweptBeam

A beam swept along a `Line`, `Arc`, or `Path` directrix using `IfcFixedReferenceSweptAreaSolid`. The `up` vector steers the profile Y axis along the sweep. If `up` is `None`, it defaults to world `+Z` (or `+Y` for near-vertical paths).

### PendingLoftedBeam (planned)

A beam with a varying cross-section along its path. Takes a list of `(chainage, profile)` pairs. Maps to `IfcSectionedSolidHorizontal` in IFC4X3. This is the correct entity for haunched girders and widening deck slabs.

```python
lofted = PendingLoftedBeam(
    path=alignment_path,
    sections=[
        (0.0,  box_girder_2m),
        (15.0, box_girder_3m),
        (30.0, box_girder_2m),
    ],
    name="Main Girder",
)
```

### PendingPier / PendingAbutment (planned)

Semantic wrappers around extruded elements with the correct IFC class (`IfcColumn` with predefined type `PIER` or `ABUTMENT` in IFC4X3). Placed relative to an alignment station and a transverse offset. The placement logic depends on the `Alignment.frame_at(chainage)` method.

---

## Profile Layer

Profile classes produce a closed, counter-clockwise list of `Vec` points in local XY (X = horizontal, Y = vertical up). They carry no IFC knowledge.

### IBeamProfile

Parametric wide-flange I-section. Parameters: `total_height`, `top_flange_width`, `top_flange_thickness`, `web_thickness`, `bottom_flange_width`, `bottom_flange_thickness`. Returns 12 points.

### LBeamProfile

Parametric L-section (angle). Parameters: `width`, `height`, `thickness`.

### Planned profiles

| Class | IFC use |
|---|---|
| `BoxGirderProfile` | Closed rectangular hollow for bridge box girders |
| `TBeamProfile` | Precast T-beam, common in bridge decks |
| `UBeamProfile` | Precast U-beam / trough section |
| `VoidedSlabProfile` | Slab with circular voids, for precast bridge decks |
| `CompositeProfile` | Steel section + concrete haunch (for composite bridges) |

All are constructable from structural catalog parameters and produce a single list of `Vec` points. Composite profiles may produce multiple closed loops (outer + voids), which maps to `IfcArbitraryProfileDefWithVoids` in IFC.

---

## Builder Layer

### Protocol

```python
class IIfcBuilder(Protocol):
    entity_type: str
    def build(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance: ...
```

`entity_type` is the registry key. `build()` is called with the raw ifcopenshell file, the pending data, the IFC spatial container (storey, bridge part, etc.), and the body geometry context.

### Registry

`BuilderRegistry` maps `entity_type` strings to builder instances. `get()` raises `KeyError` on missing types. `register()` adds or replaces a builder. `default_registry()` returns a pre-populated instance.

Custom builders can be registered for project-specific element types without modifying the library:

```python
registry = default_registry()
registry.register(MyCustomGirderBuilder())
model = IfcModel(name="...", registry=registry)
```

### ExtrudedElementBuilder

Builds `PendingBeam` or `PendingColumn` using `IfcExtrudedAreaSolid`. The cross-section frame is constructed from the beam axis and the up vector. Clip planes are expressed as `IfcBooleanClippingResult` against `IfcHalfSpaceSolid` boundaries.

The `ObjectPlacement` encodes the full frame: local Z is the extrusion direction, local Y is the resolved up direction, local X is their cross product.

### SweptElementBuilder

Builds `PendingSweptBeam` using `IfcFixedReferenceSweptAreaSolid`. The directrix is built from a `Line`, `Arc`, or `Path`. The geometry lives in world coordinates; the `ObjectPlacement` is the world origin relative to the container. Clip planes work the same way as in `ExtrudedElementBuilder` but in world space.

### AlignmentBuilder

Builds `PendingAlignment` using `IfcAlignment` with `IfcAlignmentHorizontal` and `IfcAlignmentSegment` sub-entities. Supports `LINE` and `CIRCULARARC` segment types. Vertical alignment and cant are not yet implemented.

### LoftedBeamBuilder (planned)

Builds `PendingLoftedBeam` using `IfcSectionedSolidHorizontal`. Takes the directrix curve and a list of `(parameter, profile)` pairs. This is an IFC4X3-only entity.

---

## Model Layer

### IfcModel

Owns the `ifcopenshell.file`, a `BuilderRegistry`, and the IFC project root. Created once per authoring session:

```python
model = IfcModel(
    name="Westgate Bridge",
    schema=IfcSchema.IFC4X3,
    author="J. Engineer",
    unit=LengthUnit.METRE,
)
```

Supported units: `METRE`, `MILLIMETRE`. `FOOT` and `INCH` are defined for unit conversion utilities but are not supported for `IfcModel` construction (no imperial scaling in builders).

### Spatial hierarchy

IFC4:
```
IfcProject → IfcSite → IfcBuilding → IfcBuildingStorey → elements
```

IFC4X3:
```
IfcProject → IfcSite → IfcBridge → IfcBridgePart → elements
                     → IfcAlignment
```

Each level is wrapped in a `Handle` subclass: `SiteHandle`, `BuildingHandle`, `StoreyHandle`, `BridgeHandle`, `BridgePartHandle`, `AlignmentHandle`, `EntityHandle`. Handles expose child-creation methods that return the next handle type. `EntityHandle` wraps a leaf element and exposes only `.entity`.

### model.add()

The primary authoring method:

```python
handle = storey.add(pending)
```

Sequence:
1. Validate `pending` — raise `ValueError` on errors, `warnings.warn()` on warnings
2. Look up builder by `pending.element_type` — raise `LookupError` if missing
3. Call `builder.build(ifc_file, pending, container.entity, body_context)`
4. Return `EntityHandle`

### model.export()

Writes the model to a file, inferring format from extension:

| Extension | Format |
|---|---|
| `.ifc` | IFC STEP (delegates to `save()`) |
| `.obj` | Wavefront OBJ + `.mtl` sidecar |
| `.glb` / `.gltf` | Binary / text glTF |
| `.svg` | SVG floor plan projection |
| `.dae` | Collada |
| `.ttl` | RDF/Turtle (IFC-LBD) |

Geometry export formats require `ifcopenshell.geom`. The method writes a temporary IFC file, runs the geometry iterator over it, feeds the result to the serializer, then deletes the temp file. This is a necessary workaround: ifcopenshell serializers require the file they open internally, not an independently constructed `ifcopenshell.file` object.

---

## Validation

The validator is invoked by `model.add()` before any IFC entity is created. It can also be called directly:

```python
result = validate(pending)
if not result.ok:
    print(result.errors)
```

### Rules (current)

| Element | Errors | Warnings |
|---|---|---|
| Wall / Slab | footprint ≥ 3 points, height / thickness > 0, plane axes not collinear | footprint area < threshold |
| Beam / Column | axis length > 1e-6, profile ≥ 3 points, profile area > 0, up not parallel to axis | axis very short, profile very small |
| SweptBeam | path length > 1e-6, profile ≥ 3 points, profile area > 0 | path very short |
| RevolvedBeam | arc angle ≠ 0, profile ≥ 3 points | small angle |
| Alignment | ≥ 1 segment, consecutive segments share endpoints within tolerance | |
| Bridge | bridge has a name, ≥ 1 part | |

---

## Adapter Pattern

Host applications are thin adapters. They convert native geometry to `ifckit` primitives, construct pending elements, and call `model.add()`. They do not touch ifcopenshell directly.

### Grasshopper

```python
# In a GHPython component
import rhinoscriptsyntax as rs
from ifckit.geometry import Vec, Line
from ifckit import PendingBeam

def rg_point_to_vec(pt):
    return Vec(pt.X, pt.Y, pt.Z)

axis = Line(rg_point_to_vec(start), rg_point_to_vec(end))
beam = PendingBeam(axis, profile_points, name=name)
handle = storey_handle.add(beam)
```

### FastAPI

```python
class BeamInput(BaseModel):
    start: list[float]
    end: list[float]
    profile: list[list[float]]
    name: str = ""

@router.post("/storeys/{storey_id}/beams")
def add_beam(storey_id: str, body: BeamInput):
    axis = Line(Vec(*body.start), Vec(*body.end))
    profile = [Vec(*p) for p in body.profile]
    pending = PendingBeam(axis, profile, name=body.name)
    try:
        handle = storey_handles[storey_id].add(pending)
    except ValueError as e:
        raise HTTPException(422, detail=str(e))
    return {"entity_id": handle.entity.id()}
```

### Three.js / web frontend

The web frontend does not call `ifckit` directly. A FastAPI service owns the model. The frontend sends geometry as JSON, the service constructs pending elements and calls `model.add()`, and the output IFC is served as a download or streamed to a viewer via the `model.export()` path.

---

## IFC4X3 Bridge Hierarchy

```
IfcProject
└── IfcSite
    ├── IfcAlignment
    │   └── IfcAlignmentHorizontal
    │       └── IfcAlignmentSegment (LINE / CIRCULARARC)
    └── IfcBridge
        └── IfcBridgePart (DECK / SUBSTRUCTURE / SUPERSTRUCTURE / FOUNDATION)
            ├── IfcBeam          (girders, cross-beams)
            ├── IfcSlab          (deck slab)
            ├── IfcColumn        (piers)
            └── IfcPlate         (steel plates, stiffeners)
```

Spatial containment uses `IfcRelContainedInSpatialStructure`. Aggregation (bridge → parts) uses `IfcRelAggregates`. The alignment is aggregated under the site, not under the bridge.

### Planned: linear placement

`IfcLinearPlacement` places an element relative to an alignment at a given chainage, lateral offset, and height. This is how piers, bearings, and expansion joints are positioned in IFC4X3. The current implementation uses `IfcLocalPlacement` with world coordinates. Linear placement will require the `Alignment.frame_at(chainage)` method described above.

---

## Planned Work (priority order)

### 1. Alignment with stationing

Add `Alignment` as a dedicated class wrapping a horizontal `Path` and an optional vertical profile. Implement `point_at`, `tangent_at`, `normal_at`, `frame_at` by arc-length parameterization. This unlocks programmatic placement of all bridge elements relative to the bridge centerline.

### 2. Vertical alignment

Add `VerticalAlignment` with gradient segments and parabolic transition curves. Combine with horizontal alignment to produce a full 3D space curve. Required for correct girder geometry on bridges with significant grade or sag curves.

### 3. PendingLoftedBeam / IfcSectionedSolidHorizontal

Variable cross-section along a path. Takes `(chainage, profile)` pairs. Correct IFC entity for haunched girders, widening decks, and tapered piers.

### 4. Profile library expansion

Box girder, T-beam, U-beam, voided slab. All follow the existing `get_profile_points()` pattern and are testable independently of IFC.

### 5. PendingPier / PendingAbutment

Semantic wrappers with correct IFC predefined types. Placed at alignment stations.

### 6. Property sets

Assign `IfcPropertySet` to elements: material, structural properties, cost data. The `model.add()` return handle should expose an `assign_pset(name, properties)` method.

### 7. Type objects

`IfcBeamType`, `IfcColumnType`, etc. allow many elements to share a single type definition. Important for large parametric assemblies (a bridge with 200 identical precast beams should reference one type, not carry 200 duplicate property sets).

---

## What ifckit is not

A read/parse library. `model.ifc_file` is accessible for callers who need to inspect or modify an existing file, but `ifckit` itself provides no query API for reading IFC. That remains `ifcopenshell`'s domain.

A geometry kernel. `Vec`, `Plane`, `Line`, `Arc`, and `Path` cover what is needed for IFC authoring at LOD 100–200. For NURBS surfaces, boolean operations, or mesh generation, the caller should use a dedicated geometry library and convert results to `ifckit` primitives at the adapter boundary.

A full schema wrapper. The library covers the element types needed for preliminary building and infrastructure design. Coverage is intentionally selective. Callers who need an element type not yet in `ifckit` can drop to `model.ifc_file` and use `ifcopenshell` directly, or register a custom builder.

---

## Dependencies

| Package | Role | Required |
|---|---|---|
| `ifcopenshell` | IFC file construction and geometry export | yes |
| `pytest` | test runner | dev |
| `pytest-cov` | coverage | dev |
| `ruff` | linter and formatter | dev |
| `mypy` | static type checking | dev |
| `fastapi` + `uvicorn` | HTTP adapter example | optional |

No numpy. No scipy. No geometry kernel. The standard library and `ifcopenshell` are the only runtime dependencies.

---

## Coverage Targets

| Module | Target |
|---|---|
| `geometry/` | 100% |
| `elements/` | 100% |
| `profiles/` | 100% |
| `validator.py` | 100% |
| `schema.py` | 100% |
| `builders/` | ≥ 90% |
| `model.py` | ≥ 90% |
| **Overall** | **≥ 95%** |

Uncovered lines carry `# pragma: no cover` with an explicit comment.
