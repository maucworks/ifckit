"""
ifckit.builders.base
===================

IIfcBuilder protocol, BaseBuilder abstract class, and BuilderRegistry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Protocol, runtime_checkable

import ifcopenshell

from ifckit.elements.base import PendingElement
from ifckit.elements.style import RenderStyle

if TYPE_CHECKING:
    from ifckit.geometry import Plane


@runtime_checkable
class IIfcBuilder(Protocol):
    """
    Protocol every builder must satisfy.
    This protocol lives at the ifcopenshell boundary: it deliberately depends on ifcopenshell.

    Each builder converts one PendingElement subtype into one or more
    ifcopenshell entity instances and attaches them to the given container.
    """

    #: Registry key matching PendingElement.element_type, e.g. 'basic_wall'
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


    # Subclasses must implement geometry creation.
    @abstractmethod
    def _create_geometry(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        """Create the geometry and IFC entity. Subclass implements; BaseBuilder handles styling."""
        ...


class BaseBuilder(ABC, IIfcBuilder):
    """
    Abstract base for all element builders with central styling + clipping.

    Provides common build() flow:
        1. Create geometry entity (_create_geometry)
        2. Apply clipping (if start_clip/end_clip present)
        3. Apply styling (default gray fallback)

    Subclasses must implement _create_geometry().
    """

    entity_type: str

    def build(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        # 1. Subclass creates geometry + entity
        entity = self._create_geometry(ifc_file, pending, container, context)

        # 2. Apply clipping (if element has clip planes)
        entity = self._apply_clips(ifc_file, entity, pending, container, context)

        # 3. Apply styling (central with default gray)
        self._apply_styling(ifc_file, entity, pending.style)

        # 4. Write EPset_IfcKit.HatchPattern pset if set
        if getattr(pending, "hatch_pattern", ""):
            pset = ifcopenshell.api.run(
                "pset.add_pset",
                ifc_file,
                product=entity,
                name="EPset_IfcKit",
            )
            ifcopenshell.api.run(
                "pset.edit_pset",
                ifc_file,
                pset=pset,
                properties={"HatchPattern": pending.hatch_pattern},
            )

        return entity

    @abstractmethod
    def _create_geometry(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        """Create entity. Override in subclass."""
        ...

    def _apply_clips(
        self,
        ifc_file: ifcopenshell.file,
        entity: ifcopenshell.entity_instance,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        """Apply start_clip/end_clip if present. Override in subclass if needed."""
        return entity

    def _apply_styling(
        self,
        ifc_file: ifcopenshell.file,
        entity: ifcopenshell.entity_instance,
        style: Any,
    ) -> None:
        """Apply RenderStyle. Uses #808080 (gray) as default if style is None."""
        from ifckit.builders._geom import apply_style

        if style is None:
            style = RenderStyle("#808080")
        apply_style(ifc_file, entity, style)


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
