# Pythonic Generative Component System — Design Document

## Overview

A Python-based system for creating window and door components dynamically using code. Coexists with the existing JSON declarative system.

## Design Principles

1. **Same namespace**: `door_flush` registers under same name as JSON, JSON wins on conflict
2. **Full parameter resolution**: Component receives merged type + occurrence parameters
3. **Arbitrary extrusion direction**: Create new planes for different sweep directions
4. **Dict material**: Same structure as JSON components

---

## Architecture

### Component Registry

Location: `ifckit/components/__init__.py`

```python
# Global registry: name -> Component class
COMPONENT_REGISTRY: dict[str, type[WindowComponent]] = {}
```

### Base Class

```python
@dataclass
class EvaluatedComponent:
    """Single output component produced by a component build."""
    solid: ifcopenshell.entity_instance  # The IFC geometry
    role: str  # Semantic role: "Lining", "Glazing", "Panel", "Opening"
    material: dict | None = None  # Same as JSON: {"color": {...}, "transparency": ..., "name": ...}


class WindowComponent(ABC):
    """Abstract base class for generative window/door components."""
    
    # Registered name - same namespace as JSON presets
    name: str = ""
    
    @abstractmethod
    def build(
        self,
        ifc_file: ifcopenshell.file,
        plane: Plane,
        width: float,
        height: float,
        params: dict[str, float],
    ) -> List[EvaluatedComponent]:
        """
        Build component geometry.
        
        Args:
            ifc_file: Active IFC file for entity creation
            plane: Reference plane (local X/Y defines profile plane)
            width: Overall width in mm
            height: Overall height in mm  
            params: Fully resolved parameters (type defaults merged with occurrence overrides)
        
        Returns:
            List of EvaluatedComponent objects to add to shape representation
        """
        pass
    
    @classmethod
    def register(cls, name: str = None):
        """Register this component to the global registry."""
        COMPONENT_REGISTRY[name or cls.name] = cls
        return cls
```

---

## Profile Construction API

Components construct geometry using the `Plane` as the reference frame:

| Attribute | Description |
|-----------|-------------|
| `plane.origin` | Origin point (Vec) |
| `plane.x_axis` | Local X direction (Vec) |
| `plane.y_axis` | Local Y direction (Vec) |
| `plane.z_axis` | Local Z direction (Vec) |

### Creating Profiles in Local Coordinates

```python
from ifckit.geometry import Plane, Vec

class DoorFlush(WindowComponent):
    name = "door_flush"
    
    def build(self, ifc_file, plane, w, h, params) -> List[EvaluatedComponent]:
        # Convenience: create points in plane's local coordinates
        origin = plane.origin
        x = plane.x_axis
        y = plane.y_axis
        
        # Frame outer rectangle at origin
        p0 = origin
        p1 = origin + x * w
        p2 = origin + x * w + y * h
        p3 = origin + y * h
        
        # Use geometry.PolygonProfile or similar to create profile
        frame = PolygonProfile.from_pts([p0, p1, p2, p3], plane=plane, closed=True)
        
        # Door opening hole
        lt = params.get("lining_thickness", 50)
        dh = params.get("door_height", 2100)
        
        hole_origin = origin + x * lt
        hole = PolygonProfile.rect(plane, hole_origin, hole_origin + x * (w - lt) + y * dh)
        
        # Profile with hole
        profile = frame.with_hole(hole)
        
        # Extrude - direction is implicit to profile plane
        # Profile plane (XY) extrudes in local Z (into wall)
        ld = params.get("lining_depth", 100)
        solid = extrude_profile(
            ifc_file,
            profile.to_ifc(),
            depth=ld,
            extrude_direction=tuple(-plane.z_axis),  # Into wall (negative Z)
        )
        
        return [EvaluatedComponent(solid=solid, role="Lining", material=...)]
```

---

## Material Definition

Same dict structure as JSON:

```python
ALUMINUM_FRAME = {
    "color": {"r": 0.8, "g": 0.8, "b": 0.8},
    "transparency": 0.0,
    "name": "Aluminum frame"
}

GLASS = {
    "color": {"r": 0.9, "g": 0.95, "b": 1.0},
    "transparency": 0.8,
    "name": "Clear glass"
}
```

---

## Extrusion Direction Control

**Implicit**: Profile defined in XY plane of reference `Plane` → extrudes in local Z.

**Custom direction**: Create a new `Plane` with different orientation:

```python
class Side Window(WindowComponent):
    """Window on wall side - profile in XZ plane, extrude in +Y."""
    
    name = "side_window"
    
    def build(self, ifc_file, plane, w, h, params):
        # Create XZ plane (rotate 90° around Y axis)
        xz_plane = Plane(
            origin=plane.origin,
            x_axis=plane.z_axis,  # Original Z becomes new X
            y_axis=plane.y_axis,  # Y stays Y
            z_axis=-plane.x_axis, # Original X becomes new -Z
        )
        
        # Build profile in XZ plane
        profile = PolygonProfile.rect(xz_plane, xz_plane.origin, ...)
        
        # Extrude in original +Y direction
        solid = extrude_profile(
            ifc_file,
            profile.to_ifc(),
            depth=params.get("depth", 100),
            extrude_direction=tuple(plane.y_axis),
        )
        
        return [EvaluatedComponent(solid=solid, role="Frame", material=...)]
```

---

## Integration with JSON Evaluator

In `ifckit/builders/component_graph.py`:

```python
def evaluate_component_graph(preset_name, ifc_file, context, params, plane=None):
    # 1. Check JSON preset FIRST (JSON wins on collision)
    try:
        preset = _load_preset(preset_name)
    except FileNotFoundError:
        # 2. Fall back to Python component if JSON not found
        from ifckit.components import get_component
        if component := get_component(preset_name):
            return component.build(ifc_file, plane, params["w"], params["h"], params)
        raise

    # Use JSON preset
    ...
```

**Rules:**
- JSON file wins: `door_flush.json` takes precedence over `DoorFlushComponent`
- Python wins when JSON absent: Delete/rename `door_flush.json` to use Python component
- Same namespace: Components have same name as JSON presets (`door_flush`, `fixed_casement`)

**File naming:**
- JSON: `window_types/<name>.json` (e.g., `door_flush.json`)
- Python: `components/<name>_component.py` (e.g., `door_flush_component.py`)
        component_cls = COMPONENT_REGISTRY[preset_name]
        component = component_cls()
        
        # Get plane from context (already resolved)
        plane = get_reference_plane(context, params)
        
        return component.build(
            ifc_file,
            plane,
            params["w"],
            params["h"],
            params,
        )
    
    # 2. Fall back to JSON preset (existing behavior)
    return evaluate_json_preset(preset_name, ifc_file, context, params)
```

---

## Coexistence Rules

| Scenario | Resolution |
|----------|-------------|
| Name in both JSON + Python | JSON wins (evaluator checks JSON registry first) |
| Python component missing | Error: "Component not found" |
| JSON preset missing | Error: "Preset not found" |

To force use Python component when JSON exists with same name: delete JSON file or rename Python component (e.g., `door_flush_v2`).

---

## File Structure

```
ifckit/
  components/
    __init__.py          # Base class + registry
    door_flush.py       # Example: generative door_flush
    window_fixed.py     # Example: generative fixed_casement
```

---

## Migration Path (User-Initiated)

1. Keep existing JSON presets as-is
2. User creates Python component with same name (`door_flush`)
3. At eval time, Python component is used (check order in evaluator)
4. OR rename JSON file to `door_flush.json.bak` and use Python exclusively

---

## Parameter Resolution Flow

```
1. JSON type definition (e.g., door_types) provides defaults
2. JSON occurrence provides overrides  
3. Evaluator merges: occurrence overrides → type defaults
4. Final params dict passed to component.build()
5. Component receives fully resolved parameters
```

---

## Example: Full DoorFlush Implementation

See `ifckit/components/door_flush.py` for complete implementation.

Key features:
- Lining: 3-sided frame with door opening + top/side glazing
- Panel: Door leaf
- Glazing: Top and side light glass
- All materials inline
- All using JSON-compatible dicts

---

## Testing Strategy

1. Create component, verify registration works
2. Build via JSON API (`hello_wall.json` or test JSON)
3. Compare IFC output with JSON-only version
4. Verify geometry in Bonsai
5. Edge cases: different planes, custom directions