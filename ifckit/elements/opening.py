"""
ifckit.elements.opening
=======================

Pending elements for openings, doors, and windows.

IFC semantic chain (non-negotiable for Bonsai compatibility)::

    IfcWall|IfcSlab|IfcRoof
        -> IfcRelVoidsElement
        -> IfcOpeningElement
            -> IfcRelFillsElement
            -> IfcDoor|IfcWindow  (0..n per opening)
                -> IfcRelDefinesByType
                -> IfcDoorType|IfcWindowType

``PendingOpening`` carries geometry as an explicit insert ``Plane``
(origin = insert point, X-axis = width direction, Z-axis = outward normal)
plus ``width`` and ``height``.  Host is resolved implicitly from the
JSON nesting (element → openings).

``PendingDoor`` / ``PendingWindow`` are occurrence-level fills nested
inside an opening.  They may reference a type via ``type_ref``.

Allowed door operation types (v1)::

    SINGLE_SWING_LEFT  SINGLE_SWING_RIGHT
    DOUBLE_SWING_LEFT  DOUBLE_SWING_RIGHT
    SLIDING_TO_LEFT    SLIDING_TO_RIGHT
    NOTDEFINED         USERDEFINED

Allowed window types (v1)::

    SINGLE_PANEL         SIDE_HUNG_RIGHT_HAND  SIDE_HUNG_LEFT_HAND
    TILT_AND_TURN_RIGHT_HAND  FIXED_CASEMENT
    NOTDEFINED           USERDEFINED
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ifckit.elements.base import PendingElement, UserProperties
from ifckit.elements.style import RenderStyle
from ifckit.geometry import Plane

# ---------------------------------------------------------------------------
# Allowed enum subsets (v1)
# ---------------------------------------------------------------------------

DOOR_OPERATION_TYPES: frozenset = frozenset(
    {
        "SINGLE_SWING_LEFT",
        "SINGLE_SWING_RIGHT",
        "DOUBLE_SWING_LEFT",
        "DOUBLE_SWING_RIGHT",
        "SLIDING_TO_LEFT",
        "SLIDING_TO_RIGHT",
        "NOTDEFINED",
        "USERDEFINED",
    }
)

WINDOW_TYPES: frozenset = frozenset(
    {
        "SINGLE_PANEL",
        "SIDE_HUNG_RIGHT_HAND",
        "SIDE_HUNG_LEFT_HAND",
        "TILT_AND_TURN_RIGHT_HAND",
        "FIXED_CASEMENT",
        "NOTDEFINED",
        "USERDEFINED",
    }
)

# Host IFC classes allowed for openings (v1).
OPENING_HOST_IFC_CLASSES: frozenset = frozenset(
    {"IfcWall", "IfcWallStandardCase", "IfcSlab", "IfcRoof"}
)


# ---------------------------------------------------------------------------
# PendingOpening
# ---------------------------------------------------------------------------


class PendingOpening(PendingElement):
    """
    An opening voided into a host element.

    Args:
        plane:        Insert plane.  Origin = insert point (bottom-centre of
                     opening).  X-axis = width direction.  Z-axis = outward
                     normal of the host face (points away from the host).
        width:       Opening width (metres, positive).
        height:      Opening height (metres, positive).
        opening_depth: Depth of the opening in metres (default: 10.0).
        name:        Element name (used as ``IfcOpeningElement.Name``).
        clips:       Optional boolean clip planes (inherits base convention).
        style:       Optional render style.
        properties:  Free-form user properties → ``EPset_IfcKit``.
    """

    element_type = "basic_opening"

    def __init__(
        self,
        plane: Plane,
        width: float,
        height: float,
        opening_depth: float | None = None,
        name: str = "",
        clips: Optional[List[Plane]] = None,
        style: Optional[RenderStyle] = None,
        properties: Optional[UserProperties] = None,
    ) -> None:
        super().__init__(name=name, clips=clips, style=style, properties=properties)
        if width <= 0:
            raise ValueError(f"PendingOpening: width must be positive, got {width!r}")
        if height <= 0:
            raise ValueError(f"PendingOpening: height must be positive, got {height!r}")
        if opening_depth is not None and opening_depth <= 0:
            raise ValueError(
                f"PendingOpening: opening_depth must be positive, got {opening_depth!r}"
            )
        self.plane = plane
        self.width = float(width)
        self.height = float(height)
        self.opening_depth = opening_depth  # None means "use default 10m in project units"

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["plane"] = self.plane.to_dict()
        d["width"] = self.width
        d["height"] = self.height
        if self.opening_depth is not None:
            d["opening_depth"] = self.opening_depth
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingOpening":
        plane_raw = cls._require(d, "plane")
        width = cls._require(d, "width")
        height = cls._require(d, "height")
        return cls(
            plane=Plane.from_dict(plane_raw),
            width=width,
            height=height,
            opening_depth=d.get("opening_depth"),  # None if not specified - builder converts 10m
            name=d.get("name", ""),
            clips=cls._clips_from_dict(d),
            style=cls._style_from_dict(d),
            properties=cls._properties_from_dict(d),
        )


# ---------------------------------------------------------------------------
# PendingDoor
# ---------------------------------------------------------------------------


class PendingDoor(PendingElement):
    """
    A door occurrence filling an opening.

    Args:
        overall_width:    Overall width of the door leaf (metres, positive).
        overall_height:   Overall height of the door leaf (metres, positive).
        operation_type:   One of ``DOOR_OPERATION_TYPES``.  Defaults to
                          ``"NOTDEFINED"``.
        type_ref:         Optional stable string id / key of the
                          ``PendingDoorType`` to assign.
        name:             Element name (``IfcDoor.Name``).
        style:            Optional render style.
        properties:       Free-form user properties.
    """

    element_type = "basic_door"

    def __init__(
        self,
        overall_width: float,
        overall_height: float,
        operation_type: str = "NOTDEFINED",
        type_ref: Optional[str] = None,
        name: str = "",
        style: Optional[RenderStyle] = None,
        properties: Optional[UserProperties] = None,
    ) -> None:
        super().__init__(name=name, style=style, properties=properties)
        if overall_width <= 0:
            raise ValueError(f"PendingDoor: overall_width must be positive, got {overall_width!r}")
        if overall_height <= 0:
            raise ValueError(
                f"PendingDoor: overall_height must be positive, got {overall_height!r}"
            )
        op = operation_type.upper()
        if op not in DOOR_OPERATION_TYPES:
            raise ValueError(
                f"PendingDoor: unknown operation_type {operation_type!r}. "
                f"Allowed: {sorted(DOOR_OPERATION_TYPES)}"
            )
        self.overall_width = float(overall_width)
        self.overall_height = float(overall_height)
        self.operation_type = op
        self.type_ref = type_ref

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["overall_width"] = self.overall_width
        d["overall_height"] = self.overall_height
        d["operation_type"] = self.operation_type
        if self.type_ref is not None:
            d["type_ref"] = self.type_ref
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingDoor":
        return cls(
            overall_width=cls._require(d, "overall_width"),
            overall_height=cls._require(d, "overall_height"),
            operation_type=d.get("operation_type", "NOTDEFINED"),
            type_ref=d.get("type_ref"),
            name=d.get("name", ""),
            style=cls._style_from_dict(d),
            properties=cls._properties_from_dict(d),
        )


# ---------------------------------------------------------------------------
# PendingWindow
# ---------------------------------------------------------------------------


class PendingWindow(PendingElement):
    """
    A window occurrence filling an opening.

    Args:
        overall_width:  Overall width (metres, positive).
        overall_height: Overall height (metres, positive).
        window_type:    One of ``WINDOW_TYPES``.  Defaults to ``"NOTDEFINED"``.
        type_ref:       Optional stable string id / key of the
                        ``PendingWindowType`` to assign.
        name:           Element name (``IfcWindow.Name``).
        style:          Optional render style.
        properties:     Free-form user properties.
    """

    element_type = "basic_window"

    def __init__(
        self,
        overall_width: float,
        overall_height: float,
        window_type: str = "NOTDEFINED",
        type_ref: Optional[str] = None,
        name: str = "",
        style: Optional[RenderStyle] = None,
        properties: Optional[UserProperties] = None,
    ) -> None:
        super().__init__(name=name, style=style, properties=properties)
        if overall_width <= 0:
            raise ValueError(
                f"PendingWindow: overall_width must be positive, got {overall_width!r}"
            )
        if overall_height <= 0:
            raise ValueError(
                f"PendingWindow: overall_height must be positive, got {overall_height!r}"
            )
        wt = window_type.upper()
        if wt not in WINDOW_TYPES:
            raise ValueError(
                f"PendingWindow: unknown window_type {window_type!r}. "
                f"Allowed: {sorted(WINDOW_TYPES)}"
            )
        self.overall_width = float(overall_width)
        self.overall_height = float(overall_height)
        self.window_type = wt
        self.type_ref = type_ref

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["overall_width"] = self.overall_width
        d["overall_height"] = self.overall_height
        d["window_type"] = self.window_type
        if self.type_ref is not None:
            d["type_ref"] = self.type_ref
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingWindow":
        return cls(
            overall_width=cls._require(d, "overall_width"),
            overall_height=cls._require(d, "overall_height"),
            window_type=d.get("window_type", "NOTDEFINED"),
            type_ref=d.get("type_ref"),
            name=d.get("name", ""),
            style=cls._style_from_dict(d),
            properties=cls._properties_from_dict(d),
        )
