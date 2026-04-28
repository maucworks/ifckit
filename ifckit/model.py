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


_UNIT_PREFIX: dict = {
    LengthUnit.METRE: None,
    LengthUnit.MILLIMETRE: "MILLI",
}


class Handle:
    """Base class for all entity wrappers."""
    __slots__ = ("_entity",)

    def __init__(self, entity: ifcopenshell.entity_instance) -> None:
        object.__setattr__(self, "_entity", entity)

    @property
    def entity(self) -> ifcopenshell.entity_instance:
        return object.__getattribute__(self, "_entity")

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.entity.is_a()})"


class SiteHandle(Handle):
    """Thin wrapper around an ifcopenshell IfcSite entity."""
    pass


class BuildingHandle(Handle):
    """Thin wrapper around an ifcopenshell IfcBuilding entity."""
    pass


class StoreyHandle(Handle):
    """Thin wrapper around an ifcopenshell IfcBuildingStorey entity."""
    pass


class BridgeHandle(Handle):
    """Thin wrapper around an ifcopenshell IfcBridge entity (IFC4X3)."""
    pass


class BridgePartHandle(Handle):
    """Thin wrapper around an ifcopenshell IfcBridgePart entity (IFC4X3)."""
    pass


class AlignmentHandle(Handle):
    """Thin wrapper around an ifcopenshell IfcAlignment entity (IFC4X3)."""
    pass


class EntityHandle(Handle):
    """Generic wrapper around any ifcopenshell product entity."""
    pass


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

        # Assign SI units according to the requested length unit.
        # Also add area and volume units for complete unit assignment.
        if unit in _UNIT_PREFIX:
            prefix = _UNIT_PREFIX[unit]
            kwargs: dict = {"unit_type": "LENGTHUNIT"}
            if prefix:
                kwargs["prefix"] = prefix
            length_unit = ifcopenshell.api.run("unit.add_si_unit", self._file, **kwargs)

            area_unit = ifcopenshell.api.run(
                "unit.add_si_unit", self._file, unit_type="AREAUNIT"
            )
            volume_unit = ifcopenshell.api.run(
                "unit.add_si_unit", self._file, unit_type="VOLUMEUNIT"
            )

            ifcopenshell.api.run(
                "unit.assign_unit",
                self._file,
                units=[length_unit, area_unit, volume_unit]
            )
        else:
            raise NotImplementedError(
                f"LengthUnit.{unit.name} is not yet supported. "
                "Builders write unscaled numeric values; imperial unit scaling is not implemented. "
                "Use LengthUnit.METRE or LengthUnit.MILLIMETRE."
            )

        # Record author in IfcOwnerHistory if provided.
        if author:
            ifcopenshell.api.run(
                "owner.add_person",
                self._file,
                identification=author,
                family_name=author,
            )

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
        latitude: Optional[tuple[float, float, float]] = None,
        longitude: Optional[tuple[float, float, float]] = None,
        elevation: Optional[float] = None,
        location: Optional[tuple[float, float, float]] = None,
    ) -> SiteHandle:
        """
        Create an IfcSite and aggregate it under the project.

        Args:
            name:        Site name.
            description: Optional description.
            latitude:    Optional (degrees, minutes, seconds) tuple for geolocation.
                         When provided, stored in IfcSite.RefLatitude.
                         Example for Hofplein Rotterdam: (51, 55, 21)
            longitude:   Optional (degrees, minutes, seconds) tuple for geolocation.
                         When provided, stored in IfcSite.RefLongitude.
                         Example for Hofplein Rotterdam: (4, 28, 60)
            elevation:   Site elevation in meters (stored in RefElevation).
            location:    Optional (x, y, z) Cartesian origin for the site's
                         ObjectPlacement.  Use this when working in a real-world
                         coordinate system (e.g. RD New: (103647, 434819, 0)).
                         When omitted the site has no ObjectPlacement and elements
                         are placed in a local project coordinate system at (0,0,0).
        """
        site = ifcopenshell.api.run(
            "root.create_entity",
            self._file,
            ifc_class="IfcSite",
            name=name,
        )
        if description:
            site.Description = description
        if latitude is not None:
            site.RefLatitude = latitude
        if longitude is not None:
            site.RefLongitude = longitude
        if elevation is not None:
            site.RefElevation = elevation
        if location is not None:
            from ifckit.geometry import Vec, Plane
            from ifckit.builders._geom import local_placement
            origin = Vec(*location)
            plane = Plane(origin, Vec(1, 0, 0), Vec(0, 1, 0))
            site.ObjectPlacement = local_placement(self._file, plane)
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

        Args:
            site: The site to aggregate the alignment under (must be SiteHandle).
            name: Alignment name.
        """
        self._require_schema(IfcSchema.IFC4X3, "add_alignment")
        if not isinstance(site, SiteHandle):
            raise TypeError(
                f"add_alignment() expects a SiteHandle, got {type(site).__name__}. "
                "IfcAlignment must be aggregated under IfcSite, not under a bridge or part."
            )
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
