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
    """Enumeration of path types for beam definitions."""

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


def _segment_intersects_clip(
    seg: Line | Arc,
    clip: Plane,
) -> bool:
    """True if *clip* might remove material from *seg*.

    Returns False only when both endpoints (and arc midpoint for arcs) are
    strictly on the keep side (negative signed distance along clip.z_axis).
    Checks the centerline only — does not account for profile extent.

    A point with signed distance exactly zero (on the clip plane) is treated
    as on the remove side — conservative: may create an unnecessary boolean
    but never misses a required clip.
    """

    def _sd(pt: Vec) -> float:
        return (pt - clip.origin) @ clip.z_axis

    if _sd(seg.start) >= 0 or _sd(seg.end) >= 0:
        return True
    if isinstance(seg, Arc) and _sd(seg.midpoint) >= 0:
        return True
    return False


def _segment_completely_removed(seg: Line | Arc, clip: Plane) -> bool:
    """True when ALL tested points on *seg* are on the remove side (sd >= 0).

    For arcs the midpoint is also checked — catches arcs that curve entirely
    to the remove side even when both endpoints happen to be keep-side.
    """

    def _sd(pt: Vec) -> float:
        return (pt - clip.origin) @ clip.z_axis

    if _sd(seg.start) < 0 or _sd(seg.end) < 0:
        return False
    if isinstance(seg, Arc) and _sd(seg.midpoint) < 0:
        return False
    return True


def beam_from_path(
    path: Path,
    profile: Profile,
    up: Optional[Vec] = None,
    plane: Optional[Plane] = None,
    name: str = "",
    clips: Optional[List[Plane]] = None,
    start_clip: Optional[Plane] = None,
    end_clip: Optional[Plane] = None,
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
        col_segments = beam_from_path(
            crv,
            profile=lbeam(anchor="sw", rotation=math.radians(180), offset_x=gap / 2),
            name="LBEAM_column",
            clips=clips,
        )
        res.extend(col_segments)


    Clip planes are forwarded only to segments they intersect (checked via
    signed distance).  A clip whose keep side contains the entire segment is
    skipped — no unnecessary IfcBooleanClippingResult is created.

    Segments whose every point lies on the remove side of **any** clip are
    omitted entirely — they would produce a zero-volume solid.

    A point with signed distance exactly zero (on the clip plane) is treated
    as on the remove side (conservative).  Multi-clip interaction (e.g. two
    clips together carving out a middle section) is beyond the scope of this
    function — each clip is evaluated independently.

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
        clips:   Optional list of ``Plane`` objects for boolean clipping.
                 Only forwarded to segments the plane actually intersects.
        start_clip: Backward-compat — prepended to ``clips``.
        end_clip:   Backward-compat — appended to ``clips``.

    Returns:
        List of PendingBeam (for Line segments) and PendingRevolvedBeam (for
        Arc segments), in path order.

    Raises:
        ValueError: If the path has no segments or has no computable plane.
    """
    # Merge clips
    merged: List[Plane] = list(clips) if clips else []
    if start_clip is not None:
        merged.insert(0, start_clip)
    if end_clip is not None:
        merged.append(end_clip)

    result: List[Union[PendingBeam, PendingRevolvedBeam]] = []
    path = path.continued(tol=0.1, snap=True)
    t = path.tangent_at(0).normalized()

    dot_x = t @ path.plane.x_axis
    dot_y = t @ path.plane.y_axis
    if abs(dot_x) > abs(dot_y):
        dominant_axis = dot_x
    else:
        dominant_axis = dot_y
    if dominant_axis < 0:
        path.reverse()

    segments = path.segments
    if not segments:
        raise ValueError("beam_from_path: path has no segments")

    # Reference plane: explicit argument wins over path.plane.
    ref_plane = plane if plane is not None else path.plane

    for seg in segments:
        # Skip segments whose every point is removed by any single clip.
        if any(_segment_completely_removed(seg, c) for c in merged):
            continue

        # Filter clips — only forward those that intersect this segment.
        seg_clips = [c for c in merged if _segment_intersects_clip(seg, c)]

        if isinstance(seg, Line):
            t0 = seg.tangent_at(0).normalized()
            x_axis = ref_plane.z_axis
            y_axis = x_axis**t0
            myplane = Plane(seg.point_at(0), x_axis, y_axis)
            result.append(
                PendingBeam(
                    axis=seg,
                    profile=profile,
                    plane=myplane,
                    clips=seg_clips or None,
                    name="Beam_" + name,
                )
            )

        elif isinstance(seg, Arc):
            result.append(
                PendingRevolvedBeam(
                    arc=seg,
                    profile=profile,
                    clips=seg_clips or None,
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
