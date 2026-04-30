"""
ifckit.builders.beam_factory
=============================

Orchestrator that classifies beam path type and routes to the correct builder.

Path classification:
- Single Line → IfcExtrudedAreaSolid (ExtrudedElementBuilder)
- Single Arc → IfcRevolvedAreaSolid (RevolvedBeamBuilder)
- Multi-segment → NotImplementedError (future: consecutive extrusions)
- Non-planar → NotImplementedError (future: tessellation approach)
"""

from __future__ import annotations

import ifcopenshell

from ifckit.builders._geom import local_placement, product_definition_shape
from ifckit.builders.extruded import ExtrudedElementBuilder
from ifckit.builders.revolved_beam import RevolvedBeamBuilder
from ifckit.elements.base import PendingElement
from ifckit.elements.structural import PendingBeam, PendingRevolvedBeam
from ifckit.geometry import Arc, Line, Path


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


__all__ = ["PathType", "classify_path", "build_beam"]