"""
ifckit.elements
===============

Pending IFC element data containers.
"""

from ifckit.elements.base import PendingElement, ClipData
from ifckit.elements.building import PendingWall, PendingSlab
from ifckit.elements.structural import PendingBeam, PendingColumn, PendingRevolvedBeam
from ifckit.elements.swept import PendingSweptBeam
from ifckit.elements.bridge import (
    AlignmentSegment,
    BridgePartType,
    PendingAlignment,
    PendingBridge,
    PendingBridgePart,
)

__all__ = [
    "PendingElement",
    "ClipData",
    "PendingWall",
    "PendingSlab",
    "PendingBeam",
    "PendingColumn",
    "PendingRevolvedBeam",
    "PendingSweptBeam",
    "AlignmentSegment",
    "BridgePartType",
    "PendingAlignment",
    "PendingBridge",
    "PendingBridgePart",
]
