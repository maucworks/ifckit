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
from ifckit import IfcModel, IfcSchema, PendingWall
from ifckit.geometry import Vec, Plane

model = IfcModel(name="My Project", schema=IfcSchema.IFC4, author="you")
site  = model.add_site("Site A")
bldg  = model.add_building(site, "Building 1")
floor = model.add_storey(bldg, "Ground Floor", elevation=0.0)

wall = PendingWall(
    footprint=[Vec(0,0,0), Vec(10,0,0), Vec(10,0.3,0), Vec(0,0.3,0)],
    plane=Plane.world_xy(),
    height=3.0,
    name="North Facade",
)
model.add_element(floor, wall)
model.save("/output/project.ifc")
```

## Installation

```bash
pip install ifckit          # once published
# or locally:
pip install -e ".[dev]"
```

## Development

```bash
pytest                                          # run tests
pytest --cov=ifckit --cov-report=term-missing  # with coverage
ruff check ifckit/                              # lint
```

See `PLAN.md` for the full milestone implementation plan.
