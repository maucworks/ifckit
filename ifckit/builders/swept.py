"""
ifckit.builders.swept
=====================

SweptElementBuilder: builds an IFC beam by sweeping a profile along a
Line, Arc, or mixed Path using IfcFixedReferenceSweptAreaSolid.

Cross-section frame convention
-------------------------------
The profile is drawn in the plane perpendicular to the directrix tangent.
  profile X = local horizontal  (= vert × tangent)
  profile Y = vert               (= resolved up guide projected ⊥ tangent)

The FixedReference passed to IfcFixedReferenceSweptAreaSolid is the
resolved *up* direction in world space — it steers how profile X/Y
track the tangent as the sweep progresses.

Clipping
--------
start_clip and end_clip work exactly as in ExtrudedElementBuilder: each is
a world-space Plane whose z_axis points toward material to keep.
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api

from ifckit.builders._geom import (
    _arbitrary_perp,
    axis2placement3d,
    dir3,
    directrix_from_arc,
    directrix_from_line,
    directrix_from_path,
    get_body_context,
    local_placement,
    product_definition_shape,
    profile_from_points,
    pt3,
    shape_representation,
    storey_elevation,
)
from ifckit.elements.base import PendingElement
from ifckit.elements.swept import PendingSweptBeam
from ifckit.geometry import Arc, Line, Plane, Vec


class SweptElementBuilder:
    """
    Builds a swept IFC structural element from a PendingSweptBeam.

    Args:
        entity_type: Registry key, e.g. ``"swept_beam"``.
        ifc_class:   IFC entity class name, e.g. ``"IfcBeam"``.
    """

    def __init__(self, entity_type: str, ifc_class: str) -> None:
        self.entity_type = entity_type
        self._ifc_class = ifc_class

    def build(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        if not isinstance(pending, PendingSweptBeam):
            raise TypeError(
                f"SweptElementBuilder expects PendingSweptBeam, got {type(pending).__name__}"
            )

        elev = storey_elevation(container)

        # Resolve up vector
        path = pending.path
        if pending.up is not None:
            up = pending.up.normalized()
        else:
            # Derive a sensible default from the first tangent
            if isinstance(path, Line):
                first_tangent = path.direction
            elif isinstance(path, Arc):
                first_tangent = path.tangent_at_start()
            else:
                first_tangent = path.start_tangent()
            up = Vec(0.0, 0.0, 1.0)
            if abs(first_tangent @ up) > 0.999:
                up = Vec(0.0, 1.0, 0.0)

        # Build directrix
        if isinstance(path, Line):
            directrix = directrix_from_line(ifc_file, path)
        elif isinstance(path, Arc):
            directrix = directrix_from_arc(ifc_file, path)
        else:
            directrix = directrix_from_path(ifc_file, path)

        # Profile (2-D points in cross-section XY plane)
        pts_2d = [(p.x, p.y) for p in pending.profile]
        profile = profile_from_points(ifc_file, pts_2d)

        # FixedReference — the world-space vector that profile Y tracks
        fixed_ref = dir3(ifc_file, up.x, up.y, up.z)

        solid = ifc_file.create_entity(
            "IfcFixedReferenceSweptAreaSolid",
            SweptArea=profile,
            Position=None,
            Directrix=directrix,
            StartParam=None,
            EndParam=None,
            FixedReference=fixed_ref,
        )

        # Apply clips
        geometry = solid
        for clip_plane in _iter_clips(pending):
            geometry = _apply_clip_world(ifc_file, geometry, clip_plane)

        rep_type = "SweptSolid" if geometry is solid else "Clipping"
        body_ctx = get_body_context(ifc_file)
        shape_rep = shape_representation(ifc_file, body_ctx, geometry, rep_type=rep_type)
        prod_rep = product_definition_shape(ifc_file, shape_rep)

        # ObjectPlacement: world origin (IfcFixedReferenceSweptAreaSolid uses world coords)
        world_origin = Vec(0.0, 0.0, 0.0)
        world_plane = Plane(world_origin, Vec(1, 0, 0), Vec(0, 1, 0))
        op = local_placement(ifc_file, world_plane, relative_to=container.ObjectPlacement)

        element = ifcopenshell.api.run(
            "root.create_entity",
            ifc_file,
            ifc_class=self._ifc_class,
            name=pending.name,
        )
        element.Representation = prod_rep
        element.ObjectPlacement = op

        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc_file,
            products=[element],
            relating_structure=container,
        )

        return element


# ---------------------------------------------------------------------------
# Clipping helpers
# ---------------------------------------------------------------------------


def _iter_clips(pending: PendingSweptBeam):
    if pending.start_clip is not None:
        yield pending.start_clip
    if pending.end_clip is not None:
        yield pending.end_clip


def _apply_clip_world(
    ifc_file: ifcopenshell.file,
    solid: ifcopenshell.entity_instance,
    clip_plane: Plane,
) -> ifcopenshell.entity_instance:
    """
    Subtract the half-space on the negative side of clip_plane from solid.

    For swept solids the geometry lives in world space (no OP transform),
    so the clip plane is used directly in world coordinates.
    """
    n = clip_plane.z_axis
    ref = _arbitrary_perp(n)
    half_space_pos = ifc_file.create_entity(
        "IfcAxis2Placement3D",
        Location=pt3(ifc_file, clip_plane.origin.x, clip_plane.origin.y, clip_plane.origin.z),
        Axis=dir3(ifc_file, n.x, n.y, n.z),
        RefDirection=dir3(ifc_file, ref.x, ref.y, ref.z),
    )
    base_surface = ifc_file.create_entity("IfcPlane", Position=half_space_pos)
    half_space = ifc_file.create_entity(
        "IfcHalfSpaceSolid",
        BaseSurface=base_surface,
        AgreementFlag=False,
    )
    return ifc_file.create_entity(
        "IfcBooleanClippingResult",
        Operator="DIFFERENCE",
        FirstOperand=solid,
        SecondOperand=half_space,
    )
