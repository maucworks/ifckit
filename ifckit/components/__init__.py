"""
ifckit.components
================

Pythonic generative component system for windows and doors.

Provides an alternative to JSON declarative presets. Components are Python
classes that construct geometry programmatically using the reference plane
as their coordinate system.

Usage:
    from ifckit.components import WindowComponent, EvaluatedComponent

    class MyDoor(WindowComponent):
        name = "my_door"

        def build(self, ifc_file, plane, w, h, params) -> list[EvaluatedComponent]:
            # Construct geometry
            ...
            return [EvaluatedComponent(solid=..., role="Lining", material=...)]

    # Register
    MyDoor.register()

Integration:
    The component evaluator checks the Python registry before
    falling back to JSON presets. Same namespace, JSON wins
    on name collision.

Arbitrary extrusion direction:
    Profiles are defined in the local XY plane of the reference Plane.
    To extrude in a different direction, create a new Plane with the
    desired orientation:

    class SideWindow(WindowComponent):
        def build(self, ifc_file, plane, w, h, params):
            # Rotate plane 90° around Y for XZ profile plane
            xz_plane = Plane(plane.origin, plane.z_axis, plane.y_axis, -plane.x_axis)
            # Build profile in xz_plane, extrude in original Y
            ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ifcopenshell

from ifckit.geometry import Plane

# Global registry: name -> Component class
COMPONENT_REGISTRY: dict[str, type[WindowComponent]] = {}

_pythonic_registered = False


def _ensure_components_registered():
    """Auto-import Pythonic components to register them."""
    global _pythonic_registered
    if _pythonic_registered:
        return
    _pythonic_registered = True
    # Trigger import of pythonic package which registers its components
    import ifckit.components.pythonic  # noqa: F401


@dataclass
class EvaluatedComponent:
    """Single output component produced by a WindowComponent.

    Attributes:
        solid: The IFC representation item (IfcExtrudedAreaSolid, IfcBooleanResult, etc.)
        role: Semantic role for material inheritance and identification.
             Common values: "Lining", "Glazing", "Panel", "Opening"
        material: Material definition dict, same structure as JSON.
                 Keys: "color" (r/g/b 0-1), "transparency" (0-1), "name"
        node_id: Optional node identifier for tracking.
    """

    solid: "ifcopenshell.entity_instance"
    role: str
    material: dict | None = None
    node_id: str | None = None


class WindowComponent(ABC):
    """Abstract base class for generative window/door components.

    Components construct geometry programmatically using a reference Plane
    as their local coordinate system. The plane defines:
    - XY plane: where the 2D profile is drawn
    - Z direction: default extrusion direction (into the wall)

    Subclasses must:
    1. Define class attribute `name` with the registered name
    2. Implement `build()` to construct geometry
    3. Call `register()` as a class decorator or explicitly

    Example:
        class DoorFlush(WindowComponent):
            name = "door_flush"

            def build(self, ifc_file, plane, w, h, params) -> list[EvaluatedComponent]:
                # Build geometry
                ...
                return [EvaluatedComponent(solid=solid, role="Lining", material={...})]

            DoorFlush.register()  # Or use @register decorator
    """

    name: str = ""

    @abstractmethod
    def build(
        self,
        ifc_file: ifcopenshell.file,
        plane: Plane,
        width: float,
        height: float,
        params: dict[str, float],
    ) -> list[EvaluatedComponent]:
        """Build component geometry.

        Args:
            ifc_file: Active IFC file for entity creation
            plane: Reference plane - local XY is profile plane,
                   local Z is default extrusion direction
            width: Overall width in mm (from occurrence)
            height: Overall height in mm (from occurrence)
            params: Fully resolved parameters - type defaults merged with
                   occurrence overrides. All numeric values in mm.

        Returns:
            List of EvaluatedComponent objects. Each becomes an item
            in the IfcShapeRepresentation. The evaluator handles
            placement, material styling, and representation type selection.
        """
        pass

    @classmethod
    def register(cls, name: str = None) -> type[WindowComponent]:
        """Register this component to the global registry.

        Args:
            name: Optional override for class name attribute.
                 Defaults to cls.name.

        Returns:
            The component class (for use as decorator).

        Raises:
            ValueError: If name is already registered.
        """
        registry_name = name or cls.name
        if not registry_name:
            raise ValueError(f"{cls.__name__} has no name attribute")
        if registry_name in COMPONENT_REGISTRY:
            existing = COMPONENT_REGISTRY[registry_name]
            if existing is not cls:
                raise ValueError(
                    f"Component name {registry_name!r} already registered to {existing.__name__}"
                )
        COMPONENT_REGISTRY[registry_name] = cls
        return cls


# Decorator form for convenience
def component(name: str):
    """Decorator to register a WindowComponent subclass.

    Usage:
        @component("my_door")
        class MyDoor(WindowComponent):
            name = "my_door"
            ...
    """

    def decorator(cls: type[WindowComponent]) -> type[WindowComponent]:
        cls.register(name)
        return cls

    return decorator


def get_component(name: str) -> type[WindowComponent] | None:
    """Get a registered component class by name."""
    return COMPONENT_REGISTRY.get(name)


def list_components() -> list[str]:
    """List all registered component names."""
    # Ensure Pythonic components are registered
    if not _pythonic_registered:
        import ifckit.components.pythonic  # noqa: F401
    return list(COMPONENT_REGISTRY.keys())
