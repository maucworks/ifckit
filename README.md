# ifckit

Framework-agnostic IFC builder library for architecture and infrastructure.

## What it is

`ifckit` lets you construct IFC files in pure Python.
It has one external dependency: `ifcopenshell`.
It knows nothing about Rhino, Grasshopper, FastAPI, or any other host.

Frontends (Grasshopper Python, FastAPI, CLI) are thin adapters that convert
their geometry types to `ifckit` primitives and call the library API.

## Supported schemas

- **IFC4** — buildings: walls, slabs, beams, columns
- **IFC4x3** — infrastructure: bridges, bridge parts, alignments

## Quick start

```python
from ifckit import IfcModel, IfcSchema, PendingWall, Vec, Plane, validate
from ifckit.builders import default_registry
from ifckit.builders._geom import get_body_context

# Build the spatial hierarchy
model = IfcModel(name="My Project", schema=IfcSchema.IFC4, author="you")
site  = model.add_site("Site A")
bldg  = model.add_building(site, "Building 1")
floor = model.add_storey(bldg, "Ground Floor", elevation=0.0)

# Define the element
wall = PendingWall(
    footprint=[Vec(0, 0, 0), Vec(10, 0, 0), Vec(10, 0.3, 0), Vec(0, 0.3, 0)],
    plane=Plane.world_xy(),
    height=3.0,
    name="North Facade",
)

# Validate, then build into the IFC file
result = validate(wall)
assert result.ok, result.errors

reg = default_registry()
ctx = get_body_context(model.ifc_file)
reg.get("basic_wall").build(model.ifc_file, wall, floor.entity, ctx)

model.save("output/project.ifc")
```

See `examples/quickstart.py` for the full runnable version.

## Installation

```bash
pip install ifckit          # once published
# or locally:
pip install -e ".[dev,api]"
```

## Development

```bash
make env          # create .venv + install all extras
make test         # run tests with coverage
make test-fast    # run tests, stop on first failure
make api          # start FastAPI dev server  →  http://127.0.0.1:8000/docs
make lint         # ruff check
make fmt          # ruff format + auto-fix
make help         # list all targets
```

Or directly with pytest / ruff:

```bash
pytest                                          # run tests
pytest --cov=ifckit --cov-report=term-missing  # with coverage
ruff check ifckit/                              # lint
```

See `PLAN.md` for the full milestone implementation plan.
