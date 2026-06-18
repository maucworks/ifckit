"""
ifckit.builders.beam_factory
=============================

Orchestrator that classifies beam path type and routes to the correct builder.

Path classification:
- Single Line → IfcExtrudedAreaSolid (ExtrudedElementBuilder)
- Single Arc → IfcRevolvedAreaSolid (RevolvedBeamBuilder)
- Multi-segment → NotImplementedError (future: consecutive extrusions)
- Non-planar → NotImplementedError (future: tessellation approach)

beam_from_path
--------------
Splits a planar Path into a list of PendingBeam / PendingRevolvedBeam, one per
segment, with a consistent cross-section orientation across all segments.

The key insight for orientation stability: for a 2D path the plane normal is
constant and independent of individual segment directions.  Using

    horiz = vert × plane_normal

instead of the standard

    horiz = vert × t

avoids the mirror-flip that occurs when a line segment happens to run in the
opposite direction.
"""

from __future__ import annotations

from typing import List, Optional, Union

import ifcopenshell

from ifckit.builders.extruded import ExtrudedElementBuilder
from ifckit.builders.revolved_beam import RevolvedBeamBuilder
from ifckit.elements.base import PendingElement
from ifckit.elements.structural import PendingBeam, PendingRevolvedBeam
from ifckit.geometry import Arc, Line, Path, Plane, Vec
from ifckit.profiles.base import Profile


class PathType:
    SINGLE_LINE = "single_line"
    SINGLE_ARC = "single_arc"
    MULTI_SEGMENT = "multi_segment"
    NON_PLANAR = "non_planar"


def classify_path(path: Line | Arc | Path) -> str:
    """
    Classify a beam path to determine which builder to use.

    Returns:
        PathType constant string
    """
    if isinstance(path, Line):
        return PathType.SINGLE_LINE
    if isinstance(path, Arc):
        return PathType.SINGLE_ARC
    if isinstance(path, Path):
        segs = path.segments
        if len(segs) == 0:
            raise ValueError("Empty path has no segments")
        if len(segs) == 1:
            return classify_path(segs[0])
        # Multi-segment: check if all on same plane
        if path.is_planar:
            return PathType.MULTI_SEGMENT
        return PathType.NON_PLANAR
    raise TypeError(f"Unknown path type: {type(path).__name__}")


def beam_from_path(
    path: Path,
    profile: Profile,
    up: Optional[Vec] = None,
    plane: Optional[Plane] = None,
    name: str = "",
) -> List[Union[PendingBeam, PendingRevolvedBeam]]:
    """Split a planar Path into one PendingBeam / PendingRevolvedBeam per segment.

    Profile orientation is consistent across all segments regardless of
    individual segment direction.  For each segment the cross-section frame is:

        vert  = up − t*(up·t)          profile Y — tracks the up direction
        horiz = vert × plane_normal    profile X — stable: uses path normal,
                                                   NOT segment tangent t

    Using ``plane_normal`` instead of ``t`` for the cross product means that
    reversing a segment's direction (start ↔ end) does not mirror the profile.

    For Arc segments a construction plane is derived so that the revolved beam's
    profile Y aligns with ``up``.

    Args:
        path:    Planar Path whose segments are Line and/or Arc objects.
        profile: Cross-section profile applied to every segment.
        up:      World-space guide-up vector (defines profile Y direction).
                 Defaults to ``ref_plane.y_axis`` — i.e. the in-plane
                 "vertical" direction of the reference plane.
        plane:   Explicit reference plane supplying the path normal and default
                 up direction.  Use this instead of ``path.make_planar()`` when
                 the path was produced by intersecting with a known plane — this
                 avoids modifying the path geometry.  Defaults to ``path.plane``.
        name:    Element name applied to every generated pending element.

    Returns:
        List of PendingBeam (for Line segments) and PendingRevolvedBeam (for
        Arc segments), in path order.

    Raises:
        ValueError: If the path has no segments or has no computable plane.
    """
    segments = path.segments
    if not segments:
        raise ValueError("beam_from_path: path has no segments")

    # Reference plane: explicit argument wins over path.plane.
    ref_plane = plane if plane is not None else path.plane

    # The path plane normal is stable — it is the same regardless of which
    # direction individual segments were assembled.
    plane_normal = ref_plane.z_axis.normalized()
    up_n = (up if up is not None else ref_plane.y_axis).normalized()

    result: List[Union[PendingBeam, PendingRevolvedBeam]] = []

    # Determine whether up has a meaningful component inside the path plane.
    # When up ∥ plane_normal (e.g. up is the plane's own normal) the in-plane
    # component of up is zero and we cannot use it to define vert/horiz.  In
    # that case we fall back to the plane's own fixed axes.
    up_in_plane = up_n - plane_normal * (up_n @ plane_normal)
    up_in_plane_is_valid = up_in_plane.length() > 1e-10

    if up_in_plane_is_valid:
        # Normal case: up has a component in the path plane.
        # vert_ref: the in-plane up direction (will become profile Y).
        # horiz_ref: perpendicular to vert_ref in the path plane — stable
        #            because it does not depend on any segment tangent.
        vert_ref = up_in_plane.normalized()
        horiz_ref = (vert_ref**plane_normal).normalized()
    else:
        # up ∥ plane_normal: use the plane's own fixed axes.
        # plane.y_axis becomes the profile Y (vert), plane.x_axis the profile X.
        vert_ref = path.plane.y_axis
        horiz_ref = path.plane.x_axis

    for seg in segments:
        if isinstance(seg, Line):
            t = seg.direction.normalized()
            vert = vert_ref - t * (vert_ref @ t)
            if vert.length() < 1e-10:
                # vert_ref ∥ t: use horiz_ref instead (orthogonal in plane)
                vert = horiz_ref - t * (horiz_ref @ t)
            vert = vert.normalized()
            # Profile X: orthogonalise horiz_ref against vert — t-independent.
            horiz = horiz_ref - vert * (horiz_ref @ vert)
            if horiz.length() < 1e-10:
                horiz = vert**t
            horiz = horiz.normalized()
            # Ensure perfect orthogonality after normalization (floating point safety).
            horiz = horiz - vert * (vert @ horiz)
            horiz = horiz.normalized()
            seg_plane = Plane(seg.start, horiz, vert)
            result.append(
                PendingBeam(axis=seg, profile=profile, plane=seg_plane, name="Beam_" + name)
            )

        elif isinstance(seg, Arc):
            # Construction plane for PendingRevolvedBeam:
            #   x_axis = radial (from center toward start)
            #   y_axis = up projected ⊥ radial
            # This ensures plane.z_axis (= radial × up_perp) acts as cp_normal,
            # driving flip detection consistent with the up direction.
            radial = (seg.start - seg.center).normalized()
            up_perp = up_n - radial * (up_n @ radial)
            if up_perp.length() < 1e-10:
                up_perp = plane_normal - radial * (plane_normal @ radial)
            up_perp = up_perp.normalized()
            # Ensure perfect orthogonality after normalization (floating point safety).
            up_perp = up_perp - radial * (radial @ up_perp)
            up_perp = up_perp.normalized()
            cp_plane = Plane(seg.start, radial, up_perp)
            result.append(
                PendingRevolvedBeam(
                    arc=seg,
                    profile=profile,
                    plane=cp_plane,
                    name="Revolved_beam_" + name,
                )
            )

    return result


def build_beam(
    ifc_file: ifcopenshell.file,
    pending: PendingElement,
    container: ifcopenshell.entity_instance,
    context: ifcopenshell.entity_instance,
) -> ifcopenshell.entity_instance:
    """
    Build a beam element by classifying its path and routing to the appropriate builder.

    Args:
        ifc_file: ifcopenshell file instance
        pending: PendingBeam or PendingRevolvedBeam
        container: IfcBuildingStorey or similar spatial container
        context: Representation context

    Returns:
        IfcBeam entity instance

    Raises:
        TypeError: If pending is not a supported beam type
        NotImplementedError: For multi-segment or non-planar paths

    Future work:
        - Multi-segment paths: Use consecutive IfcExtrudedAreaSolid with placement
        - Non-planar paths: Approximate with tessellation or IfcFacetedBrep
        - Profile abstraction: Support IBeamProfile, LBeamProfile etc.
    """
    # Route based on element_type string for reload safety
    if hasattr(pending, "element_type"):
        if pending.element_type == "basic_beam":
            path = pending.axis
            path_type = classify_path(path)
            if path_type == PathType.SINGLE_LINE:
                builder = ExtrudedElementBuilder("basic_beam", "IfcBeam")
                return builder.build(ifc_file, pending, container, context)
            elif path_type == PathType.SINGLE_ARC:
                raise NotImplementedError(
                    "Arc paths require PendingRevolvedBeam. "
                    "Use ifckit.PendingRevolvedBeam for arc-based beams."
                )
            elif path_type == PathType.MULTI_SEGMENT:
                raise NotImplementedError(
                    "Multi-segment paths not yet implemented. "
                    "Future: consecutive extrusions along each segment."
                )
            elif path_type == PathType.NON_PLANAR:
                raise NotImplementedError(
                    "Non-planar paths not yet implemented. "
                    "Future: tessellation or IfcFacetedBrep fallback."
                )
        elif pending.element_type == "revolved_beam":
            builder = RevolvedBeamBuilder()
            return builder.build(ifc_file, pending, container, context)

    raise TypeError(
        f"beam_factory does not support {type(pending).__name__} "
        f"(element_type={getattr(pending, 'element_type', None)!r})"
    )


__all__ = ["PathType", "classify_path", "build_beam", "beam_from_path"]
