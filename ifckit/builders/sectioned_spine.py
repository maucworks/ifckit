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
from typing import Dict, Optional

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
from ifckit.geometry import Path, Plane, upvector_frames
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
    entity_type = "sectioned_spine"  # BuilderRegistry key
    ifc_class = "IfcBuildingElementProxy"  # actual IFC class created

    # ------------------------------------------------------------------
    # Public low-level API: face-set only (no product, no shape rep)
    # ------------------------------------------------------------------

    def build_face_set(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
    ) -> ifcopenshell.entity_instance:
        """Return the raw ``IfcTriangulatedFaceSet`` — geometry only.

        Unlike ``build()`` or ``build_shape_rep()``, this creates neither a
        product entity nor an ``IfcShapeRepresentation``.  Use it when the
        caller manages the representation themselves, e.g. inside a component
        graph that assembles multiple solids into one window/door.
        """
        spine_curve = directrix_from_path(ifc_file, pending.spine)
        profile_defs = [p.to_ifc(ifc_file) for p in pending.profiles]
        pos_entities = [
            axis2placement3d(ifc_file, pl.origin, pl.z_axis, pl.x_axis) for pl in pending.positions
        ]
        return _sectioned_spine(
            ifc_file,
            spine_curve,
            profile_defs,
            pos_entities,
            profile_segments=getattr(pending, "profile_segments", 32),
            closed=getattr(pending, "closed", False),
        )

    # ------------------------------------------------------------------
    # Public low-level API: shape-rep only
    # ------------------------------------------------------------------

    def build_shape_rep(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        """Return an ``IfcShapeRepresentation`` without creating a product.

        Useful when the caller manages the product entity themselves and only
        needs the tessellated geometry representation.
        """
        face_set = self.build_face_set(ifc_file, pending)
        return shape_representation(
            ifc_file,
            context,
            face_set,
            rep_type="Tessellation",
        )

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
            write_psets(ifc_file, element, pending)

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
            profile_segments=getattr(pending, "profile_segments", 32),
            closed=getattr(pending, "closed", False),
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
    def _make_pending(
        spine: Path,
        profile: Profile,
        starter_plane: Plane,
        angle_step_deg: float = 5.0,
        profile_segments: int = 32,
        name: str = "",
        profile_overrides: "Optional[Dict[int, Profile]]" = None,
    ) -> PendingSectionedSpine:
        """Extract points, compute frames, build mitered profiles.

        When *profile_overrides* is given (dict mapping position index
        to a Profile), those positions are built with the override
        wrapped in the same miter scale as the base profile.

        Returns a ``PendingSectionedSpine`` ready to pass to
        ``build_face_set()``, ``build_shape_rep()``, or ``build()``.
        """
        # 1. Extract control/sample points from path (Arc-aware)
        from ifckit.geometry import Arc as _Arc

        has_arc = any(isinstance(s, _Arc) for s in spine._segments) if spine._segments else False
        if has_arc:
            pts = spine.sample(angle_step_deg).points
        else:
            segs = spine._segments
            pts = [seg.start for seg in segs]
            last = segs[-1].end
            if not (pts and pts[0].equals(last)):
                pts.append(last)

        # 2. Detect closed loop
        is_closed = getattr(spine, "is_closed", False)

        # 3. World-up direction from starter plane
        world_up = starter_plane.y_axis

        # 4. Compute frames with miter scales
        field = upvector_frames(pts, world_up, closed=is_closed)

        # 5. Extract vertex-mitered frames (midpoints are helpers)
        if is_closed:
            n_orig = len(pts)
            mit_indices = [4 * i + 2 for i in range(n_orig)]
            vtx_frames = [field.frames[i] for i in mit_indices]
            vtx_scales = [field.scales[i] for i in mit_indices]
        else:
            vtx_frames = field.frames
            vtx_scales = field.scales

        # 6. Build miter-scaled profile list
        overrides = profile_overrides or {}
        profiles: list[Profile] = []
        for i, (_s, axis) in enumerate(vtx_scales):
            scale = _s
            p = overrides.get(i, profile)
            if scale == 1.0:
                profiles.append(p)
            elif axis == "x":
                profiles.append(DerivedProfile(p, scale_y=scale))
            else:
                profiles.append(DerivedProfile(p, scale_x=scale))

        return PendingSectionedSpine(
            spine=spine,
            profiles=profiles,
            positions=vtx_frames,
            name=name,
            profile_segments=profile_segments,
            closed=is_closed,
            profile_overrides=overrides,
        )

    def tessellate_spine(
        self,
        ifc_file: ifcopenshell.file,
        spine: Path,
        profile: Profile,
        starter_plane: Plane,
        angle_step_deg: float = 5.0,
        profile_segments: int = 32,
        name: str = "",
        profile_overrides: "Optional[Dict[int, Profile]]" = None,
    ) -> ifcopenshell.entity_instance:
        """One-shot: return only the ``IfcTriangulatedFaceSet``.

        Like ``build_from_spine()`` but skips product creation —
        returns the raw tessellated mesh.  Ideal for component graphs
        that embed the geometry into a larger product (e.g. window lining).
        """
        pending = self._make_pending(
            spine,
            profile,
            starter_plane,
            angle_step_deg=angle_step_deg,
            profile_segments=profile_segments,
            name=name,
            profile_overrides=profile_overrides,
        )
        return self.build_face_set(ifc_file, pending)

    def build_from_spine(
        self,
        ifc_file: ifcopenshell.file,
        spine: Path,
        profile: Profile,
        starter_plane: Plane,
        storey: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
        name: str = "",
        angle_step_deg: float = 5.0,
        profile_segments: int = 32,
        profile_overrides: "Optional[Dict[int, Profile]]" = None,
    ) -> ifcopenshell.entity_instance:
        """Build a sectioned spine from minimal inputs.

        Automates frame computation (world-up projection), miter scaling
        (via ``DerivedProfile``), and product creation.

        The starter plane's ``.y_axis`` is used as the \"world-up\"
        direction — profile Y stays as close to this as the path allows.

        Arc segments are supported: pass a ``Path`` built with
        ``path.add_arc(center, normal, start, angle)`` and the arc is
        discretised at ``angle_step_deg`` resolution before frame
        computation.

        Args:
            ifc_file:       Open IFC file.
            spine:          Spine path (polyline or mixed Line+Arc).
            profile:        Base cross-section profile (single instance,
                            automatically cloned and miter-scaled).
            starter_plane:  Initial frame at the path start.  Its ``.y_axis``
                            is the world-up direction for the cross-section.
            storey:         Spatial container (``IfcBuildingStorey``).
            context:        Geometry context.
            name:           Optional element name.
            angle_step_deg: Arc discretisation resolution in degrees
                            (default 5°; smaller = finer mesh).

        Returns:
            ``IfcBuildingElementProxy`` with tessellated sectioned-spine
            geometry, object placement, and spatial containment.
        """
        pending = self._make_pending(
            spine,
            profile,
            starter_plane,
            angle_step_deg=angle_step_deg,
            profile_segments=profile_segments,
            name=name,
            profile_overrides=profile_overrides,
        )
        return self.build(ifc_file, pending, storey, context)
