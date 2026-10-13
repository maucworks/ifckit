"""
ifckit.model
============

IfcModel: builds and manages an IFC spatial hierarchy using ifcopenshell.

Supports IFC2X3 (legacy buildings), IFC4 (buildings) and IFC4X3 (bridges / infrastructure).
"""

from __future__ import annotations

import hashlib as _hashlib
import json as _json
import warnings as _warnings
from typing import TYPE_CHECKING, Collection, Iterator, Optional, Union

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


def _delta_signature(elem: dict) -> str:
    """Change hash for an apply_delta element dict.

    Ignores ``global_id`` (an identity override, not a change) and nested
    ``"id"`` keys: geometry objects (``Vec``/``Plane``/…) mint a random
    identity per instance, so two semantically identical dicts would
    otherwise never compare equal. The top-level ``"id"``/``"host_id"``
    keys are stable caller keys and stay in the hash.
    """

    def _strip(node, top: bool):
        if isinstance(node, dict):
            return {
                key: _strip(value, False)
                for key, value in node.items()
                if (top or key != "id") and key != "global_id"
            }
        if isinstance(node, (list, tuple)):
            return [_strip(value, False) for value in node]
        return node

    canonical = _json.dumps(_strip(elem, True), sort_keys=True, default=str)
    return _hashlib.md5(canonical.encode()).hexdigest()


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

    @classmethod
    def from_file(cls, ifc_file: "ifcopenshell.file") -> "IfcModel":
        """
        Wrap an existing ``ifcopenshell.file`` in an ``IfcModel`` without
        creating a new project.  All builders and helper methods work as
        normal; ``save()`` writes back to the same file object.

        This is useful for adding ifckit-built elements (walls, windows, …)
        to a project that was already opened externally — e.g. the active
        Bonsai / BlenderBIM project.

        The file must already contain exactly one ``IfcProject`` and a
        ``Model/Body/MODEL_VIEW`` geometric representation sub-context.
        If the body sub-context is missing it is created automatically.

        Args:
            ifc_file: An ``ifcopenshell.file`` instance, e.g. from
                      ``ifcopenshell.open("project.ifc")`` or from
                      Bonsai's ``tool.Ifc.get()``.

        Returns:
            ``IfcModel`` wrapping *ifc_file*.

        Raises:
            ValueError: If the file contains no ``IfcProject``.

        Example (Bonsai Scripting editor)::

            import bonsai.tool as tool
            from ifckit.model import IfcModel
            from ifckit.handles import StoreyHandle

            model = IfcModel.from_file(tool.Ifc.get())
            storey_entity = tool.Ifc.get().by_type("IfcBuildingStorey")[0]
            storey = StoreyHandle(storey_entity, model)
            storey.add(PendingWall(...))
            # Changes are live in Bonsai; save with Ctrl+S.
        """
        import ifcopenshell.util.representation
        import ifcopenshell.util.unit

        projects = ifc_file.by_type("IfcProject")
        if not projects:
            raise ValueError("from_file(): the supplied file contains no IfcProject.")

        obj = cls.__new__(cls)

        # Core file reference
        obj._file = ifc_file
        obj._project = projects[0]

        # Schema
        schema_map = {
            "IFC2X3": IfcSchema.IFC2X3,
            "IFC4": IfcSchema.IFC4,
            "IFC4X3_ADD2": IfcSchema.IFC4X3,
            "IFC4X3": IfcSchema.IFC4X3,
        }
        obj.schema = schema_map.get(ifc_file.schema, IfcSchema.IFC4)

        # Unit — derive from file's length unit scale
        unit_scale = ifcopenshell.util.unit.calculate_unit_scale(ifc_file)
        # 0.001 = millimetres, 1.0 = metres (anything else → metres)
        obj.unit = LengthUnit.MILLIMETRE if abs(unit_scale - 0.001) < 1e-9 else LengthUnit.METRE

        # Author — informational only, not writable back
        obj.name = obj._project.Name or "Unnamed Project"
        obj.author = ""

        # Geometric representation contexts
        body_ctx = ifcopenshell.util.representation.get_context(
            ifc_file, "Model", "Body", "MODEL_VIEW"
        )
        if body_ctx is None:
            # Find or create the parent Model context
            model_ctx = next(
                (
                    c
                    for c in ifc_file.by_type("IfcGeometricRepresentationContext")
                    if not c.is_a("IfcGeometricRepresentationSubContext")
                    and c.ContextType == "Model"
                ),
                None,
            )
            if model_ctx is None:
                model_ctx = ifcopenshell.api.run(
                    "context.add_context", ifc_file, context_type="Model"
                )
            body_ctx = ifc_file.create_entity(
                "IfcGeometricRepresentationSubContext",
                ContextIdentifier="Body",
                ContextType="Model",
                ParentContext=model_ctx,
                TargetView="MODEL_VIEW",
            )
        # _context = the parent Model context of the body sub-context
        obj._context = body_ctx.ParentContext

        # Builders registry + type cache
        from ifckit.builders import default_registry

        obj._registry = default_registry()
        obj._type_cache = {}

        # Incremental patch state (apply_delta): stable key -> GlobalId,
        # signature, host key and handle. Empty for wrapped files.
        obj._delta_guids = {}
        obj._delta_sigs = {}
        obj._delta_hosts = {}
        obj._delta_handles = {}

        return obj

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

        schema_str = schema.to_ifcopenshell()
        self._file = ifcopenshell.file(schema=schema_str)  # type: ignore[arg-type]

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

        # Create Body sub-context for geometry representation. The reference
        # is not cached since get_body_context() retrieves it dynamically as needed.
        self._file.create_entity(
            "IfcGeometricRepresentationSubContext",
            ContextIdentifier="Body",
            ContextType="Model",
            ParentContext=self._context,
            TargetView="MODEL_VIEW",
        )

        from ifckit.builders import default_registry

        self._registry = default_registry()
        self._type_cache: dict = {}

        # Incremental patch state (apply_delta): stable key -> GlobalId,
        # signature, host key and handle.
        self._delta_guids: dict = {}
        self._delta_sigs: dict = {}
        self._delta_hosts: dict = {}
        self._delta_handles: dict = {}

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
        container: "Union[StoreyHandle, BridgePartHandle, EntityHandle]",
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
        handle = EntityHandle(entity, self)

        self._attach_footprint(handle, pending)

        return handle

    def _attach_footprint(
        self,
        handle: "EntityHandle",
        pending,
    ) -> None:
        """Look up the component's ``footprint()`` method and store curves on *handle*."""
        graph_name = getattr(pending, "component_graph", None)
        if not graph_name:
            return

        from ifckit.components import get_component

        comp_cls = get_component(graph_name)
        if comp_cls is None:
            return
        fp_method = getattr(comp_cls, "footprint", None)
        if fp_method is None:
            return

        p_plane = getattr(pending, "plane", None)
        if p_plane is None:
            return

        params: dict = {
            "w": getattr(pending, "overall_width", 0),
            "h": getattr(pending, "overall_height", 0),
        }
        for attr in ("operation_type", "window_type"):
            val = getattr(pending, attr, None)
            if val is not None:
                params[attr] = val
        extra = getattr(pending, "parameters", None) or {}
        params.update(extra)

        curves = fp_method(p_plane, params["w"], params["h"], params)

        # Transform curves from world space to entity-local coordinate system.
        # Footprint methods generate world-space curves, but IfcShapeRepresentation
        # on the entity expects coordinates relative to the entity's ObjectPlacement.
        if p_plane is not None:
            curves = self._footprint_to_local(curves, p_plane)

        handle.footprint_curves = curves
        self._attach_footprint_representation(handle, curves)

    def _attach_footprint_representation(
        self,
        handle: "EntityHandle",
        curves,
    ) -> None:
        """Append a 'FootPrint' IfcShapeRepresentation to the entity itself.

        Per IFC4 spec (FootPrint Geometry concept template), presentation
        geometry directly related to a single product belongs on the product's
        ``IfcProductDefinitionShape`` as an additional ``IfcShapeRepresentation``
        with ``RepresentationIdentifier='FootPrint'`` and
        ``RepresentationType='GeometricCurveSet'``, items wrapped in a single
        ``IfcGeometricCurveSet``.
        """
        if not curves:
            return
        from ifckit.builders._geom import get_or_create_footprint_context
        from ifckit.types.ifc_curves import curves_to_ifc

        ifc_curves = curves_to_ifc(self._file, curves)
        if not ifc_curves:
            return

        ctx = get_or_create_footprint_context(self._file)
        curve_set = self._file.create_entity(
            "IfcGeometricCurveSet",
            Elements=ifc_curves,
        )
        shape_rep = self._file.create_entity(
            "IfcShapeRepresentation",
            ContextOfItems=ctx,
            RepresentationIdentifier="FootPrint",
            RepresentationType="GeometricCurveSet",
            Items=[curve_set],
        )

        prod_def = handle.entity.Representation
        if prod_def is None:
            handle.entity.Representation = self._file.create_entity(
                "IfcProductDefinitionShape",
                Representations=[shape_rep],
            )
        else:
            prod_def.Representations = list(prod_def.Representations) + [shape_rep]

    @staticmethod
    def _footprint_to_local(curves, plane):
        """Transform world-space footprint curves to entity-local coordinates."""
        from ifckit.geometry import Arc, Line

        z_axis = plane.z_axis
        result = []
        for c in curves:
            if isinstance(c, Line):
                result.append(
                    Line(
                        IfcModel._world_to_local(c.start, plane, z_axis),
                        IfcModel._world_to_local(c.end, plane, z_axis),
                    )
                )
            elif isinstance(c, Arc):
                result.append(
                    Arc(
                        IfcModel._world_to_local(c.center, plane, z_axis),
                        IfcModel._dir_to_local(c.normal, plane, z_axis),
                        IfcModel._world_to_local(c.start, plane, z_axis),
                        c.angle,
                    )
                )
            else:
                result.append(c)
        return result

    @staticmethod
    def _world_to_local(pt, plane, z_axis):
        from ifckit.geometry import Vec

        delta = pt - plane.origin
        return Vec(
            delta @ plane.x_axis,
            delta @ plane.y_axis,
            delta @ z_axis,
        )

    @staticmethod
    def _dir_to_local(dir_vec, plane, z_axis):
        from ifckit.geometry import Vec

        return Vec(
            dir_vec @ plane.x_axis,
            dir_vec @ plane.y_axis,
            dir_vec @ z_axis,
        )

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
        import ifcopenshell.util.unit as unit_util

        unit_scale = unit_util.calculate_unit_scale(self._file)
        half = 25.0 / unit_scale  # 25 m (halve 50 m box) in bestandseenheden
        depth = 10.0 / unit_scale  # 10 m clip-diepte in bestandseenheden

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
        opening_anchor: str = "sw",
    ) -> "EntityHandle":
        """
        Create an ``IfcDoor`` filling *opening* and place it in *container*.

        Args:
            pending:        A ``PendingDoor`` instance.
            opening:        ``EntityHandle`` wrapping the ``IfcOpeningElement``.
            container:      ``StoreyHandle`` for spatial containment.
            door_type:      Optional ``EntityHandle`` wrapping an ``IfcDoorType``
                            entity to assign via ``IfcRelDefinesByType``.
            opening_anchor: Anchor of the parent ``PendingOpening`` (default ``"sw"``).

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
        opening_anchor: str = "sw",
    ) -> "EntityHandle":
        """
        Create an ``IfcWindow`` filling *opening* and place it in *container*.

        Args:
            pending:        A ``PendingWindow`` instance.
            opening:        ``EntityHandle`` wrapping the ``IfcOpeningElement``.
            container:      ``StoreyHandle`` for spatial containment.
            window_type:    Optional ``EntityHandle`` wrapping an ``IfcWindowType``.
            opening_anchor: Anchor of the parent ``PendingOpening`` (default ``"sw"``).

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

    def export(self, path: str, *, skip_openings: bool = True) -> None:
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
        ``.dae``      Collada (only if supported by the installed build)
        ``.ttl``      TTL/WKT geometry (only if supported by the installed build)
        ``.stp``      STEP (only if supported by the installed build)
        ``.igs``      IGES (only if supported by the installed build)
        ``.usd``      USD (only if supported by the installed build)
        ============  ========================================================

        Requires ifcopenshell == 0.9.0 (see ``ifckit.geom_backend``).

        Since 0.3.1, ``IfcOpeningElement`` voids are skipped by default —
        void boxes no longer render as solid in viewer files. Pass
        ``skip_openings=False`` for the old behavior.

        Args:
            path: Destination file path including extension.
            skip_openings: Skip ``IfcOpeningElement`` shapes (default True).

        Raises:
            ValueError:  If the extension is not recognised.
            ImportError: If the requested serializer is not available in the
                         current ifcopenshell build, or ifcopenshell < 0.9.0
                         is installed.

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

        from ifckit import geom_backend

        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self._file.write(tmp_path)
            geom_backend.serialize_to_file(
                tmp_path, path, geom_backend.make_settings(), skip_openings=skip_openings
            )
        finally:
            os.unlink(tmp_path)

    def iter_mesh_dicts(
        self,
        tessellation: Optional[dict] = None,
        *,
        skip_openings: bool = True,
        y_up: bool = True,
        include_guids: Optional[Collection[str]] = None,
        preset: str = "final",
    ) -> Iterator[dict]:
        """Stream viewer mesh dicts for every product, without temp files.

        Tessellates the in-memory model and yields one ``triangles`` dict per
        product (same format as ``Path``/``Surface.to_mesh_dict()``), each
        carrying the element ``guid`` so callers can diff and selectively
        update meshes instead of re-tessellating everything.

        Diff-contract: with the same settings, ``include_guids=[...]``
        yields dicts identical to what a full pass yields for those GUIDs
        (same order, same positions/indices) — preview callers can splice
        them into the previous full result by ``guid``.

        Args:
            tessellation: Optional ``{"linear_deflection": ..., ...}`` overrides.
            skip_openings: Skip ``IfcOpeningElement`` shapes (default True).
            y_up: Convert Z-up to Y-up ``(x, z, -y)`` (default True).
            include_guids: Only yield these GUIDs (selective re-tessellation).
            preset: Tessellation preset, ``"final"`` (default) or
                ``"interactive"`` (coarse preview) — see
                ``geom_backend.PRESETS``. Explicit *tessellation* keys win.
        """
        from ifckit import geom_backend

        settings = geom_backend.make_settings(tessellation, preset=preset)
        shapes = geom_backend.iter_shapes(
            self._file,
            settings,
            skip_openings=skip_openings,
            include_guids=include_guids,
        )
        yield from geom_backend.shapes_to_mesh_dicts(shapes, y_up=y_up)

    def to_mesh_dicts(
        self,
        tessellation: Optional[dict] = None,
        *,
        skip_openings: bool = True,
        y_up: bool = True,
        include_guids: Optional[Collection[str]] = None,
        preset: str = "final",
    ) -> list:
        """Return all viewer mesh dicts as a list (see :meth:`iter_mesh_dicts`)."""
        return list(
            self.iter_mesh_dicts(
                tessellation,
                skip_openings=skip_openings,
                y_up=y_up,
                include_guids=include_guids,
                preset=preset,
            )
        )

    def iter_chunks(
        self,
        tessellation: Optional[dict] = None,
        *,
        skip_openings: bool = True,
        y_up: bool = True,
        include_guids: Optional[Collection[str]] = None,
        preset: str = "final",
    ) -> Iterator[dict]:
        """Stream compact binary mesh chunks (see ``geom_backend.shapes_to_chunks``).

        Same tessellation as :meth:`iter_mesh_dicts` (same ``guid``\\ s, same
        shapes), but as float32/uint32 bytes with a translation-invariant
        ``profile_key`` per product, so viewers can instance and diff.

        Args:
            tessellation: Optional ``{"linear_deflection": ..., ...}`` overrides.
            skip_openings: Skip ``IfcOpeningElement`` shapes (default True).
            y_up: Convert Z-up to Y-up ``(x, z, -y)`` (default True).
            include_guids: Only yield these GUIDs (selective re-tessellation).
            preset: Tessellation preset, ``"final"`` (default) or
                ``"interactive"`` (coarse preview).
        """
        from ifckit import geom_backend

        settings = geom_backend.make_settings(tessellation, preset=preset)
        shapes = geom_backend.iter_shapes(
            self._file,
            settings,
            skip_openings=skip_openings,
            include_guids=include_guids,
        )
        yield from geom_backend.shapes_to_chunks(shapes, y_up=y_up)

    def to_chunks(
        self,
        tessellation: Optional[dict] = None,
        *,
        skip_openings: bool = True,
        y_up: bool = True,
        include_guids: Optional[Collection[str]] = None,
        preset: str = "final",
    ) -> list:
        """Return all binary mesh chunks as a list (see :meth:`iter_chunks`)."""
        return list(
            self.iter_chunks(
                tessellation,
                skip_openings=skip_openings,
                y_up=y_up,
                include_guids=include_guids,
                preset=preset,
            )
        )

    # ------------------------------------------------------------------
    # Incremental patch API (PLAN-interactive-preview, I-1)
    # ------------------------------------------------------------------

    def apply_delta(self, elements: list, *, storey=None) -> list:
        """Patch products in-place from element dicts; return changed GUIDs.

        The same ``IfcFile`` is mutated: new elements are built into it,
        changed ones are rebuilt with their ``GlobalId`` preserved, and
        unchanged ones are skipped via a signature cache. Callers can then
        re-tessellate only the returned GUIDs (see :meth:`iter_mesh_dicts`
        with ``include_guids``).

        Each element dict carries:

        - ``id``: stable caller-side key (preferred). Without ``global_id``
          the GUID stays stable as long as ``id`` is stable (derived via
          ``geom_backend.guid_for_id``). Either ``id`` or ``global_id``
          is required.
        - ``global_id``: explicit IFC ``GlobalId``. Always wins when given
          and is adopted into the stable mapping.
        - ``element_type`` (or ``type``): registry key, e.g. ``basic_wall``.
        - ``host_id``: stable ``id`` of the host element. Only supported
          for ``PendingWindow``/``PendingDoor`` with ``component_graph``
          (Model B); the opening + fill are regenerated from the preset.
        - remaining keys (or a nested ``data`` dict): the ``from_dict``
          body of the pending element (same convention as ``json_build``).

        Replacing a host also removes its openings + fills — resend them
        in the same delta to rebuild them under stable GUIDs.

        Args:
            elements: Element dicts (full state per tick; order hosts
                      before their fills).
            storey:   Optional ``StoreyHandle`` (or ``IfcBuildingStorey``
                      entity) receiving newly created storey-placed
                      elements. Defaults to the first storey in the file.

        Returns:
            Changed ``GlobalId`` strings, in input order. Unchanged
            elements are absent.
        """
        from ifckit.elements.registry import ElementRegistry

        changed: list = []
        default_storey = None
        for elem in elements:
            if not isinstance(elem, dict):
                raise TypeError(
                    f"apply_delta: each element must be a dict, got {type(elem).__name__}"
                )
            sid = elem.get("id")
            given = elem.get("global_id")
            data = elem.get("data")
            if sid is None and isinstance(data, dict):
                sid = data.get("id")
            if sid is None and not given:
                raise ValueError("apply_delta: each element needs 'id' or 'global_id'.")
            if given is not None and not (isinstance(given, str) and len(given) == 22):
                raise ValueError(
                    f"apply_delta: 'global_id' must be a 22-char IFC GlobalId, got {given!r}."
                )
            key = str(sid) if sid is not None else f"@guid:{given}"

            sig = _delta_signature(elem)
            mapped_guid = self._delta_guids.get(key)
            if self._delta_sigs.get(key) == sig and (not given or given == mapped_guid):
                continue

            element_type = elem.get("element_type") or elem.get("type")
            if isinstance(data, dict):
                body = dict(data)
                element_type = element_type or body.get("element_type") or body.get("type")
            else:
                body = {k: v for k, v in elem.items() if k not in ("id", "host_id", "global_id")}
            if not element_type:
                raise ValueError(f"apply_delta: element {key!r} misses 'element_type'/'type'.")
            try:
                cls = ElementRegistry.get(element_type)
            except KeyError:
                raise ValueError(
                    f"apply_delta: unknown element type {element_type!r} for {key!r}."
                ) from None
            pending = cls.from_dict(body)

            old_guid = self._delta_guids.get(key)
            old_entity = self._by_guid_safe(old_guid) if old_guid else None
            if old_entity is None:
                old_entity, old_guid = self._adopt_entity(sid, given)
            if old_entity is not None and old_guid is not None:
                owner = next((k for k, g in self._delta_guids.items() if g == old_guid), None)
                if owner is not None and owner != key:
                    raise ValueError(
                        f"apply_delta: global_id {old_guid!r} for {key!r} "
                        f"is already used by {owner!r}."
                    )
            target_guid = given or old_guid
            if target_guid is None and sid is not None:
                from ifckit.geom_backend import guid_for_id

                target_guid = guid_for_id(str(sid))
            if old_entity is None and target_guid is not None:
                occupant = self._by_guid_safe(target_guid)
                if occupant is not None:
                    old_entity, old_guid = occupant, target_guid

            host_id = elem.get("host_id")
            if host_id is None:
                host_id = self._delta_hosts.get(key)
            if host_id is not None:
                host_handle = self._delta_handles.get(str(host_id))
                if host_handle is None:
                    raise ValueError(
                        f"apply_delta: host_id {host_id!r} for {key!r} not found — "
                        "send the host in the same (or an earlier) delta."
                    )
                from ifckit.elements.opening import PendingDoor, PendingWindow

                if not isinstance(pending, (PendingWindow, PendingDoor)) or not getattr(
                    pending, "component_graph", None
                ):
                    raise ValueError(
                        f"apply_delta: host_id for {key!r} needs PendingWindow/"
                        "PendingDoor with component_graph (Model B)."
                    )
                if old_entity is not None:
                    self._remove_fill(old_entity)
                new_handle = host_handle.add(pending)
            else:
                if old_entity is not None:
                    storey_entity = self._container_of(old_entity)
                    self._remove_product(old_entity)
                elif default_storey is None:
                    default_storey = self._resolve_delta_storey(storey)
                    storey_entity = default_storey
                else:
                    storey_entity = default_storey
                new_handle = self.add(pending, StoreyHandle(storey_entity, self))

            if new_handle.entity.GlobalId != target_guid:
                occupant = self._by_guid_safe(target_guid)
                if occupant is not None:
                    raise ValueError(
                        f"apply_delta: global_id {target_guid!r} for {key!r} "
                        "is already used by another entity."
                    )
                new_handle.entity.GlobalId = target_guid
            self._delta_guids[key] = target_guid
            self._delta_sigs[key] = sig
            self._delta_hosts[key] = host_id
            self._delta_handles[key] = new_handle
            changed.append(target_guid)
        return changed

    def _by_guid_safe(self, guid) -> Optional["ifcopenshell.entity_instance"]:
        """Look up an entity by GlobalId, returning None on miss."""
        if not guid:
            return None
        try:
            return self._file.by_guid(guid)
        except RuntimeError:
            return None

    def _adopt_entity(self, sid, given):
        """Adopt an entity built outside apply_delta (same GUID, no map yet)."""
        if isinstance(given, str) and given:
            found = self._by_guid_safe(given)
            if found is not None:
                return found, given
        if sid is not None:
            from ifckit.geom_backend import guid_for_id

            found = self._by_guid_safe(guid_for_id(str(sid)))
            if found is not None:
                return found, found.GlobalId
        return None, None

    def _resolve_delta_storey(self, storey):
        """Resolve the receiving storey for newly created delta elements."""
        if storey is None:
            found = self._file.by_type("IfcBuildingStorey")
            if not found:
                raise ValueError(
                    "apply_delta: new element but no IfcBuildingStorey in the file — "
                    "create the spatial hierarchy first or pass storey=."
                )
            return found[0]
        if isinstance(storey, StoreyHandle):
            return storey.entity
        return storey

    def _container_of(self, entity):
        """Return the IfcBuildingStorey containing *entity* (delta rebuilds)."""
        try:
            return self._find_containing_storey(entity)
        except ValueError:
            raise ValueError(
                "apply_delta: replacing non-storey-contained products "
                f"({entity.is_a()}) is not supported."
            ) from None

    def _try_remove(self, entity) -> None:
        """Remove *entity*, tolerating prior removal."""
        try:
            self._file.remove(entity)
        except RuntimeError:
            pass

    def _strip_product(self, entity) -> None:
        """Detach representation, placement and containment of *entity*."""
        if getattr(entity, "Representation", None):
            for rep in list(entity.Representation.Representations or []):
                for item in list(rep.Items or []):
                    self._try_remove(item)
                self._try_remove(rep)
            self._try_remove(entity.Representation)
            entity.Representation = None
        if getattr(entity, "ObjectPlacement", None):
            placement = entity.ObjectPlacement
            entity.ObjectPlacement = None
            self._try_remove(placement)
        for rel in list(self._file.by_type("IfcRelContainedInSpatialStructure")):
            related = list(rel.RelatedElements or [])
            if entity in related:
                related.remove(entity)
                if related:
                    rel.RelatedElements = related
                else:
                    self._try_remove(rel)

    def _invalidate_dependents(self, guid) -> None:
        """Drop signature/handle cache for the delta key mapped to *guid*."""
        for key, mapped in list(self._delta_guids.items()):
            if mapped == guid:
                self._delta_sigs.pop(key, None)
                self._delta_handles.pop(key, None)

    def _remove_opening_tree(self, opening) -> None:
        """Remove an opening plus its fills, rels and cached delta keys."""
        for fills in list(getattr(opening, "HasFillings", None) or []):
            fill = fills.RelatedBuildingElement
            fill_guid = fill.GlobalId
            self._strip_product(fill)
            self._try_remove(fills)
            self._try_remove(fill)
            self._invalidate_dependents(fill_guid)
        self._strip_product(opening)
        self._try_remove(opening)

    def _remove_product(self, entity) -> None:
        """Remove a storey-placed product with its openings/fills (cascade)."""
        for voids in list(getattr(entity, "HasOpenings", None) or []):
            self._remove_opening_tree(voids.RelatedOpeningElement)
            self._try_remove(voids)
        self._strip_product(entity)
        self._try_remove(entity)

    def _remove_fill(self, entity) -> None:
        """Remove a fill plus the opening it fills (regenerated on rebuild)."""
        for fills in list(getattr(entity, "FillsVoids", None) or []):
            opening = fills.RelatingOpeningElement
            for voids in list(getattr(opening, "VoidsElements", None) or []):
                self._try_remove(voids)
            self._remove_opening_tree(opening)
            self._try_remove(fills)
        self._strip_product(entity)
        self._try_remove(entity)

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
                f"IfcModel.{method}() requires schema {required.to_ifcopenshell()}, "
                f"but model uses {self.schema.to_ifcopenshell()}"
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
        for rel in getattr(container, "ContainsElements", None) or []:
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
