"""
ifckit.elements
==============

Pending IFC element data containers.
"""

from ifckit.elements.base import ClipData, PendingElement
from ifckit.elements.bridge import (
    AlignmentSegment,
    BridgePartType,
    PendingAlignment,
    PendingBridge,
    PendingBridgePart,
)
from ifckit.elements.building import PendingSlab, PendingWall
from ifckit.elements.opening import (
    DOOR_OPERATION_TYPES,
    OPENING_HOST_IFC_CLASSES,
    WINDOW_TYPES,
    PendingDoor,
    PendingOpening,
    PendingWindow,
)
from ifckit.elements.registry import ElementRegistry
from ifckit.elements.sectioned_spine import PendingSectionedSpine
from ifckit.elements.space import PendingSpace
from ifckit.elements.structural import (
    PendingBeam,
    PendingColumn,
    PendingExtrudedElement,
    PendingRevolvedBeam,
    PendingTaperedExtrusion,
)
from ifckit.elements.style import RenderStyle
from ifckit.elements.types import PendingDoorType, PendingTypeObject, PendingWindowType
from ifckit.elements.wall_graph import PendingWallGraph

__all__ = [
    "PendingElement",
    "ClipData",
    "ElementRegistry",
    "RenderStyle",
    "PendingWall",
    "PendingSlab",
    "PendingSpace",
    "PendingWallGraph",
    "PendingOpening",
    "PendingDoor",
    "PendingWindow",
    "DOOR_OPERATION_TYPES",
    "WINDOW_TYPES",
    "OPENING_HOST_IFC_CLASSES",
    "PendingTypeObject",
    "PendingDoorType",
    "PendingWindowType",
    "PendingBeam",
    "PendingColumn",
    "PendingExtrudedElement",
    "PendingRevolvedBeam",
    "PendingTaperedExtrusion",
    "PendingSectionedSpine",
    "AlignmentSegment",
    "BridgePartType",
    "PendingAlignment",
    "PendingBridge",
    "PendingBridgePart",
]
