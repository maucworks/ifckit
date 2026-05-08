"""
ifckit.builders.sectioned_spine
===========================

SectionedSpineBuilder: builds IfcSectionedSpine by sweeping
cross-sectional profiles along a spine curve.

Usage via registry::

    from ifckit.elements import PendingSectionedSpine
    from ifckit.geometry import Path, Plane, Vec
    from ifckit.profiles import RectangleProfile

    spine = Path.from_pts([Vec(0,0,0), Vec(1000,0,0)])
    profiles = [RectangleProfile(50, 70), RectangleProfile(50, 70)]
    positions = [Plane(Vec(0,0,0), Vec(1,0,0), Vec(0,1,0)),
               Plane(Vec(1000,0,0), Vec(1,0,0), Vec(0,1,0))]

    pending = PendingSectionedSpine(
        spine=spine,
        profiles=profiles,
        positions=positions,
        name="my_spine"
    )

One-shot convenience API::

    builder = SectionedSpineBuilder()
    element = builder.build_from_spine(
        ifc_file,
        spine=Path.from_pts(pts),
        profile=RectangleProfile(150, 300),
        starter_plane=Plane(pts[0], Vec(0, 1, 0), Vec(0, 0, 1)),
        storey=storey,
        context=context,
        name="auto_spine",
    )

Low-level shape-rep access::

    builder = SectionedSpineBuilder()
    shape_rep = builder.build_shape_rep(ifc_file, pending, context)
"""

from __future__ import annotations

import uuid

import ifcopenshell

from ifckit.builders._geom import (
    axis2placement3d,
    directrix_from_path,
    product_definition_shape,
    shape_representation,
)
from ifckit.builders._geom import (
    sectioned_spine as _sectioned_spine,
)
from ifckit.builders.base import BaseBuilder
from ifckit.builders.psets import write_psets
from ifckit.elements.base import PendingElement
from ifckit.elements.sectioned_spine import PendingSectionedSpine
from ifckit.geometry import Path, Plane, Vec, upvector_frames
from ifckit.profiles import DerivedProfile, Profile


def _guid():
    return ifcopenshell.guid.compress(uuid.uuid4().hex)


class SectionedSpineBuilder(BaseBuilder):
    """Builder that tessellates a SectionedSpine to IfcBuildingElementProxy.

    Two usage modes:

    1. Via registry / ``build()``: returns an IfcBuildingElementProxy with
       GlobalId, ObjectPlacement, and spatial containment — ready for Bonsai.

    2. Low-level via ``build_shape_rep()``: returns only the
       IfcShapeRepresentation, useful when the caller wants to embed the
       geometry inside a larger product (e.g. a window fill).
    """

    element_type = "sectioned_spine"
    ifc_class = "IfcBuildingElementProxy"  # actual IFC class created

    # ------------------------------------------------------------------
    # Public low-level API: shape-rep only
    # ------------------------------------------------------------------

    def build_shape_rep(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        """Return an IfcShapeRepresentation without creating a product.

        Useful when the caller manages the product entity themselves and only
        needs the tessellated geometry representation.
        """
        return self._make_shape_rep(ifc_file, pending, context)

    # ------------------------------------------------------------------
    # BaseBuilder contract
    # ------------------------------------------------------------------

    def _create_geometry(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        """Create IfcBuildingElementProxy with tessellated spine geometry.

        Returns the product entity (as required by BaseBuilder.build).
        """
        if pending.element_type != self.element_type:
            raise TypeError(
                f"SectionedSpineBuilder expects {self.element_type!r}, got {pending.element_type!r}"
            )

        shape_rep = self._make_shape_rep(ifc_file, pending, context)

        # ObjectPlacement relative to container (absorbs storey elevation)
        if container and getattr(container, "ObjectPlacement", None):
            origin = ifc_file.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
            z = ifc_file.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
            x = ifc_file.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
            axis = ifc_file.create_entity(
                "IfcAxis2Placement3D", Location=origin, Axis=z, RefDirection=x
            )
            placement = ifc_file.create_entity(
                "IfcLocalPlacement",
                PlacementRelTo=container.ObjectPlacement,
                RelativePlacement=axis,
            )
        else:
            origin = ifc_file.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
            z = ifc_file.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
            x = ifc_file.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
            axis = ifc_file.create_entity(
                "IfcAxis2Placement3D", Location=origin, Axis=z, RefDirection=x
            )
            placement = ifc_file.create_entity(
                "IfcLocalPlacement",
                PlacementRelTo=None,
                RelativePlacement=axis,
            )

        element = ifc_file.create_entity(
            "IfcBuildingElementProxy",
            GlobalId=_guid(),
            Name=pending.name or "SectionedSpine",
            Representation=product_definition_shape(ifc_file, shape_rep),
            ObjectPlacement=placement,
        )

        # Contain in spatial structure
        if container:
            ifc_file.create_entity(
                "IfcRelContainedInSpatialStructure",
                GlobalId=_guid(),
                RelatingStructure=container,
                RelatedElements=[element],
            )

        # Write properties if any
        if pending.properties:
            write_psets(ifc_file, element, pending.properties)

        return element

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_shape_rep(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        """Tessellate spine to IfcTriangulatedFaceSet and wrap in IfcShapeRepresentation."""
        # 1. Convert spine to IfcCompositeCurve
        spine_curve = directrix_from_path(ifc_file, pending.spine)

        # 2. Convert each profile to IfcProfileDef
        profile_defs = [p.to_ifc(ifc_file) for p in pending.profiles]

        # 3. Convert each position to IfcAxis2Placement3D
        pos_entities = []
        for pl in pending.positions:
            pos_entity = axis2placement3d(
                ifc_file,
                pl.origin,
                pl.z_axis,
                pl.x_axis,
            )
            pos_entities.append(pos_entity)

        # 4. Tessellate → IfcTriangulatedFaceSet
        face_set = _sectioned_spine(
            ifc_file,
            spine_curve,
            profile_defs,
            pos_entities,
        )

        # 5. Wrap in IfcShapeRepresentation (Tessellation type)
        return shape_representation(
            ifc_file,
            context,
            face_set,
            rep_type="Tessellation",
        )

    # ------------------------------------------------------------------
    # One-shot convenience API
    # ------------------------------------------------------------------

    @staticmethod
    def _points_from_path(spine: Path) -> list[Vec]:
        """Extract control points from a polyline Path."""
        segs = spine._segments
        if not segs:
            raise ValueError("Spine path has no segments")
        pts = [seg.start for seg in segs]
        pts.append(segs[-1].end)
        return pts

    def build_from_spine(
        self,
        ifc_file: ifcopenshell.file,
        spine: Path,
        profile: Profile,
        starter_plane: Plane,
        storey: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
        name: str = "",
    ) -> ifcopenshell.entity_instance:
        """Build a sectioned spine from minimal inputs.

        Automates frame computation (world-up projection), miter scaling
        (via ``DerivedProfile``), and product creation.

        The starter plane's ``.y_axis`` is used as the \"world-up\"
        direction — profile Y stays as close to this as the path allows.
        No holonomic twist accumulates across orthogonal-plane corners.

        Args:
            ifc_file:      Open IFC file.
            spine:         Spine path (polyline from ``Path.from_pts()``).
            profile:       Base cross-section profile (single instance,
                           automatically cloned and miter-scaled).
            starter_plane: Initial frame at the path start.  Its ``.y_axis``
                           is the world-up direction for the cross-section.
            storey:        Spatial container (``IfcBuildingStorey``).
            context:       Geometry context (``IfcGeometricRepresentationSubContext``).
            name:          Optional element name.

        Returns:
            ``IfcBuildingElementProxy`` with tessellated sectioned-spine
            geometry, object placement, and spatial containment.
        """
        # 1. Extract control points from path
        pts = self._points_from_path(spine)

        # 2. World-up direction from starter plane
        world_up = starter_plane.y_axis

        # 3. Compute upvector frames with miter scales
        field = upvector_frames(pts, world_up)

        # 4. Build profile list with miter-scaled copies
        profiles: list[Profile] = []
        for i, (scale, axis) in enumerate(field.scales):
            if scale == 1.0:
                profiles.append(profile)
            elif axis == "x":
                # rotation around X → miter along Y → scale Y
                profiles.append(DerivedProfile(profile, scale_y=scale))
            else:
                # rotation around Y → miter along X → scale X
                profiles.append(DerivedProfile(profile, scale_x=scale))

        # 5. Create pending element and build
        pending = PendingSectionedSpine(
            spine=spine,
            profiles=profiles,
            positions=field.frames,
            name=name,
        )
        return self.build(ifc_file, pending, storey, context)
