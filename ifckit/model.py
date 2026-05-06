"""
ifckit.model
============

IfcModel: builds and manages an IFC spatial hierarchy using ifcopenshell.

Supports IFC2X3 (legacy buildings), IFC4 (buildings) and IFC4X3 (bridges / infrastructure).
"""

from __future__ import annotations

import warnings as _warnings
from typing import TYPE_CHECKING, Optional, Union

import ifcopenshell
import ifcopenshell.api

from ifckit.handles import (
    AlignmentHandle,
    BridgeHandle,
    BridgePartHandle,
    BuildingHandle,
    EntityHandle,
    SiteHandle,
    StoreyHandle,
)
from ifckit.schema import IfcSchema, LengthUnit

if TYPE_CHECKING:
    from ifckit.elements.base import PendingElement

_UNIT_PREFIX: dict = {
    LengthUnit.METRE: None,
    LengthUnit.MILLIMETRE: "MILLI",
}


class IfcModel:
    """
    Manages an IFC spatial hierarchy and exposes a simple builder API.

    Args:
        name:   Project name (IfcProject.Name).
        schema: IfcSchema.IFC2X3, IfcSchema.IFC4 or IfcSchema.IFC4X3.
        author: Author name stored in IfcOwnerHistory (informational only).
                For IFC2X3 this is required for a valid file; when omitted
                ``"Unknown"`` is used.
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

        schema_str = schema.value
        self._file = ifcopenshell.file(schema=schema_str)

        # IFC2X3 requires OwnerHistory on every root entity.
        # Set up person + org + application before the first root.create_entity call
        # so that ifcopenshell's owner.settings can resolve them automatically.
        if schema == IfcSchema.IFC2X3:
            self._setup_owner_history(author)

        self._project = ifcopenshell.api.run(
            "root.create_entity",
            self._file,
            ifc_class="IfcProject",
            name=name,
        )

        if unit in _UNIT_PREFIX:
            prefix = _UNIT_PREFIX[unit]
            kwargs: dict = {"unit_type": "LENGTHUNIT"}
            if prefix:
                kwargs["prefix"] = prefix
            length_unit = ifcopenshell.api.run("unit.add_si_unit", self._file, **kwargs)

            area_unit = ifcopenshell.api.run("unit.add_si_unit", self._file, unit_type="AREAUNIT")
            volume_unit = ifcopenshell.api.run(
                "unit.add_si_unit", self._file, unit_type="VOLUMEUNIT"
            )
            angle_unit = ifcopenshell.api.run(
                "unit.add_si_unit", self._file, unit_type="PLANEANGLEUNIT"
            )

            ifcopenshell.api.run(
                "unit.assign_unit",
                self._file,
                units=[length_unit, area_unit, volume_unit, angle_unit],
            )
        else:
            raise NotImplementedError(
                f"LengthUnit.{unit.name} is not yet supported. "
                "Builders write unscaled numeric values; imperial unit scaling is not implemented. "
                "Use LengthUnit.METRE or LengthUnit.MILLIMETRE."
            )

        if author and schema != IfcSchema.IFC2X3:
            ifcopenshell.api.run(
                "owner.add_person",
                self._file,
                identification=author,
                family_name=author,
            )

        self._context = ifcopenshell.api.run(
            "context.add_context",
            self._file,
            context_type="Model",
        )

        self._body_context = self._file.create_entity(
            "IfcGeometricRepresentationSubContext",
            ContextIdentifier="Body",
            ContextType="Model",
            ParentContext=self._context,
            TargetView="MODEL_VIEW",
        )

        from ifckit.builders import default_registry

        self._registry = default_registry()
        self._type_cache: dict = {}

    # ------------------------------------------------------------------
    # High-level element API
    # ------------------------------------------------------------------

    def _validate_or_raise(self, pending: "PendingElement", stacklevel: int = 3) -> None:
        """Validate *pending*; emit warnings and raise ValueError on errors."""
        from ifckit.validator import validate

        result = validate(pending)
        for w in result.warnings:
            _warnings.warn(w, stacklevel=stacklevel)
        if not result.ok:
            raise ValueError(
                f"Validation failed for {type(pending).__name__} '{pending.name}':\n"
                + "\n".join(f"  - {e}" for e in result.errors)
            )

    def add(
        self,
        pending: "PendingElement",
        container: "Union[StoreyHandle, BridgePartHandle]",
    ) -> "EntityHandle":
        """
        Validate and build a pending element, placing it in *container*.

        Model B shortcut: if *pending* is a PendingWindow or PendingDoor with
        ``component_graph`` set and *container* is an EntityHandle wrapping a
        wall/slab host, the opening is generated automatically from the preset's
        ``opening_component`` section.

        Args:
            pending:   Any ``PendingElement`` subclass (PendingBeam, PendingWall, …).
            container: The spatial container — a ``StoreyHandle`` (IFC4 building),
                       a ``BridgePartHandle`` (IFC4X3 bridge), or an
                       ``EntityHandle`` wrapping a wall/slab host (Model B only).

        Returns:
            ``EntityHandle`` wrapping the created IFC entity.

        Raises:
            TypeError:    If *container* is not a recognised container type.
            LookupError:  If no builder is registered for the element type.
            ValueError:   If validation fails (message lists all errors).
        """
        # ------------------------------------------------------------------
        # Model B: PendingWindow/PendingDoor with component_graph + wall host
        # ------------------------------------------------------------------
        if (
            isinstance(container, EntityHandle)
            and getattr(pending, "component_graph", None) is not None
            and type(pending).__name__ in ("PendingWindow", "PendingDoor")
        ):
            return self._add_fill_model_b(pending, container)

        if not isinstance(container, (StoreyHandle, BridgePartHandle)):
            raise TypeError(
                f"model.add() expects a StoreyHandle or BridgePartHandle, "
                f"got {type(container).__name__}"
            )

        self._validate_or_raise(pending)

        try:
            builder = self._registry.get(pending.element_type)
        except KeyError:
            raise LookupError(
                f"No builder registered for element type {pending.element_type!r}. "
                "Register one via model._registry.register() or use default_registry()."
            )

        from ifckit.builders._geom import get_body_context

        ctx = get_body_context(self._file)
        entity = builder.build(self._file, pending, container.entity, ctx)
        return EntityHandle(entity, self)

    def _add_fill_model_b(
        self,
        pending: "PendingElement",
        host: "EntityHandle",
    ) -> "EntityHandle":
        """
        Model B internal: build opening + fill from a component_graph preset.

        Args:
            pending: PendingWindow or PendingDoor with plane + component_graph.
            host:    EntityHandle wrapping the IfcWall/IfcSlab host.

        Returns:
            EntityHandle wrapping the created IfcWindow or IfcDoor.
        """
        from ifckit.builders._geom import get_body_context
        from ifckit.builders.door_window import build_door_model_b, build_window_model_b

        ctx = get_body_context(self._file)
        storey = self._find_containing_storey(host.entity)

        if type(pending).__name__ == "PendingWindow":
            entity = build_window_model_b(self._file, pending, host.entity, storey, ctx)
        else:
            entity = build_door_model_b(self._file, pending, host.entity, storey, ctx)
        return EntityHandle(entity, self)

    def _find_containing_storey(
        self,
        entity: "ifcopenshell.entity_instance",
    ) -> "ifcopenshell.entity_instance":
        """
        Walk IfcRelContainedInSpatialStructure to find the IfcBuildingStorey
        that directly contains *entity*.

        Returns:
            IfcBuildingStorey entity.

        Raises:
            ValueError: If no containing storey is found.
        """
        for rel in self._file.by_type("IfcRelContainedInSpatialStructure"):
            if entity in rel.RelatedElements:
                structure = rel.RelatingStructure
                if structure.is_a("IfcBuildingStorey"):
                    return structure
        raise ValueError(
            f"_find_containing_storey: entity {entity!r} is not contained "
            "in any IfcBuildingStorey in this file."
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
        if description is not None:
            site.Description = description
        if latitude is not None:
            site.RefLatitude = latitude
        if longitude is not None:
            site.RefLongitude = longitude
        if elevation is not None:
            site.RefElevation = elevation
        if location is not None:
            from ifckit.builders._geom import local_placement
            from ifckit.geometry import Plane, Vec

            origin = Vec(*location)
            plane = Plane(origin, Vec(1, 0, 0), Vec(0, 1, 0))
            site.ObjectPlacement = local_placement(self._file, plane)
        ifcopenshell.api.run(
            "aggregate.assign_object",
            self._file,
            products=[site],
            relating_object=self._project,
        )
        return SiteHandle(site, self)

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
        if description is not None:
            building.Description = description
        ifcopenshell.api.run(
            "aggregate.assign_object",
            self._file,
            products=[building],
            relating_object=site.entity,
        )
        return BuildingHandle(building, self)

    def add_storey(
        self,
        building: BuildingHandle,
        name: str,
        elevation: float = 0.0,
    ) -> StoreyHandle:
        """
        Create an IfcBuildingStorey and aggregate it under a building.

        The storey receives an IfcLocalPlacement with the elevation as Z-offset,
        so that element placements can be expressed relative to the storey origin
        (local Z = 0 at floor level).
        """
        storey = ifcopenshell.api.run(
            "root.create_entity",
            self._file,
            ifc_class="IfcBuildingStorey",
            name=name,
        )
        storey.Elevation = elevation

        from ifckit.builders._geom import local_placement
        from ifckit.geometry import Plane, Vec

        origin = Vec(0.0, 0.0, float(elevation))
        plane = Plane(origin, Vec(1, 0, 0), Vec(0, 1, 0))
        storey.ObjectPlacement = local_placement(self._file, plane)

        ifcopenshell.api.run(
            "aggregate.assign_object",
            self._file,
            products=[storey],
            relating_object=building.entity,
        )
        return StoreyHandle(storey, self)

    def add_drawing(
        self,
        name: str,
        target_view: str = "PLAN_VIEW",
        position: tuple[float, float, float] = (0.0, 0.0, 0.0),
        x_axis: tuple[float, float, float] = (1.0, 0.0, 0.0),
        z_axis: tuple[float, float, float] = (0.0, 0.0, -1.0),
    ) -> "ifcopenshell.entity_instance":
        """Create a Bonsai-compatible drawing annotation in the IFC file.

        Creates an ``IfcAnnotation[ObjectType="DRAWING"]`` with an
        ``EPset_Drawing`` property set and an associated ``IfcGroup``,
        matching the structure Bonsai (BlenderBIM) uses for floor-plan and
        section drawings.

        The annotation can be consumed by ``ifcopenshell.draw`` via::

            draw_settings(drawing_object_type="DRAWING")

        Args:
            name:        Drawing name (e.g. ``"Section A-A"``).
            target_view: IFC drawing target view.  One of ``"PLAN_VIEW"``,
                         ``"SECTION_VIEW"``, ``"ELEVATION_VIEW"``,
                         ``"REFLECTED_PLAN_VIEW"``, ``"MODEL_VIEW"``.
                         Defaults to ``"PLAN_VIEW"``.
            position:    Origin of the section plane in IFC file units.
            x_axis:      Local X axis of the section plane (right direction
                         of the drawing).  Defaults to world X ``(1,0,0)``.
            z_axis:      View direction / plane normal.  IfcOpenShell's
                         SvgSerializer interprets this as the camera look-at
                         direction.  For a plan view looking down use
                         ``(0,0,-1)`` (default); for a section facing north
                         use ``(0,-1,0)``.

        Returns:
            The created ``IfcAnnotation`` entity.
        """
        from ifckit.builders._geom import axis2placement3d
        from ifckit.geometry import Vec

        origin = Vec(*[float(v) for v in position])
        z_vec = Vec(*[float(v) for v in z_axis])
        x_vec = Vec(*[float(v) for v in x_axis])

        # Bonsai stores the placement Axis as the camera's outward normal
        # (pointing away from the scene toward the viewer), which is the
        # negation of the view/look-at direction the user supplies.
        # e.g. user z_axis=(0,0,-1) "looking down" → IFC Axis=(0,0,1).
        placement_z = Vec(-z_vec.x, -z_vec.y, -z_vec.z)

        annotation = ifcopenshell.api.run(
            "root.create_entity",
            self._file,
            ifc_class="IfcAnnotation",
            name=name,
        )
        annotation.ObjectType = "DRAWING"
        # Note: PredefinedType on IfcAnnotation only accepts schema-specific enums
        # (infrastructure types in IFC4X3, none in IFC4/IFC2X3).
        # Bonsai uses ObjectType="DRAWING" as the convention, not PredefinedType.

        ax = axis2placement3d(self._file, origin, placement_z, x_vec)
        annotation.ObjectPlacement = self._file.create_entity(
            "IfcLocalPlacement",
            PlacementRelTo=None,
            RelativePlacement=ax,
        )

        # Camera box representation — matches Bonsai's IfcCsgSolid/IfcBlock
        # convention exactly. The SvgSerializer matches the annotation GUID in
        # the geometry iterator and extracts the section plane from the block.
        #
        # Bonsai convention (reverse-engineered from reference file):
        #   - IfcCsgSolid wrapping an IfcBlock
        #   - Block centred on the annotation origin: position (-half, -half, -depth)
        #   - Annotation Z-axis = (0,0,1) — camera looks toward -Z in world space
        #   - Block: 50 m × 50 m × 10 m (large enough for any model)
        half = 25000.0  # mm — half of 50 m box in XY
        depth = 10000.0  # mm — 10 m clip depth below the section plane

        # Use the 'Body' subcontext — the geometry iterator only processes
        # representations under subcontexts, not the root Model context.
        model_ctx = next(
            (
                c
                for c in self._file.by_type("IfcGeometricRepresentationContext")
                if not c.is_a("IfcGeometricRepresentationSubContext") and c.ContextType == "Model"
            ),
            self._file.by_type("IfcGeometricRepresentationContext")[0],
        )
        geom_ctx = next(
            (
                c
                for c in self._file.by_type("IfcGeometricRepresentationSubContext")
                if c.ContextIdentifier == "Body" and c.ParentContext == model_ctx
            ),
            None,
        )
        if geom_ctx is None:
            geom_ctx = self._file.create_entity(
                "IfcGeometricRepresentationSubContext",
                ContextIdentifier="Body",
                ContextType="Model",
                ParentContext=model_ctx,
                TargetView="MODEL_VIEW",
            )

        # Block positioned so annotation origin is at the top face centre.
        # Local coords: X and Y centred (±half), Z from -depth to 0.
        block_pos = self._file.create_entity(
            "IfcAxis2Placement3D",
            Location=self._file.create_entity(
                "IfcCartesianPoint", Coordinates=(-half, -half, -depth)
            ),
        )
        block = self._file.create_entity(
            "IfcBlock",
            Position=block_pos,
            XLength=half * 2,
            YLength=half * 2,
            ZLength=depth,
        )
        csg = self._file.create_entity("IfcCsgSolid", TreeRootExpression=block)
        shape_rep = self._file.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=geom_ctx,
            RepresentationIdentifier="Body",
            RepresentationType="CSG",
            Items=[csg],
        )
        annotation.Representation = self._file.create_entity(
            "IfcProductDefinitionShape",
            Representations=[shape_rep],
        )

        # EPset_Drawing — Bonsai's standard property set for drawings
        pset = ifcopenshell.api.run(
            "pset.add_pset",
            self._file,
            product=annotation,
            name="EPset_Drawing",
        )
        scale_str = "1/100"
        human_scale = "1:100"
        ifcopenshell.api.run(
            "pset.edit_pset",
            self._file,
            pset=pset,
            properties={
                "TargetView": target_view,
                "Scale": scale_str,
                "HumanScale": human_scale,
                "HasUnderlay": False,
                "HasLinework": True,
                "HasAnnotation": False,
                "GlobalReferencing": True,
                "Stylesheet": "",
                "Markers": "",
                "Symbols": "",
                "Patterns": "",
                "ShadingStyles": "",
                "CurrentShadingStyle": "",
            },
        )

        # IfcGroup — Bonsai groups each drawing's annotations under a named group
        group = ifcopenshell.api.run("group.add_group", self._file)
        ifcopenshell.api.run(
            "group.edit_group",
            self._file,
            group=group,
            attributes={"Name": name, "ObjectType": "DRAWING"},
        )
        ifcopenshell.api.run(
            "group.assign_group",
            self._file,
            group=group,
            products=[annotation],
        )

        return annotation

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
        return EntityHandle(entity, self)

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
        if description is not None:
            bridge.Description = description
        ifcopenshell.api.run(
            "aggregate.assign_object",
            self._file,
            products=[bridge],
            relating_object=site.entity,
        )
        return BridgeHandle(bridge, self)

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
        return BridgePartHandle(part, self)

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
        return AlignmentHandle(alignment, self)

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
        return EntityHandle(entity, self)

    # ------------------------------------------------------------------
    # Openings, doors, windows and type objects (M2 / M3)
    # ------------------------------------------------------------------

    def add_opening(
        self,
        pending,  # PendingOpening
        host: "EntityHandle",
        container: "StoreyHandle",
    ) -> "EntityHandle":
        """
        Create an ``IfcOpeningElement`` voiding *host* and place it in *container*.

        Args:
            pending:   A ``PendingOpening`` instance.
            host:      ``EntityHandle`` wrapping the host element
                       (IfcWall, IfcSlab or IfcRoof).
            container: ``StoreyHandle`` for spatial containment.

        Returns:
            ``EntityHandle`` wrapping the created ``IfcOpeningElement``.

        Raises:
            TypeError:  If *host* or *container* are wrong types.
            ValueError: If *pending* fails validation.
        """
        from ifckit.builders._geom import get_body_context
        from ifckit.builders.opening import build_opening
        from ifckit.elements.opening import OPENING_HOST_IFC_CLASSES

        if not isinstance(host, EntityHandle):
            raise TypeError(f"add_opening: host must be an EntityHandle, got {type(host).__name__}")
        if not isinstance(container, StoreyHandle):
            raise TypeError(
                f"add_opening: container must be a StoreyHandle, got {type(container).__name__}"
            )

        # Validate that host is an allowed IFC class.
        host_class = host.entity.is_a()
        if not any(host.entity.is_a(cls) for cls in OPENING_HOST_IFC_CLASSES):
            raise ValueError(
                f"add_opening: host entity is {host_class!r}, "
                f"which is not in the allowed host classes: {sorted(OPENING_HOST_IFC_CLASSES)}"
            )

        self._validate_or_raise(pending)

        ctx = get_body_context(self._file)
        opening_entity = build_opening(self._file, pending, host.entity, container.entity, ctx)
        return EntityHandle(opening_entity, self)

    def add_door(
        self,
        pending,  # PendingDoor
        opening: "EntityHandle",
        container: "StoreyHandle",
        door_type: "Optional[EntityHandle]" = None,
        opening_anchor: str = "s",
    ) -> "EntityHandle":
        """
        Create an ``IfcDoor`` filling *opening* and place it in *container*.

        Args:
            pending:        A ``PendingDoor`` instance.
            opening:        ``EntityHandle`` wrapping the ``IfcOpeningElement``.
            container:      ``StoreyHandle`` for spatial containment.
            door_type:      Optional ``EntityHandle`` wrapping an ``IfcDoorType``
                            entity to assign via ``IfcRelDefinesByType``.
            opening_anchor: Anchor of the parent ``PendingOpening`` (default ``"s"``).

        Returns:
            ``EntityHandle`` wrapping the created ``IfcDoor``.
        """
        from ifckit.builders._geom import get_body_context
        from ifckit.builders.door_window import build_door

        if not isinstance(opening, EntityHandle):
            raise TypeError(
                f"add_door: opening must be an EntityHandle, got {type(opening).__name__}"
            )
        if not isinstance(container, StoreyHandle):
            raise TypeError(
                f"add_door: container must be a StoreyHandle, got {type(container).__name__}"
            )
        if not opening.entity.is_a("IfcOpeningElement"):
            raise ValueError(
                f"add_door: opening entity is {opening.entity.is_a()!r}, expected IfcOpeningElement"
            )

        self._validate_or_raise(pending)

        ctx = get_body_context(self._file)
        type_entity = door_type.entity if door_type is not None else None
        door_entity = build_door(
            self._file,
            pending,
            opening.entity,
            container.entity,
            ctx,
            type_entity,
            opening_anchor=opening_anchor,
        )
        return EntityHandle(door_entity, self)

    def add_window(
        self,
        pending,  # PendingWindow
        opening: "EntityHandle",
        container: "StoreyHandle",
        window_type: "Optional[EntityHandle]" = None,
        opening_anchor: str = "s",
    ) -> "EntityHandle":
        """
        Create an ``IfcWindow`` filling *opening* and place it in *container*.

        Args:
            pending:        A ``PendingWindow`` instance.
            opening:        ``EntityHandle`` wrapping the ``IfcOpeningElement``.
            container:      ``StoreyHandle`` for spatial containment.
            window_type:    Optional ``EntityHandle`` wrapping an ``IfcWindowType``.
            opening_anchor: Anchor of the parent ``PendingOpening`` (default ``"s"``).

        Returns:
            ``EntityHandle`` wrapping the created ``IfcWindow``.
        """
        from ifckit.builders._geom import get_body_context
        from ifckit.builders.door_window import build_window

        if not isinstance(opening, EntityHandle):
            raise TypeError(
                f"add_window: opening must be an EntityHandle, got {type(opening).__name__}"
            )
        if not isinstance(container, StoreyHandle):
            raise TypeError(
                f"add_window: container must be a StoreyHandle, got {type(container).__name__}"
            )
        if not opening.entity.is_a("IfcOpeningElement"):
            raise ValueError(
                f"add_window: opening entity is {opening.entity.is_a()!r}, "
                "expected IfcOpeningElement"
            )

        self._validate_or_raise(pending)

        ctx = get_body_context(self._file)
        type_entity = window_type.entity if window_type is not None else None
        window_entity = build_window(
            self._file,
            pending,
            opening.entity,
            container.entity,
            ctx,
            type_entity,
            opening_anchor=opening_anchor,
            graph_name=getattr(pending, "component_graph", None),
        )
        return EntityHandle(window_entity, self)

    def add_door_type(self, pending) -> "EntityHandle":  # pending: PendingDoorType
        """
        Create (or retrieve from cache) an ``IfcDoorType`` entity.

        If a type with the same ``type_key`` already exists, the cached
        entity is returned immediately.  If a type with the same key
        but different parameters is requested, ``ValueError`` is raised.

        Args:
            pending: A ``PendingDoorType`` instance.

        Returns:
            ``EntityHandle`` wrapping the ``IfcDoorType`` entity.
        """
        from ifckit.builders.types import build_door_type

        return self._add_type(pending, build_door_type)

    def add_window_type(self, pending) -> "EntityHandle":  # pending: PendingWindowType
        """
        Create (or retrieve from cache) an ``IfcWindowType`` entity.

        If a type with the same ``type_key`` already exists, the cached
        entity is returned immediately.  If a type with the same key
        but different parameters is requested, ``ValueError`` is raised.

        Args:
            pending: A ``PendingWindowType`` instance.

        Returns:
            ``EntityHandle`` wrapping the ``IfcWindowType`` entity.
        """
        from ifckit.builders.types import build_window_type

        return self._add_type(pending, build_window_type)

    def _add_type(self, pending, builder_fn) -> "EntityHandle":
        """
        Internal: check type cache, create if absent, enforce collision rule.
        """
        key = pending.type_key
        if key in self._type_cache:
            cached_pending, cached_entity = self._type_cache[key]
            # Collision check: same key must match same to_dict payload.
            if cached_pending.to_dict() != pending.to_dict():
                raise ValueError(
                    f"Type key {key!r} is already registered with different parameters.\n"
                    f"  Existing : {cached_pending.to_dict()}\n"
                    f"  Requested: {pending.to_dict()}"
                )
            return EntityHandle(cached_entity, self)

        entity = builder_fn(self._file, pending)
        self._type_cache[key] = (pending, entity)
        return EntityHandle(entity, self)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Write the IFC file to disk."""
        self._file.write(path)

    def to_string(self) -> str:
        """Serialise the IFC model to a STEP string (no file I/O)."""
        return self._file.to_string()

    def export(self, path: str) -> None:
        """
        Export the model to a geometry format via ifcopenshell serializers.

        The output format is inferred from the file extension:

        ============  ========================================================
        Extension     Format
        ============  ========================================================
        ``.ifc``      Native IFC STEP (same as ``save()``)
        ``.obj``      Wavefront OBJ (+ a ``.mtl`` sidecar written alongside)
        ``.glb``      Binary glTF 2.0
        ``.gltf``     Binary glTF 2.0 (same as ``.glb``)
        ``.svg``      2-D SVG plan views
        ``.xml``      ifcXML
        ``.dae``      Collada (only if ifcopenshell is built with Collada support)
        ``.ttl``      TTL/WKT geometry (only if supported by installed build)
        ============  ========================================================

        Args:
            path: Destination file path including extension.

        Raises:
            ValueError:  If the extension is not recognised.
            ImportError: If the requested serializer is not available in the
                         current ifcopenshell build (e.g. Collada, HDF5).

        Example::

            model.save("output/bridge.ifc")        # always works
            model.export("output/bridge.obj")      # Wavefront OBJ + .mtl
            model.export("output/bridge.glb")      # binary glTF
            model.export("output/bridge.svg")      # SVG floor plan
        """
        import os
        import tempfile

        ext = os.path.splitext(path)[1].lower().lstrip(".")

        if ext == "ifc":
            self.save(path)
            return

        try:
            import ifcopenshell.geom as _geom
        except ImportError as exc:
            raise ImportError(
                "ifcopenshell.geom is required for geometry export. "
                "Make sure ifcopenshell is installed with geometry support."
            ) from exc

        try:
            serializer_factory = _geom.serializers.guess_from_extension(path)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        if serializer_factory is None:
            raise ImportError(
                f"The serializer for .{ext} is not available in this ifcopenshell build."
            )

        geom_settings = _geom.settings()
        geom_settings.set(geom_settings.USE_WORLD_COORDS, True)
        s_settings = _geom.serializer_settings()

        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self._file.write(tmp_path)

            it = _geom.iterator(geom_settings, tmp_path)

            if ext == "obj":
                mtl_path = os.path.splitext(path)[0] + ".mtl"
                serializer = serializer_factory(path, mtl_path, geom_settings, s_settings)
            else:
                serializer = serializer_factory(path, geom_settings, s_settings)

            serializer.setFile(it.file)
            serializer.writeHeader()

            if it.initialize():
                while True:
                    serializer.write(it.get())
                    if not it.next():
                        break

            serializer.finalize()
        finally:
            os.unlink(tmp_path)

    def export_step(self, output_path: str) -> None:
        """Export the model to an ISO 10303 STEP file via ``ifcconvert``.

        ``ifcconvert`` must be installed and available on ``PATH``.  It is
        part of the `IfcOpenShell distribution
        <https://ifcopenshell.org/ifcconvert>`_.

        The model is first written to a temporary ``.ifc`` file, then
        ``ifcconvert`` converts it to STEP (``.stp`` / ``.step``).

        Args:
            output_path: Destination path; should end in ``.stp`` or ``.step``.

        Raises:
            FileNotFoundError: If ``ifcconvert`` is not found on ``PATH``.
            RuntimeError:      If ``ifcconvert`` exits with a non-zero code.

        Example::

            model.export_step("output/bridge.stp")
        """
        import os
        import shutil
        import subprocess
        import tempfile

        ifcconvert = shutil.which("ifcconvert")
        if ifcconvert is None:
            raise FileNotFoundError(
                "ifcconvert not found on PATH. "
                "Install it from https://ifcopenshell.org/ifcconvert or add it to PATH."
            )

        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self._file.write(tmp_path)
            result = subprocess.run(
                [ifcconvert, tmp_path, output_path],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"ifcconvert failed (exit {result.returncode}):\n"
                    f"{result.stderr.strip() or result.stdout.strip()}"
                )
        finally:
            os.unlink(tmp_path)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_schema(self, required: IfcSchema, method: str) -> None:
        if self.schema != required:
            raise ValueError(
                f"IfcModel.{method}() requires schema {required.value}, "
                f"but model uses {self.schema.value}"
            )

    def _setup_owner_history(self, author: str) -> None:
        """Set up the mandatory IFC2X3 OwnerHistory entities.

        IFC2X3 requires ``IfcOwnerHistory`` on every root entity.
        ifcopenshell resolves the active user and application via
        ``owner.settings.get_user()`` / ``get_application()``, which look for
        the first ``IfcPersonAndOrganization`` and ``IfcApplication`` in the
        file.  We create them here — before the first ``root.create_entity``
        call — so that all subsequent API calls succeed automatically.

        Args:
            author: Author name; ``"Unknown"`` is used when empty.
        """
        name = author or "Unknown"
        person = ifcopenshell.api.run(
            "owner.add_person",
            self._file,
            identification=name,
            family_name=name,
        )
        org = ifcopenshell.api.run(
            "owner.add_organisation",
            self._file,
            name="Unknown",
        )
        ifcopenshell.api.run(
            "owner.add_person_and_organisation",
            self._file,
            person=person,
            organisation=org,
        )
        ifcopenshell.api.run(
            "owner.add_application",
            self._file,
            application_developer=org,
            version="1",
            application_full_name="ifckit",
            application_identifier="ifckit",
        )

    @property
    def ifc_file(self) -> ifcopenshell.file:
        """Direct access to the underlying ifcopenshell file (advanced use)."""
        return self._file

    def clear(self) -> int:
        """
        Remove all products from the entire model (all sites, buildings, storeys,
        bridge parts).

        Traverses the full spatial hierarchy under IfcProject and removes every
        product found in a ``ContainsElements`` relationship.

        Returns:
            The number of products removed.
        """
        removed = 0

        def _remove_from(container) -> None:
            nonlocal removed
            for rel in getattr(container, "ContainsElements", None) or []:
                for product in list(rel.RelatedElements):
                    self._file.remove(product)
                    removed += 1
            # recurse into aggregated children
            for rel in getattr(container, "IsDecomposedBy", None) or []:
                for child in rel.RelatedObjects:
                    _remove_from(child)

        for rel in getattr(self._project, "IsDecomposedBy", None) or []:
            for child in rel.RelatedObjects:
                _remove_from(child)

        return removed

    def _clear_container(self, container) -> int:
        """
        Remove all products contained in a spatial container (storey, building, site, etc).

        Args:
            container: An ifcopenshell entity (IfcBuildingStorey, IfcBuilding, IfcSite, etc).

        Returns:
            The number of elements removed.
        """
        removed = 0
        for rel in container.ContainsElements or []:
            for product in list(rel.RelatedElements):
                self._file.remove(product)
                removed += 1
        return removed

    def preview_rhino_curves(
        self,
        clear: bool = True,
        hlr_poly: bool = True,
        mesher_deflection: Optional[float] = None,
    ) -> dict:
        """Import the model into the active Rhino document as 2-D curves and
        hatches derived from section-plane drawings.

        Each IFC element's section-cut outline and projection are placed as
        ``PolylineCurve`` / ``PolyCurve`` objects on a layered hierarchy::

            IFC-SVG / <drawing name> / cut / IfcWall
            IFC-SVG / <drawing name> / cut_hatch / IfcWall
            IFC-SVG / <drawing name> / projection / IfcWall
            IFC-SVG / <drawing name> / projection_hatch / IfcWall

        Closed paths that carry an IFC material fill colour are also added as
        ``Hatch`` objects on the corresponding ``_hatch`` layer.  The hatch
        pattern is resolved per-element from ``EPset_IfcKit.HatchPattern``,
        falling back to ``"Solid"``.

        Requires Rhino 8+ with ``ifcopenshell.draw`` support.

        Args:
            clear:              If *True*, remove existing IFC-SVG objects before importing.
            hlr_poly:           Use polygonal HLR (faster, Bonsai default).
                                Set ``False`` for exact BREP HLR.
            mesher_deflection:  OCC mesher linear deflection in metres.
                                ``None`` = ifcopenshell default.

        Returns:
            ``{"curves": int, "hatches": int}``
        """
        from ifckit.rhino_import import IfcSvgImporter

        importer = IfcSvgImporter()
        if clear:
            importer.clear()
        return importer.import_model(self, hlr_poly=hlr_poly, mesher_deflection=mesher_deflection)

    def preview_rhino(
        self, mesh_quality: str = "default", clear: bool = True, skip_voids: bool = False
    ) -> int:
        """Import the model into the active Rhino document as meshes.

        Requires Rhino 8+ with ifcopenshell installed. Intended for use
        in Grasshopper to preview the IFC model without saving to disk.

        Args:
            mesh_quality: Tessellation quality preset
                          (superfine/fine/default/coarse/supercoarse).
            clear: If True, clear existing IFC meshes before import.
            skip_voids: If True, skip IfcOpeningElement geometry (voids).

        Returns:
            Number of elements imported.
        """
        from ifckit.rhino_import import IfcMeshImporter

        importer = IfcMeshImporter(
            clear_on_import=clear,
            mesh_quality=mesh_quality,
            skip_voids=skip_voids,
        )
        return importer.import_model(self)
