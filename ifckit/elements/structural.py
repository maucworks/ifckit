"""
ifckit.elements.structural
==========================

Pending structural elements: PendingBeam, PendingColumn, PendingRevolvedBeam.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from ifckit.elements.base import PendingElement
from ifckit.geometry import Arc, Line, Plane, Vec

# A profile point can be a Vec or a plain (x, y) or (x, y, z) tuple.
ProfilePoint = Union[Vec, Tuple[float, float], Tuple[float, float, float]]


def _coerce_profile(points: Sequence[ProfilePoint]) -> List[Vec]:
    """Coerce a mixed list of Vec / (x,y) / (x,y,z) tuples to List[Vec]."""
    result = []
    for p in points:
        if isinstance(p, Vec):
            result.append(p)
        elif len(p) == 2:
            result.append(Vec(p[0], p[1], 0.0))
        else:
            result.append(Vec(p[0], p[1], p[2]))
    return result


def _plane_to_dict(plane: Plane) -> Dict[str, Any]:
    return {
        "origin": plane.origin.to_tuple(),
        "x_axis": plane.x_axis.to_tuple(),
        "y_axis": plane.y_axis.to_tuple(),
    }


def _plane_from_dict(d: Dict[str, Any]) -> Plane:
    return Plane(Vec(*d["origin"]), Vec(*d["x_axis"]), Vec(*d["y_axis"]))


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
        axis:        Line from start to end of the beam.
        profile:     Closed list of Vec points defining the cross-section
                     in the local XY plane (perpendicular to axis).
        up:          Optional guide-up vector (world space).  Defines the
                     profile Y direction (vertical up in cross-section).
                     Must not be parallel to the beam axis — raises
                     ValueError immediately if it is.
                     Defaults to world +Z (or +Y if axis is vertical).
        start_clip:  Optional Plane that clips the start of the extrusion.
                     The plane's z_axis points toward the material to keep.
        end_clip:    Optional Plane that clips the end of the extrusion.
                     The plane's z_axis points toward the material to keep.
        name:        Element name.
        ref_line:    Optional reference line for web orientation.
    """

    element_type = "basic_beam"

    def __init__(
        self,
        axis: Line,
        profile: Sequence[ProfilePoint],
        up: Optional[Vec] = None,
        start_clip: Optional[Plane] = None,
        end_clip: Optional[Plane] = None,
        name: str = "",
        ref_line: Optional[Line] = None,
    ) -> None:
        super().__init__(name=name)
        self.axis = axis
        self.profile = _coerce_profile(profile)
        self.ref_line = ref_line
        self.start_clip = start_clip
        self.end_clip = end_clip
        if up is not None:
            _validate_up(up, axis, "PendingBeam")
        self.up = up

    @classmethod
    def from_plane(
        cls,
        axis: Line,
        profile: List[Vec],
        plane: Plane,
        up: Optional[Vec] = None,
        start_clip: Optional[Plane] = None,
        end_clip: Optional[Plane] = None,
        name: str = "",
        ref_line: Optional[Line] = None,
    ) -> "PendingBeam":
        """Construct with up extracted from plane.y_axis."""
        return cls(
            axis=axis,
            profile=profile,
            up=plane.y_axis,
            start_clip=start_clip,
            end_clip=end_clip,
            name=name,
            ref_line=ref_line,
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
        if self.start_clip is not None:
            d["start_clip"] = _plane_to_dict(self.start_clip)
        if self.end_clip is not None:
            d["end_clip"] = _plane_to_dict(self.end_clip)
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
            start_clip=_plane_from_dict(d["start_clip"]) if "start_clip" in d else None,
            end_clip=_plane_from_dict(d["end_clip"]) if "end_clip" in d else None,
            name=d.get("name", ""),
        )


class PendingColumn(PendingElement):
    """
    A column defined by an axis (Line) and a cross-section profile.

    Args:
        axis:        Line from base to top of the column.
        profile:     Closed list of Vec points defining the cross-section.
        up:          Optional guide-up vector (world space).  Defines the
                     profile Y direction.  Must not be parallel to the
                     column axis — raises ValueError immediately if it is.
                     Defaults to world +Z (or +Y if axis is vertical).
        start_clip:  Optional Plane that clips the base of the extrusion.
        end_clip:    Optional Plane that clips the top of the extrusion.
        name:        Element name.
    """

    element_type = "basic_column"

    def __init__(
        self,
        axis: Line,
        profile: Sequence[ProfilePoint],
        up: Optional[Vec] = None,
        start_clip: Optional[Plane] = None,
        end_clip: Optional[Plane] = None,
        name: str = "",
    ) -> None:
        super().__init__(name=name)
        self.axis = axis
        self.profile = _coerce_profile(profile)
        self.start_clip = start_clip
        self.end_clip = end_clip
        if up is not None:
            _validate_up(up, axis, "PendingColumn")
        self.up = up

    @classmethod
    def from_plane(
        cls,
        axis: Line,
        profile: List[Vec],
        plane: Plane,
        up: Optional[Vec] = None,
        start_clip: Optional[Plane] = None,
        end_clip: Optional[Plane] = None,
        name: str = "",
    ) -> "PendingColumn":
        """Construct with up extracted from plane.y_axis."""
        return cls(
            axis=axis,
            profile=profile,
            up=plane.y_axis,
            start_clip=start_clip,
            end_clip=end_clip,
            name=name,
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
        if self.start_clip is not None:
            d["start_clip"] = _plane_to_dict(self.start_clip)
        if self.end_clip is not None:
            d["end_clip"] = _plane_to_dict(self.end_clip)
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
            start_clip=_plane_from_dict(d["start_clip"]) if "start_clip" in d else None,
            end_clip=_plane_from_dict(d["end_clip"]) if "end_clip" in d else None,
            name=d.get("name", ""),
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
        profile: Sequence[ProfilePoint],
        name: str = "",
        ref_line: Optional[Line] = None,
    ) -> None:
        super().__init__(name=name)
        self.arc = arc
        self.profile = _coerce_profile(profile)
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
