"""
ifckit.elements.structural
==========================

Pending structural elements: PendingBeam, PendingColumn, PendingRevolvedBeam.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from ifckit.elements.base import ClipData, PendingElement
from ifckit.geometry import Arc, Line, Plane, Vec


def _validate_up(up: Vec, axis: Line, cls_name: str) -> None:
    """Raise ValueError if up is parallel to axis direction."""
    if abs(up) == 0.0:
        raise ValueError(f"{cls_name}: up vector must not be zero-length")
    t = axis.direction.normalized()
    u = up.normalized()
    if abs(t @ u) > 0.999:
        raise ValueError(
            f"{cls_name}: up vector {up!r} is parallel to beam axis "
            f"{axis.direction!r} — cannot define a cross-section frame"
        )


class PendingBeam(PendingElement):
    """
    A straight beam defined by an axis (Line) and a cross-section profile.

    Args:
        axis:       Line from start to end of the beam.
        profile:    Closed list of Vec points defining the cross-section
                    in the local XY plane (perpendicular to axis).
        up:         Optional guide-up vector (world space).  Defines the
                    profile Y direction (vertical up in cross-section).
                    Must not be parallel to the beam axis — raises
                    ValueError immediately if it is.
                    Defaults to world +Z (or +Y if axis is vertical).
        name:       Element name.
        ref_line:   Optional reference line for web orientation.
        clip_data:  Optional clip plane data.
    """

    element_type = "basic_beam"

    def __init__(
        self,
        axis: Line,
        profile: List[Vec],
        up: Optional[Vec] = None,
        name: str = "",
        ref_line: Optional[Line] = None,
        clip_data: Optional[ClipData] = None,
    ) -> None:
        super().__init__(name=name, clip_data=clip_data)
        self.axis = axis
        self.profile = list(profile)
        self.ref_line = ref_line
        if up is not None:
            _validate_up(up, axis, "PendingBeam")
        self.up = up

    @classmethod
    def from_plane(
        cls,
        axis: Line,
        profile: List[Vec],
        plane: Plane,
        name: str = "",
        ref_line: Optional[Line] = None,
        clip_data: Optional[ClipData] = None,
    ) -> "PendingBeam":
        """Construct with up extracted from plane.y_axis."""
        return cls(
            axis=axis,
            profile=profile,
            up=plane.y_axis,
            name=name,
            ref_line=ref_line,
            clip_data=clip_data,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["axis"] = {
            "start": self.axis.start.to_tuple(),
            "end": self.axis.end.to_tuple(),
        }
        d["profile"] = [p.to_tuple() for p in self.profile]
        if self.up is not None:
            d["up"] = self.up.to_tuple()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingBeam":
        axis_d = cls._require(d, "axis")
        axis = Line(Vec(*axis_d["start"]), Vec(*axis_d["end"]))
        profile = [Vec(*pt) for pt in cls._require(d, "profile")]
        up_raw = d.get("up")
        up = Vec(*up_raw) if up_raw is not None else None
        return cls(
            axis=axis,
            profile=profile,
            up=up,
            name=d.get("name", ""),
            clip_data=d.get("clip_data"),
        )


class PendingColumn(PendingElement):
    """
    A column defined by an axis (Line) and a cross-section profile.

    Args:
        axis:       Line from base to top of the column.
        profile:    Closed list of Vec points defining the cross-section.
        up:         Optional guide-up vector (world space).  Defines the
                    profile Y direction.  Must not be parallel to the
                    column axis — raises ValueError immediately if it is.
                    Defaults to world +Z (or +Y if axis is vertical).
        name:       Element name.
        clip_data:  Optional clip plane data.
    """

    element_type = "basic_column"

    def __init__(
        self,
        axis: Line,
        profile: List[Vec],
        up: Optional[Vec] = None,
        name: str = "",
        clip_data: Optional[ClipData] = None,
    ) -> None:
        super().__init__(name=name, clip_data=clip_data)
        self.axis = axis
        self.profile = list(profile)
        if up is not None:
            _validate_up(up, axis, "PendingColumn")
        self.up = up

    @classmethod
    def from_plane(
        cls,
        axis: Line,
        profile: List[Vec],
        plane: Plane,
        name: str = "",
        clip_data: Optional[ClipData] = None,
    ) -> "PendingColumn":
        """Construct with up extracted from plane.y_axis."""
        return cls(
            axis=axis,
            profile=profile,
            up=plane.y_axis,
            name=name,
            clip_data=clip_data,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["axis"] = {
            "start": self.axis.start.to_tuple(),
            "end": self.axis.end.to_tuple(),
        }
        d["profile"] = [p.to_tuple() for p in self.profile]
        if self.up is not None:
            d["up"] = self.up.to_tuple()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingColumn":
        axis_d = cls._require(d, "axis")
        axis = Line(Vec(*axis_d["start"]), Vec(*axis_d["end"]))
        profile = [Vec(*pt) for pt in cls._require(d, "profile")]
        up_raw = d.get("up")
        up = Vec(*up_raw) if up_raw is not None else None
        return cls(
            axis=axis,
            profile=profile,
            up=up,
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
        clip_data:  Optional clip plane data.
    """

    element_type = "revolved_beam"

    def __init__(
        self,
        arc: Arc,
        profile: List[Vec],
        name: str = "",
        ref_line: Optional[Line] = None,
        clip_data: Optional[ClipData] = None,
    ) -> None:
        super().__init__(name=name, clip_data=clip_data)
        self.arc = arc
        self.profile = list(profile)
        self.ref_line = ref_line

    def to_dict(self) -> Dict[str, Any]:
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
        arc_d = cls._require(d, "arc")
        arc = Arc(
            center=Vec(*arc_d["center"]),
            normal=Vec(*arc_d["normal"]),
            start=Vec(*arc_d["start"]),
            angle=math.radians(arc_d["angle_deg"]),
        )
        profile = [Vec(*pt) for pt in cls._require(d, "profile")]
        return cls(arc=arc, profile=profile, name=d.get("name", ""))
