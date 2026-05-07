"""
ifckit.builders.sectioned_spine
===========================

SectionedSpineBuilder: builds IfcSectionedSpine by sweeping
cross-sectional profiles along a spine curve.

Usage::

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


def _guid():
    return ifcopenshell.guid.compress(uuid.uuid4().hex)


class SectionedSpineBuilder(BaseBuilder):
    """Builder that creates IfcSectionedSpine."""

    element_type = "sectioned_spine"
    ifc_class = "IfcSectionedSpine"  # Used as generic geometric entity

    def _create_geometry(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        # Validate element type
        if pending.element_type != self.element_type:
            raise TypeError(
                f"SectionedSpineBuilder expects {self.element_type!r}, got {pending.element_type!r}"
            )

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

        # 4. Create IfcSectionedSpine
        spine = _sectioned_spine(
            ifc_file,
            spine_curve,
            profile_defs,
            pos_entities,
        )

        # 5. Create shape representation with Tessellation type
        # (IfcPolygonalFaceSet uses "Tessellation" representation type)
        shape_rep = shape_representation(
            ifc_file,
            context,
            spine,
            rep_type="Tessellation",
        )

        return shape_rep

    def _create_element(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        geometry: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        # Create ObjectPlacement at origin if no container
        if container and container.ObjectPlacement:
            placement = container.ObjectPlacement
        else:
            origin = ifc_file.create_entity("IfcCartesianPoint", Coordinates=(0.0, 0.0, 0.0))
            z = ifc_file.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
            x = ifc_file.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
            axis = ifc_file.create_entity(
                "IfcAxis2Placement3D", Location=origin, Axis=z, RefDirection=x
            )
            placement = ifc_file.create_entity(
                "IfcLocalPlacement", PlacementRelTo=None, RelativePlacement=axis
            )

        element = ifc_file.create_entity(
            "IfcBuildingElementProxy",
            GlobalId=_guid(),
            Name=pending.name or "SectionedSpine",
            Representation=product_definition_shape(ifc_file, geometry),
            ObjectPlacement=placement,
        )

        # Contain in spatial structure if container provided
        if container:
            ifc_file.create_entity(
                "IfcRelContainedInSpatialStructure",
                RelatingStructure=container,
                RelatedElements=[element],
            )

        # Write properties if any
        if pending.properties:
            write_psets(ifc_file, element, pending.properties)

        return element
