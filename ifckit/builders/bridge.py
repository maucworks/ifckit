"""
ifckit.builders.bridge
======================

Bridge builders for IFC4X3:
  AlignmentBuilder  — PendingAlignment → IfcAlignment + IfcAlignmentHorizontal
  BridgeBuilder     — (see IfcModel; used for element placement only)
  BridgePartBuilder — (see IfcModel; used for element placement only)

Note: IfcBridge and IfcBridgePart creation is handled by IfcModel itself
(since they are spatial structure elements, not products with geometry).
AlignmentBuilder handles the geometry/nesting of IfcAlignment.
"""

from __future__ import annotations

import math

import ifcopenshell
import ifcopenshell.api

from ifckit.builders._geom import pt2
from ifckit.elements.base import PendingElement
from ifckit.elements.bridge import AlignmentSegment, PendingAlignment
from ifckit.geometry import Arc, Line


def _start_direction_rad(segment: AlignmentSegment) -> float:
    """
    Return the start direction of a segment in radians, measured CCW from +X.
    For a Line: angle of its direction vector in XY plane.
    For an Arc: tangent at start in XY plane.
    """
    geom = segment.geometry
    if isinstance(geom, Line):
        d = geom.direction
        return math.atan2(d.y, d.x)
    else:
        t = geom.tangent_at_start()
        return math.atan2(t.y, t.x)


def _start_point_2d(segment: AlignmentSegment) -> tuple[float, float]:
    """Return the 2D (x, y) start point of a segment."""
    geom = segment.geometry
    return (geom.start.x, geom.start.y)


class AlignmentBuilder:
    """
    Builds an IfcAlignment with horizontal segments from a PendingAlignment.

    Creates:
      IfcAlignment
        └─ IfcAlignmentHorizontal (via IfcRelNests)
              └─ IfcAlignmentSegment  (one per AlignmentSegment)
                    DesignParameters → IfcAlignmentHorizontalSegment

    The alignment entity must already exist (created by IfcModel.add_alignment).
    This builder populates the horizontal curve geometry.
    """

    entity_type = "alignment"

    def build(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        """Build horizontal alignment geometry onto an existing IfcAlignment entity.

        .. note::
            This builder intentionally deviates from the ``IIfcBuilder`` protocol
            contract: ``container`` here is the **IfcAlignment entity** (created by
            ``IfcModel.add_alignment``), not a spatial structure container such as
            ``IfcBuildingStorey``.  The alignment workflow is:

            1. ``handle = model.add_alignment(site, name)``  — creates IfcAlignment
            2. ``builder.build(ifc_file, pending, handle.entity, ctx)``  — adds geometry

            This two-step approach is necessary because IfcAlignment is aggregated under
            IfcSite (not contained in a storey), and its geometry is populated separately
            rather than via ``model.add()``.
        """
        # Use element_type string comparison instead of isinstance() to handle
        # class identity mismatches from module reloading in Rhino/Grasshopper.
        if not hasattr(pending, 'element_type') or pending.element_type != 'alignment':
            raise TypeError(
                f"AlignmentBuilder expects PendingAlignment, got {type(pending).__name__}"
            )

        # container here is the IfcAlignment entity created by IfcModel
        alignment = container

        # Create IfcAlignmentHorizontal
        horiz = ifcopenshell.api.run(
            "root.create_entity",
            ifc_file,
            ifc_class="IfcAlignmentHorizontal",
            name=f"{pending.name}_H" if pending.name else "",
        )
        ifcopenshell.api.run(
            "nest.assign_object",
            ifc_file,
            related_objects=[horiz],
            relating_object=alignment,
        )

        # Add one IfcAlignmentSegment per AlignmentSegment
        for seg in pending.segments:
            geom = seg.geometry
            start_dir = _start_direction_rad(seg)
            start_pt = _start_point_2d(seg)

            if isinstance(geom, Line):
                design_params = ifc_file.create_entity(
                    "IfcAlignmentHorizontalSegment",
                    StartPoint=pt2(ifc_file, *start_pt),
                    StartDirection=float(start_dir),
                    StartRadiusOfCurvature=0.0,
                    EndRadiusOfCurvature=0.0,
                    SegmentLength=float(geom.length),
                    PredefinedType="LINE",
                )
            else:
                if not isinstance(geom, Arc):
                    raise TypeError(
                        f"AlignmentSegment geometry must be Line or Arc, got {type(geom).__name__}"
                    )
                # Radius (signed: positive = left turn, negative = right turn)
                # IFC convention: positive radius = left (CCW), negative = right (CW)
                radius = geom.radius if geom.angle >= 0 else -geom.radius
                seg_length = abs(geom.angle) * geom.radius
                design_params = ifc_file.create_entity(
                    "IfcAlignmentHorizontalSegment",
                    StartPoint=pt2(ifc_file, *start_pt),
                    StartDirection=float(start_dir),
                    StartRadiusOfCurvature=float(radius),
                    EndRadiusOfCurvature=float(radius),
                    SegmentLength=float(seg_length),
                    PredefinedType="CIRCULARARC",
                )

            align_seg = ifcopenshell.api.run(
                "root.create_entity",
                ifc_file,
                ifc_class="IfcAlignmentSegment",
            )
            align_seg.DesignParameters = design_params
            ifcopenshell.api.run(
                "nest.assign_object",
                ifc_file,
                related_objects=[align_seg],
                relating_object=horiz,
            )

        return alignment
