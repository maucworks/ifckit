# Components HOWTO — Python generative window/door components

## Layout

```
ifckit/components/
├── __init__.py          ← registry, _ensure_components_registered()
├── json/                ← JSON preset components (legacy)
└── pythonic/            ← Python generative components
    ├── __init__.py      ← imports every component module
    ├── door_flush_component.py
    ├── fixed_casement_component.py
    ├── rounded_casement_component.py
    └── …                ← add new files here
```

## Stap 1 — Schrijf de component

Maak `ifckit/components/pythonic/mijn_component.py`:

```python
"""
MijnComponent — Python generative component voor IfcPlate.
"""
from ifckit.builders._geom import axis2placement3d, extrude_profile, profile_from_points
from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.components import EvaluatedComponent, FillComponent
from ifckit.components.materials import ALUMINUM, GLASS, VOID
from ifckit.geometry import Path, Plane, Vec
from ifckit.profiles import RectangleProfile


ALUMINUM = {"color": {"r": 0.8, "g": 0.8, "b": 0.8}, "transparency": 0.0, "name": "Aluminium"}
GLASS    = {"color": {"r": 0.9, "g": 0.95, "b": 1.0}, "transparency": 0.5, "name": "Glas"}
VOID     = {"color": {"r": 0.5, "g": 0.5, "b": 0.5}, "transparency": 1.0, "name": "Opening"}


class MijnComponent(FillComponent):
    ifc_class = "IfcPlate"

    def build(self, ifc_file, plane, w, h, params):
        ...
        return comps
```

Niks anders — geen decorator, geen `name`, geen `register()`.

## Stap 2 — Klaar

Auto-discovery in ``pythonic/__init__.py`` importeert elk bestand dat op
``_component.py`` eindigt. De ``FillComponent`` subclass wordt
automatisch in ``COMPONENT_REGISTRY`` gezet met twee keys:

```
mijn                      (short — voor nieuwe JSON)
mijn_component            (full — backward compat)
```

## Stap 3 — Naar verwijzen in `hello_wall.json`

```json
{"component_graph": "mijn", "parameters": {}}
```

## Hoe het werkt

| Laag | Wat |
|---|---|
| `pythonic/__init__.py` | Auto-discovert elke `_component.py`, registreert de `FillComponent` subclass |
| FillComponent.ifc_class | Bepaalt het IFC product type (`IfcWindow`, `IfcDoor`, `IfcPlate`, `IfcShadingDevice`, …) |
| EvaluatedComponent.role | `"Opening"` → maakt IfcOpeningElement, andere roles → items in IfcShapeRepresentation |

## Bootstrap

```bash
python ifckit/components/bootstrap.py
# vraagt component name, IFC class, display name
# maakt alleen het bestand — __init__.py hoeft niet aangepast
```
