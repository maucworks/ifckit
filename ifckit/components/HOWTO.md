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
MijnComponent — Python generative window.
"""
from ifckit.builders._geom import axis2placement3d, extrude_profile, profile_from_points
from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.components import EvaluatedComponent, WindowComponent, component
from ifckit.geometry import Path, Plane, Vec
from ifckit.profiles import RectangleProfile


ALUMINUM = {"color": {"r": 0.8, "g": 0.8, "b": 0.8}, "transparency": 0.0, "name": "Aluminium"}
GLASS    = {"color": {"r": 0.9, "g": 0.95, "b": 1.0}, "transparency": 0.5, "name": "Glas"}
VOID     = {"color": {"r": 0.5, "g": 0.5, "b": 0.5}, "transparency": 1.0, "name": "Opening"}


@component("mijn_component")
class MijnComponent(WindowComponent):
    name = "mijn_component"

    def build(self, ifc_file, plane, w, h, params):
        lt = float(params.get("lining_thickness", 55))
        ld = float(params.get("lining_depth", 70))
        gd = float(params.get("panel_depth", 6))
        wt = float(params.get("wall_thickness", 200))
        wx, wy = float(w), float(h)

        comps = []

        # ── Opening (gat in de muur) ──────────────────────────────
        opening_profile = profile_from_points(
            ifc_file, [(0.0, 0.0), (wx, 0.0), (wx, wy), (0.0, wy)]
        )
        opening_solid = extrude_profile(
            ifc_file, opening_profile, depth=wt * 2, extrude_direction=(0, 0, -1),
        )
        comps.append(EvaluatedComponent(solid=opening_solid, role="Opening", material=VOID))

        # ── Lining (frame) ────────────────────────────────────────
        spine = Path.from_pts(
            [Vec(0, 0, 0), Vec(wx, 0, 0), Vec(wx, wy, 0), Vec(0, wy, 0)],
            plane=Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
            closed=True,
        )
        spine.fillet([0, 1, 2, 3], wx / 2.1)

        starter = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        profile = RectangleProfile(ld, lt)
        profile.anchor = "w"
        lining_solid = SectionedSpineBuilder().tessellate_spine(
            ifc_file, spine=spine, profile=profile,
            starter_plane=starter, profile_segments=16,
        )
        comps.append(EvaluatedComponent(solid=lining_solid, role="Lining", material=ALUMINUM))

        # ── Glazing ──────────────────────────────────────────────
        glass_profile = profile_from_points(
            ifc_file,
            [(lt, lt), (wx - lt, lt), (wx - lt, wy - lt), (lt, wy - lt)],
        )
        z_off = -(ld / 2 - gd / 2)
        glass_pos = axis2placement3d(ifc_file, Vec(0, 0, z_off), Vec(0, 0, 1), Vec(1, 0, 0))
        glass_solid = extrude_profile(
            ifc_file, glass_profile, depth=gd, position=glass_pos,
            extrude_direction=(0, 0, -1),
        )
        comps.append(EvaluatedComponent(solid=glass_solid, role="Glazing", material=GLASS))

        return comps


MijnComponent.register()
```

## Stap 2 — Import toevoegen in `pythonic/__init__.py`

Open `ifckit/components/pythonic/__init__.py` en voeg toe:

```python
from ifckit.components.pythonic.mijn_component import MijnComponent as MijnComponent

__all__ = [
    "DoorFlushComponent",
    "FixedCasementComponent",
    "RoundedCasementComponent",
    "MijnComponent",   # ←
]
```

De import zorgt dat het bestand geladen wordt tijdens `_ensure_components_registered()`, die `import ifckit.components.pythonic` doet en alle module-regels activeert.

## Stap 3 — Naar verwijzen in `hello_wall.json`

```json
{
  "id": "W-MIJN",
  "type": "window",
  "component_graph": "mijn_component",
  "parameters": {
    "lining_thickness": 50,
    "lining_depth": 80
  }
}
```

## Hoe het werkt

| Laag | Wat |
|---|---|
| `@component("naam")` | registreert de class in `COMPONENT_REGISTRY["naam"]` |
| `register()` | idem (fallback als decorator niet gebruikt is) |
| `__init__.py` import | laadt het bestand zodat de decorator/register wordt uitgevoerd |
| `hello_wall.json` | `component_graph` verwijst naar de registry-naam |

## Waarom deze flow

Python components worden NIET automatisch gediscovered — elk nieuw bestand moet expliciet geïmporteerd worden in `__init__.py`. Dit voorkomt:
- onverwachte import-side-effects
- conflicten tussen JSON-presets en Python components met dezelfde naam

De fallback in `evaluate_opening_nodes()` probeert eerst Python registry, dan JSON.
