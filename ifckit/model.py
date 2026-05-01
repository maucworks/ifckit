"""
ifckit.model
============

IfcModel: builds and manages an IFC spatial hierarchy using ifcopenshell.

Supports IFC2X3 (legacy buildings), IFC4 (buildings) and IFC4X3 (bridges / infrastructure).
"""

from __future__ import annotations

import warnings as _warnings
from typing import Optional, Union

import ifcopenshell
import ifcopenshell.api

from ifckit.schema import IfcSchema, LengthUnit, get_schema_name
from ifckit.handles import (
    SiteHandle,
    BuildingHandle,
    StoreyHandle,
    BridgeHandle,
    BridgePartHandle,
    AlignmentHandle,
    EntityHandle,
)

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

        schema_str = get_schema_name(schema)
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

    # ------------------------------------------------------------------
    # High-level element API
    # ------------------------------------------------------------------

    def add(
        self,
        pending: "PendingElement",
        container: "Union[StoreyHandle, BridgePartHandle]",
    ) -> "EntityHandle":
        """
        Validate and build a pending element, placing it in *container*.

        Args:
            pending:   Any ``PendingElement`` subclass (PendingBeam, PendingWall, …).
            container: The spatial container — a ``StoreyHandle`` (IFC4 building) or
                       a ``BridgePartHandle`` (IFC4X3 bridge).

        Returns:
            ``EntityHandle`` wrapping the created IFC entity.

        Raises:
            TypeError:    If *container* is not a StoreyHandle or BridgePartHandle.
            LookupError:  If no builder is registered for the element type.
            ValueError:   If validation fails (message lists all errors).
        """
        from ifckit.validator import validate

        if not isinstance(container, (StoreyHandle, BridgePartHandle)):
            raise TypeError(
                f"model.add() expects a StoreyHandle or BridgePartHandle, "
                f"got {type(container).__name__}"
            )

        result = validate(pending)
        for w in result.warnings:
            _warnings.warn(w, stacklevel=2)
        if not result.ok:
            raise ValueError(
                f"Validation failed for {type(pending).__name__} "
                f"'{pending.name}':\n" + "\n".join(f"  - {e}" for e in result.errors)
            )

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

    def preview_rhino(self, mesh_quality: str = "default", clear: bool = True) -> int:
        """Import the model into the active Rhino document as meshes.

        Requires Rhino 8+ with ifcopenshell installed. Intended for use
        in Grasshopper to preview the IFC model without saving to disk.

        Args:
            mesh_quality: Tessellation quality preset
                          (superfine/fine/default/coarse/supercoarse).
            clear: If True, clear existing IFC meshes before import.

        Returns:
            Number of elements imported.
        """
        from ifckit.rhino_import import IfcMeshImporter

        importer = IfcMeshImporter(
            clear_on_import=clear,
            mesh_quality=mesh_quality,
        )
        return importer.import_model(self)