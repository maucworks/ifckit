"""
ifckit.elements.structural
==========================

Pending structural elements: PendingBeam, PendingColumn, PendingRevolvedBeam.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ifckit.elements.base import ClipData, PendingElement
from ifckit.geometry import Arc, Line, Vec


class PendingBeam(PendingElement):
    """
    A straight beam defined by an axis (Line) and a cross-section profile.

    Args:
        axis:       Line from start to end of the beam.
        profile:    Closed list of Vec points defining the cross-section
                    in the local YZ plane (perpendicular to axis).
        name:       Element name.
        ref_line:   Optional reference line for web orientation.
        clip_data:  Optional clip plane data.
    """

    element_type = "basic_beam"

    def __init__(
        self,
        axis: Line,
        profile: List[Vec],
        name: str = "",
        ref_line: Optional[Line] = None,
        clip_data: Optional[ClipData] = None,
    ) -> None:
        super().__init__(name=name, clip_data=clip_data)
        self.axis = axis
        self.profile = list(profile)
        self.ref_line = ref_line

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["axis"] = {
            "start": self.axis.start.to_tuple(),
            "end": self.axis.end.to_tuple(),
        }
        d["profile"] = [p.to_tuple() for p in self.profile]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingBeam":
        axis_d = cls._require(d, "axis")
        axis = Line(Vec(*axis_d["start"]), Vec(*axis_d["end"]))
        profile = [Vec(*pt) for pt in cls._require(d, "profile")]
        return cls(
            axis=axis,
            profile=profile,
            name=d.get("name", ""),
            clip_data=d.get("clip_data"),
        )


class PendingColumn(PendingElement):
    """
    A column defined by an axis (Line) and a cross-section profile.

    Args:
        axis:       Line from base to top of the column.
        profile:    Closed list of Vec points defining the cross-section.
        name:       Element name.
        clip_data:  Optional clip plane data.
    """

    element_type = "basic_column"

    def __init__(
        self,
        axis: Line,
        profile: List[Vec],
        name: str = "",
        clip_data: Optional[ClipData] = None,
    ) -> None:
        super().__init__(name=name, clip_data=clip_data)
        self.axis = axis
        self.profile = list(profile)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["axis"] = {
            "start": self.axis.start.to_tuple(),
            "end": self.axis.end.to_tuple(),
        }
        d["profile"] = [p.to_tuple() for p in self.profile]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingColumn":
        axis_d = cls._require(d, "axis")
        axis = Line(Vec(*axis_d["start"]), Vec(*axis_d["end"]))
        profile = [Vec(*pt) for pt in cls._require(d, "profile")]
        return cls(
            axis=axis,
            profile=profile,
            name=d.get("name", ""),
            clip_data=d.get("clip_data"),
        )


class PendingRevolvedBeam(PendingElement):
    """
    A curved beam produced by revolving a profile along an Arc path.

    Args:
        arc:        The arc that defines the sweep path.
        profile:    Closed list of Vec points (cross-section in local YZ plane).
        name:       Element name.
        ref_line:   Optional reference line for orientation.
    """

    element_type = "revolved_beam"

    def __init__(
        self,
        arc: Arc,
        profile: List[Vec],
        name: str = "",
        ref_line: Optional[Line] = None,
    ) -> None:
        super().__init__(name=name, clip_data=None)
        self.arc = arc
        self.profile = list(profile)
        self.ref_line = ref_line

    def to_dict(self) -> Dict[str, Any]:
        import math
        d = super().to_dict()
        d["arc"] = {
            "center": self.arc.center.to_tuple(),
            "normal": self.arc.normal.to_tuple(),
            "start": self.arc.start.to_tuple(),
            "angle_deg": math.degrees(self.arc.angle),
        }
        d["profile"] = [p.to_tuple() for p in self.profile]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingRevolvedBeam":
        import math
        arc_d = cls._require(d, "arc")
        arc = Arc(
            center=Vec(*arc_d["center"]),
            normal=Vec(*arc_d["normal"]),
            start=Vec(*arc_d["start"]),
            angle=math.radians(arc_d["angle_deg"]),
        )
        profile = [Vec(*pt) for pt in cls._require(d, "profile")]
        return cls(arc=arc, profile=profile, name=d.get("name", ""))
