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
├── model.py              # IfcModel, spatial hierarchy handles
├── schema/
│   ├── __init__.py       # IfcSchema, LengthUnit enums
│   └── json_schema.py    # JSON ↔ IFC conversion
├── elements/
│   ├── base.py           # PendingElement base class
│   ├── registry.py       # ElementRegistry (auto-registration)
│   ├── building.py       # PendingWall, PendingSlab
│   ├── structural.py     # PendingBeam, PendingColumn
│   ├── swept.py          # PendingSweptBeam
│   └── bridge.py         # PendingBridge, etc.
├── geometry/
│   └── __init__.py       # Vec, Plane, Line, Arc, Path
├── validators/
│   └── validator.py      # Validation with auto-registration
├── builders/
│   ├── base.py           # BuilderRegistry, IIfcBuilder
│   ├── wall.py           # WallBuilder
│   ├── extruded.py       # ExtrudedElementBuilder
│   └── ...
└── __main__.py           # CLI entry point
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
@register_validator(PendingNewElement)
def _validate_new_element(e: PendingNewElement) -> ValidationResult:
    # validation logic
    ...

def validate(pending: PendingElement) -> ValidationResult:
    return ValidatorRegistry.get(type(pending))(pending)
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

## JSON Workflow

ifckit supports a complete JSON → IFC workflow:

```python
# Build from JSON
from ifckit.schema.json_schema import build, validate_json

# Validate
result = validate_json(project_dict)
if result.ok:
    model = build(project_dict, "output.ifc")

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

## Design Principles

1. **No external dependencies in data classes** - Pending elements work without Rhino, ifcopenshell, etc.
2. **Auto-registration** - New element types require minimal boilerplate
3. **Clear separation** - Model doesn't know about geometry; validators don't know about IFC
4. **Python-first** - No code generation; pure Python data structures
5. **Schema flexibility** - IFC4 and IFC4X3 support via schema enum