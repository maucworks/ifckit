"""
ifckit.elements.bridge
======================

Pending bridge and infrastructure elements for IFC4x3:
  PendingAlignment, AlignmentSegment
  PendingBridgePart, PendingBridge
"""

from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional, Union

from ifckit.elements.base import PendingElement
from ifckit.geometry import Arc, Line, Vec


# ---------------------------------------------------------------------------
# AlignmentSegment
# ---------------------------------------------------------------------------

class AlignmentSegment:
    """
    A single segment of a horizontal alignment — either a straight tangent
    (Line) or a circular arc (Arc).

    Args:
        geometry:       Line or Arc
        station_start:  Chainage / station at start (metres, optional)
    """

    def __init__(
        self,
        geometry: Union[Line, Arc],
        station_start: float = 0.0,
    ) -> None:
        self.geometry = geometry
        self.station_start = float(station_start)

    @property
    def length(self) -> float:
        if isinstance(self.geometry, Arc):
            return self.geometry.length()
        return self.geometry.length

    def to_dict(self) -> Dict[str, Any]:
        import math
        if isinstance(self.geometry, Line):
            geom_d = {
                "segment_type": "line",
                "start": self.geometry.start.to_tuple(),
                "end": self.geometry.end.to_tuple(),
            }
        else:
            geom_d = {
                "segment_type": "arc",
                "center": self.geometry.center.to_tuple(),
                "normal": self.geometry.normal.to_tuple(),
                "start": self.geometry.start.to_tuple(),
                "angle_deg": math.degrees(self.geometry.angle),
            }
        return {"geometry": geom_d, "station_start": self.station_start}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AlignmentSegment":
        import math
        geom_d = d["geometry"]
        if geom_d["segment_type"] == "line":
            geom: Union[Line, Arc] = Line(Vec(*geom_d["start"]), Vec(*geom_d["end"]))
        else:
            geom = Arc(
                center=Vec(*geom_d["center"]),
                normal=Vec(*geom_d["normal"]),
                start=Vec(*geom_d["start"]),
                angle=math.radians(geom_d["angle_deg"]),
            )
        return cls(geometry=geom, station_start=d.get("station_start", 0.0))


# ---------------------------------------------------------------------------
# PendingAlignment
# ---------------------------------------------------------------------------

class PendingAlignment(PendingElement):
    """
    A horizontal alignment composed of ordered AlignmentSegment objects.

    Consecutive segments must share endpoints (G0 continuity).
    """

    element_type = "alignment"

    def __init__(
        self,
        segments: List[AlignmentSegment],
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.segments = list(segments)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["segments"] = [s.to_dict() for s in self.segments]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingAlignment":
        segments = [
            AlignmentSegment.from_dict(s)
            for s in cls._require(d, "segments")
        ]
        return cls(segments=segments, name=d.get("name", ""))


# ---------------------------------------------------------------------------
# BridgePartType
# ---------------------------------------------------------------------------

class BridgePartType(enum.Enum):
    DECK = "DECK"
    SUBSTRUCTURE = "SUBSTRUCTURE"
    FOUNDATION = "FOUNDATION"
    SUPERSTRUCTURE = "SUPERSTRUCTURE"


# ---------------------------------------------------------------------------
# PendingBridgePart
# ---------------------------------------------------------------------------

class PendingBridgePart(PendingElement):
    """
    A part of a bridge (deck, substructure, foundation, superstructure).

    Args:
        part_type:  BridgePartType enum value.
        elements:   List of PendingElement objects contained in this part.
        alignment:  Optional alignment this part follows.
        name:       Element name.
    """

    element_type = "bridge_part"

    def __init__(
        self,
        part_type: BridgePartType,
        elements: Optional[List[PendingElement]] = None,
        alignment: Optional[PendingAlignment] = None,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.part_type = part_type
        self.elements: List[PendingElement] = list(elements) if elements else []
        self.alignment = alignment

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["part_type"] = self.part_type.value
        d["elements"] = [e.to_dict() for e in self.elements]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingBridgePart":
        part_type = BridgePartType(cls._require(d, "part_type"))
        return cls(
            part_type=part_type,
            name=d.get("name", ""),
        )


# ---------------------------------------------------------------------------
# PendingBridge
# ---------------------------------------------------------------------------

class PendingBridge(PendingElement):
    """
    A bridge (IfcBridge in IFC4x3) composed of PendingBridgePart objects.

    Args:
        parts:      List of PendingBridgePart objects.
        alignment:  Optional primary alignment.
        name:       Element name.
    """

    element_type = "bridge"

    def __init__(
        self,
        parts: List[PendingBridgePart],
        alignment: Optional[PendingAlignment] = None,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.parts = list(parts)
        self.alignment = alignment

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["parts"] = [p.to_dict() for p in self.parts]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingBridge":
        parts = [PendingBridgePart.from_dict(p) for p in cls._require(d, "parts")]
        return cls(parts=parts, name=d.get("name", ""))
