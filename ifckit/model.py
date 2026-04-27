"""
ifckit.model
============

IfcModel: builds and manages an IFC spatial hierarchy using ifcopenshell.

Supports IFC4 (buildings) and IFC4X3 (bridges / infrastructure).
"""

from __future__ import annotations

from typing import Optional

import ifcopenshell
import ifcopenshell.api

from ifckit.schema import IfcSchema, LengthUnit, get_schema_name


class SiteHandle:
    """Thin wrapper around an ifcopenshell IfcSite entity."""
    def __init__(self, entity: ifcopenshell.entity_instance) -> None:
        self._entity = entity

    @property
    def entity(self) -> ifcopenshell.entity_instance:
        return self._entity


class BuildingHandle:
    """Thin wrapper around an ifcopenshell IfcBuilding entity."""
    def __init__(self, entity: ifcopenshell.entity_instance) -> None:
        self._entity = entity

    @property
    def entity(self) -> ifcopenshell.entity_instance:
        return self._entity


class StoreyHandle:
    """Thin wrapper around an ifcopenshell IfcBuildingStorey entity."""
    def __init__(self, entity: ifcopenshell.entity_instance) -> None:
        self._entity = entity

    @property
    def entity(self) -> ifcopenshell.entity_instance:
        return self._entity


class BridgeHandle:
    """Thin wrapper around an ifcopenshell IfcBridge entity (IFC4X3)."""
    def __init__(self, entity: ifcopenshell.entity_instance) -> None:
        self._entity = entity

    @property
    def entity(self) -> ifcopenshell.entity_instance:
        return self._entity


class BridgePartHandle:
    """Thin wrapper around an ifcopenshell IfcBridgePart entity (IFC4X3)."""
    def __init__(self, entity: ifcopenshell.entity_instance) -> None:
        self._entity = entity

    @property
    def entity(self) -> ifcopenshell.entity_instance:
        return self._entity


class AlignmentHandle:
    """Thin wrapper around an ifcopenshell IfcAlignment entity (IFC4X3)."""
    def __init__(self, entity: ifcopenshell.entity_instance) -> None:
        self._entity = entity

    @property
    def entity(self) -> ifcopenshell.entity_instance:
        return self._entity


class EntityHandle:
    """Generic wrapper around any ifcopenshell product entity."""
    def __init__(self, entity: ifcopenshell.entity_instance) -> None:
        self._entity = entity

    @property
    def entity(self) -> ifcopenshell.entity_instance:
        return self._entity


class IfcModel:
    """
    Manages an IFC spatial hierarchy and exposes a simple builder API.

    Args:
        name:   Project name (IfcProject.Name).
        schema: IfcSchema.IFC4 or IfcSchema.IFC4X3.
        author: Author name stored in IfcOwnerHistory (informational only).
        unit:   Length unit (default: METRE).

    Usage::

        model = IfcModel(name="My Project", schema=IfcSchema.IFC4, author="Me")
        site = model.add_site("Site A")
        building = model.add_building(site, "Building 1")
        storey = model.add_storey(building, "Ground Floor", elevation=0.0)
        model.save("/tmp/output.ifc")
    """

    def __init__(
        self,
        name: str = "Unnamed Project",
        schema: IfcSchema = IfcSchema.IFC4,
        author: str = "",
        unit: LengthUnit = LengthUnit.METRE,
    ) -> None:
        self.name = name
        self.schema = schema
        self.author = author
        self.unit = unit

        schema_str = get_schema_name(schema)
        self._file = ifcopenshell.file(schema=schema_str)

        # Create IfcProject
        self._project = ifcopenshell.api.run(
            "root.create_entity",
            self._file,
            ifc_class="IfcProject",
            name=name,
        )

        # Assign SI units
        ifcopenshell.api.run("unit.assign_unit", self._file)

        # Add geometric representation context (needed for geometry)
        self._context = ifcopenshell.api.run(
            "context.add_context",
            self._file,
            context_type="Model",
        )

    # ------------------------------------------------------------------
    # IFC4 spatial hierarchy
    # ------------------------------------------------------------------

    def add_site(
        self,
        name: str,
        description: Optional[str] = None,
    ) -> SiteHandle:
        """Create an IfcSite and aggregate it under the project."""
        site = ifcopenshell.api.run(
            "root.create_entity",
            self._file,
            ifc_class="IfcSite",
            name=name,
        )
        if description:
            site.Description = description
        ifcopenshell.api.run(
            "aggregate.assign_object",
            self._file,
            products=[site],
            relating_object=self._project,
        )
        return SiteHandle(site)

    def add_building(
        self,
        site: SiteHandle,
        name: str,
        description: Optional[str] = None,
    ) -> BuildingHandle:
        """Create an IfcBuilding and aggregate it under a site."""
        building = ifcopenshell.api.run(
            "root.create_entity",
            self._file,
            ifc_class="IfcBuilding",
            name=name,
        )
        if description:
            building.Description = description
        ifcopenshell.api.run(
            "aggregate.assign_object",
            self._file,
            products=[building],
            relating_object=site.entity,
        )
        return BuildingHandle(building)

    def add_storey(
        self,
        building: BuildingHandle,
        name: str,
        elevation: float = 0.0,
    ) -> StoreyHandle:
        """Create an IfcBuildingStorey and aggregate it under a building."""
        storey = ifcopenshell.api.run(
            "root.create_entity",
            self._file,
            ifc_class="IfcBuildingStorey",
            name=name,
        )
        storey.Elevation = elevation
        ifcopenshell.api.run(
            "aggregate.assign_object",
            self._file,
            products=[storey],
            relating_object=building.entity,
        )
        return StoreyHandle(storey)

    def add_element(
        self,
        storey: StoreyHandle,
        ifc_class: str,
        name: str = "",
    ) -> EntityHandle:
        """
        Create a generic IFC product entity and contain it in a storey.

        Args:
            storey:    Target storey (IfcBuildingStorey).
            ifc_class: IFC entity class name, e.g. 'IfcWall', 'IfcBeam'.
            name:      Entity name.

        Returns:
            EntityHandle wrapping the created entity.
        """
        entity = ifcopenshell.api.run(
            "root.create_entity",
            self._file,
            ifc_class=ifc_class,
            name=name,
        )
        ifcopenshell.api.run(
            "spatial.assign_container",
            self._file,
            products=[entity],
            relating_structure=storey.entity,
        )
        return EntityHandle(entity)

    # ------------------------------------------------------------------
    # IFC4X3 bridge hierarchy
    # ------------------------------------------------------------------

    def add_bridge(
        self,
        site: SiteHandle,
        name: str,
        description: Optional[str] = None,
    ) -> BridgeHandle:
        """
        Create an IfcBridge and aggregate it under a site.
        Requires schema IFC4X3.
        """
        self._require_schema(IfcSchema.IFC4X3, "add_bridge")
        bridge = ifcopenshell.api.run(
            "root.create_entity",
            self._file,
            ifc_class="IfcBridge",
            name=name,
        )
        if description:
            bridge.Description = description
        ifcopenshell.api.run(
            "aggregate.assign_object",
            self._file,
            products=[bridge],
            relating_object=site.entity,
        )
        return BridgeHandle(bridge)

    def add_bridge_part(
        self,
        bridge: BridgeHandle,
        name: str,
        part_type: str = "NOTDEFINED",
    ) -> BridgePartHandle:
        """
        Create an IfcBridgePart and aggregate it under a bridge.
        Requires schema IFC4X3.

        Args:
            bridge:    Parent bridge handle.
            name:      Part name.
            part_type: PredefinedType string, e.g. 'DECK', 'SUBSTRUCTURE'.
        """
        self._require_schema(IfcSchema.IFC4X3, "add_bridge_part")
        part = ifcopenshell.api.run(
            "root.create_entity",
            self._file,
            ifc_class="IfcBridgePart",
            predefined_type=part_type,
            name=name,
        )
        ifcopenshell.api.run(
            "aggregate.assign_object",
            self._file,
            products=[part],
            relating_object=bridge.entity,
        )
        return BridgePartHandle(part)

    def add_alignment(
        self,
        site: SiteHandle,
        name: str,
    ) -> AlignmentHandle:
        """
        Create an IfcAlignment and aggregate it under a site.
        Requires schema IFC4X3.
        """
        self._require_schema(IfcSchema.IFC4X3, "add_alignment")
        alignment = ifcopenshell.api.run(
            "root.create_entity",
            self._file,
            ifc_class="IfcAlignment",
            name=name,
        )
        ifcopenshell.api.run(
            "aggregate.assign_object",
            self._file,
            products=[alignment],
            relating_object=site.entity,
        )
        return AlignmentHandle(alignment)

    def add_element_to_part(
        self,
        part: BridgePartHandle,
        ifc_class: str,
        name: str = "",
    ) -> EntityHandle:
        """
        Create a generic IFC product entity and contain it in a bridge part.
        """
        entity = ifcopenshell.api.run(
            "root.create_entity",
            self._file,
            ifc_class=ifc_class,
            name=name,
        )
        ifcopenshell.api.run(
            "spatial.assign_container",
            self._file,
            products=[entity],
            relating_structure=part.entity,
        )
        return EntityHandle(entity)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Write the IFC file to disk."""
        self._file.write(path)

    def to_string(self) -> str:
        """Serialise the IFC model to a STEP string (no file I/O)."""
        return self._file.to_string()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_schema(self, required: IfcSchema, method: str) -> None:
        if self.schema != required:
            raise ValueError(
                f"IfcModel.{method}() requires schema {required.value}, "
                f"but model uses {self.schema.value}"
            )

    @property
    def ifc_file(self) -> ifcopenshell.file:
        """Direct access to the underlying ifcopenshell file (advanced use)."""
        return self._file
