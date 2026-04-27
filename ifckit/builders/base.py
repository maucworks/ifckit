"""
ifckit.builders.base
====================

IIfcBuilder protocol and BuilderRegistry.
"""

from __future__ import annotations

from typing import Any, Dict, Protocol, Type

import ifcopenshell

from ifckit.elements.base import PendingElement


class IIfcBuilder(Protocol):
    """
    Protocol every builder must satisfy.

    Each builder converts one PendingElement subtype into one or more
    ifcopenshell entity instances and attaches them to the given container.
    """

    #: IFC class name this builder produces, e.g. 'IfcWall'
    entity_type: str

    def build(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        """
        Build and return the primary IFC entity.

        Args:
            ifc_file:  The target ifcopenshell file.
            pending:   The pending element data container.
            container: The spatial structure entity to contain the result
                       (IfcBuildingStorey, IfcBridgePart, etc.).
            context:   The geometric representation context to use.

        Returns:
            The created primary IFC entity.
        """
        ...


class BuilderRegistry:
    """
    Registry mapping PendingElement.element_type → IIfcBuilder instance.

    Usage::

        registry = BuilderRegistry()
        registry.register(WallBuilder())
        entity = registry.build(ifc_file, pending_wall, storey, context)
    """

    def __init__(self) -> None:
        self._builders: Dict[str, IIfcBuilder] = {}

    def register(self, builder: IIfcBuilder) -> None:
        """Register a builder. Raises if element_type already registered."""
        key = builder.entity_type
        if key in self._builders:
            raise ValueError(f"Builder already registered for element_type '{key}'")
        self._builders[key] = builder

    def get(self, element_type: str) -> IIfcBuilder:
        """Return the builder for a given element_type or raise KeyError."""
        try:
            return self._builders[element_type]
        except KeyError:
            raise KeyError(
                f"No builder registered for element_type '{element_type}'. "
                f"Registered: {list(self._builders)}"
            )

    def build(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        """Dispatch to the correct builder and return the created entity."""
        builder = self.get(pending.element_type)
        return builder.build(ifc_file, pending, container, context)

    def registered_types(self) -> list[str]:
        return list(self._builders)
