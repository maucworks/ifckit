"""
ifckit.handles
==============

Handle classes that wrap ifcopenshell entities.

Handles provide a clean, Pythonic API for navigating the IFC spatial hierarchy.
They are lightweight wrappers that delegate to IfcModel for actual operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import ifcopenshell

if TYPE_CHECKING:
    from ifckit.model import IfcModel
    from ifckit.elements.base import PendingElement


class Handle:
    """Base class for all entity wrappers."""

    __slots__ = ("_entity", "_model")

    def __init__(self, entity: ifcopenshell.entity_instance, model: IfcModel) -> None:
        object.__setattr__(self, "_entity", entity)
        object.__setattr__(self, "_model", model)

    @property
    def entity(self) -> ifcopenshell.entity_instance:
        return object.__getattribute__(self, "_entity")

    @property
    def _model_ref(self) -> IfcModel:
        return object.__getattribute__(self, "_model")

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.entity.is_a()})"


class SiteHandle(Handle):
    """Thin wrapper around an ifcopenshell IfcSite entity."""

    def add_building(
        self,
        name: str,
        description: Optional[str] = None,
    ) -> "BuildingHandle":
        """Create an IfcBuilding under this site."""
        return self._model_ref.add_building(self, name, description=description)

    def add_bridge(
        self,
        name: str,
        description: Optional[str] = None,
    ) -> "BridgeHandle":
        """Create an IfcBridge under this site (IFC4X3 only)."""
        return self._model_ref.add_bridge(self, name, description=description)

    def add_alignment(self, name: str) -> "AlignmentHandle":
        """Create an IfcAlignment under this site (IFC4X3 only)."""
        return self._model_ref.add_alignment(self, name)

    def clear(self) -> int:
        """
        Remove all elements contained in this site (buildings, bridges, etc).

        Returns:
            The number of elements removed.
        """
        return self._model_ref._clear_container(self.entity)


class BuildingHandle(Handle):
    """Thin wrapper around an ifcopenshell IfcBuilding entity."""

    def add_storey(
        self,
        name: str,
        elevation: float = 0.0,
    ) -> "StoreyHandle":
        """Create an IfcBuildingStorey under this building."""
        return self._model_ref.add_storey(self, name, elevation=elevation)

    def clear(self) -> int:
        """
        Remove all elements contained in this building and its storeys.

        Returns:
            The number of elements removed.
        """
        return self._model_ref._clear_container(self.entity)


class StoreyHandle(Handle):
    """Thin wrapper around an ifcopenshell IfcBuildingStorey entity."""

    def add(self, pending: PendingElement) -> "EntityHandle":
        """Validate and build *pending*, placing it in this storey."""
        return self._model_ref.add(pending, self)

    def clear(self) -> int:
        """
        Remove all elements contained in this storey.

        Returns:
            The number of elements removed.
        """
        return self._model_ref._clear_container(self.entity)


class BridgeHandle(Handle):
    """Thin wrapper around an ifcopenshell IfcBridge entity (IFC4X3)."""

    def add_bridge_part(
        self,
        name: str,
        part_type: str = "NOTDEFINED",
    ) -> "BridgePartHandle":
        """Create an IfcBridgePart under this bridge."""
        return self._model_ref.add_bridge_part(self, name, part_type=part_type)

    def clear(self) -> int:
        """
        Remove all elements contained in this bridge.

        Returns:
            The number of elements removed.
        """
        return self._model_ref._clear_container(self.entity)


class BridgePartHandle(Handle):
    """Thin wrapper around an ifcopenshell IfcBridgePart entity (IFC4X3)."""

    def add(self, pending: PendingElement) -> "EntityHandle":
        """Validate and build *pending*, placing it in this bridge part."""
        return self._model_ref.add(pending, self)

    def clear(self) -> int:
        """
        Remove all elements contained in this bridge part.

        Returns:
            The number of elements removed.
        """
        return self._model_ref._clear_container(self.entity)


class AlignmentHandle(Handle):
    """Thin wrapper around an ifcopenshell IfcAlignment entity (IFC4X3)."""

    pass


class EntityHandle(Handle):
    """Generic wrapper around any ifcopenshell product entity."""

    pass