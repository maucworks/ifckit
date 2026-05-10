"""
ifckit.components
=================

Pythonic generative component system for fill products (windows, doors,
shading devices, plates, etc.).

Components are auto-discovered from ``ifckit/components/pythonic/`` — any
file ending in ``_component.py`` is imported and its ``FillComponent``
subclass is registered in ``COMPONENT_REGISTRY`` keyed by the file name
minus the ``_component`` suffix.

Example component at ``pythonic/folding_door_component.py``::

    class FoldingDoor(FillComponent):
        ifc_class = "IfcDoor"

        def build(self, ifc_file, plane, w, h, params) -> list[EvaluatedComponent]:
            return [...]
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import ifcopenshell

from ifckit.geometry import Plane

# Global registry: name -> Component class
COMPONENT_REGISTRY: dict[str, type["FillComponent"]] = {}

_discovered = False


def _ensure_components_registered():
    """Auto-discover Pythonic components and populate COMPONENT_REGISTRY."""
    global _discovered
    if _discovered:
        return
    _discovered = True
    import ifckit.components.pythonic  # noqa: F401


@dataclass
class EvaluatedComponent:
    """Single output component produced by a FillComponent.

    Attributes:
        solid: The IFC representation item.
        role: Semantic role: ``"Opening"``, ``"Lining"``, ``"Glazing"``,
              ``"Panel"``, etc.  A component whose role is ``"Opening"``
              triggers creation of an ``IfcOpeningElement``.
        material: Material definition dict (color, transparency, name).
        node_id: Optional node identifier for tracking.
    """

    solid: "ifcopenshell.entity_instance"
    role: str
    material: dict | None = None
    node_id: str | None = None


class FillComponent(ABC):
    """Abstract base class for generative fill components.

    A fill component produces geometry that lives inside an opening
    (or is itself an opening).  It returns a list of
    :class:`EvaluatedComponent` objects from :meth:`build`.

    When one of those components has ``role="Opening"``, the pipeline
    automatically creates an ``IfcOpeningElement`` + ``IfcRelVoidsElement``
    in the host element.  All other roles become items in the fill product's
    ``IfcShapeRepresentation``.

    Subclasses must:
    * Set ``ifc_class`` (e.g. ``"IfcWindow"``, ``"IfcDoor"``,
      ``"IfcPlate"``, ``"IfcShadingDevice"``).
    * Implement :meth:`build`.
    * Be placed in a ``_component.py`` file inside ``pythonic/`` — auto-
      discovery handles the rest.  No decorator, no ``name``, no ``register``.
    """

    ifc_class: str = "IfcWindow"

    @abstractmethod
    def build(
        self,
        ifc_file: "ifcopenshell.file",
        plane: Plane,
        width: float,
        height: float,
        params: dict[str, float],
    ) -> list[EvaluatedComponent]:
        """Build component geometry.

        Args:
            ifc_file: Active IFC file for entity creation.
            plane: Reference plane — local XY is the profile plane,
                   local Z is the default extrusion direction.
            width: Overall width in mm.
            height: Overall height in mm.
            params: Fully resolved parameters (type defaults + occurrence
                    overrides).  All values in mm.

        Returns:
            List of :class:`EvaluatedComponent` objects.  Each becomes an
            item in the ``IfcShapeRepresentation``.  A component with
            ``role="Opening"`` additionally creates an
            ``IfcOpeningElement``.
        """
        ...


def get_component(name: str) -> type[FillComponent] | None:
    """Get a registered component class by name."""
    return COMPONENT_REGISTRY.get(name)


def list_components() -> list[str]:
    """List all registered component names."""
    _ensure_components_registered()
    return list(COMPONENT_REGISTRY.keys())
