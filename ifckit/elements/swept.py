"""
ifckit.elements.swept
=====================

PendingSweptBeam: a beam swept along a Line, Arc, or mixed Path using
IfcFixedReferenceSweptAreaSolid.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Union

from ifckit.elements.base import PendingElement
from ifckit.elements.structural import (
    ProfileInput,
    _coerce_profile,
    _plane_from_dict,
    _plane_to_dict,
)
from ifckit.geometry import Arc, Line, Path, Plane, Vec

PathInput = Union[Line, Arc, Path]


def _validate_up_for_path(up: Vec, path: PathInput, cls_name: str) -> None:
    """
    Raise ValueError if *up* is parallel to any tangent along the path.

    For a Line the only tangent is the direction.
    For an Arc we check start and end tangents.
    For a Path we check every segment.
    """
    u = up.normalized()

    def _check(tangent: Vec) -> None:
        t = tangent.normalized()
        if abs(t @ u) > 0.999:
            raise ValueError(
                f"{cls_name}: up vector {up!r} is parallel to path tangent "
                f"{tangent!r} — cannot define a cross-section frame"
            )

    if isinstance(path, Line):
        _check(path.direction)
    elif isinstance(path, Arc):
        _check(path.tangent_at_start())
        _check(path.tangent_at_end())
    else:  # Path
        for seg in path.segments:
            if isinstance(seg, Line):
                _check(seg.direction)
            else:
                _check(seg.tangent_at_start())
                _check(seg.tangent_at_end())


class PendingSweptBeam(PendingElement):
    """
    A beam produced by sweeping a profile along a Line, Arc, or mixed Path
    using IfcFixedReferenceSweptAreaSolid.

    Args:
        path:        The directrix — a Line, Arc, or Path.
        profile:     Closed cross-section profile (Vec list, tuple list,
                     or any object with ``get_profile_points()``).
        up:          Optional guide-up vector (world space).  Used as the
                     FixedReference for the sweep (profile Y direction).
                     Must not be parallel to any tangent along the path.
                     Defaults to world +Z (or +Y as fallback).
        start_clip:  Optional Plane to clip the start of the sweep.
                     z_axis points toward material to keep.
        end_clip:    Optional Plane to clip the end of the sweep.
                     z_axis points toward material to keep.
        name:        Element name.
    """

    element_type = "swept_beam"

    def __init__(
        self,
        path: PathInput,
        profile: ProfileInput,
        up: Optional[Vec] = None,
        start_clip: Optional[Plane] = None,
        end_clip: Optional[Plane] = None,
        name: str = "",
        style=None,
    ) -> None:
        super().__init__(name=name, style=style)
        self.path = path
        self.profile = _coerce_profile(profile)
        self.start_clip = start_clip
        self.end_clip = end_clip
        if up is not None:
            _validate_up_for_path(up, path, "PendingSweptBeam")
        self.up = up

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    @staticmethod
    def _path_to_dict(path: PathInput) -> Dict[str, Any]:
        if isinstance(path, Line):
            return {
                "type": "line",
                "start": path.start.to_tuple(),
                "end": path.end.to_tuple(),
            }
        if isinstance(path, Arc):
            return {
                "type": "arc",
                "center": path.center.to_tuple(),
                "normal": path.normal.to_tuple(),
                "start": path.start.to_tuple(),
                "angle_deg": math.degrees(path.angle),
            }
        # Path
        segs = []
        for seg in path.segments:
            if isinstance(seg, Line):
                segs.append(
                    {
                        "type": "line",
                        "start": seg.start.to_tuple(),
                        "end": seg.end.to_tuple(),
                    }
                )
            else:
                segs.append(
                    {
                        "type": "arc",
                        "center": seg.center.to_tuple(),
                        "normal": seg.normal.to_tuple(),
                        "start": seg.start.to_tuple(),
                        "angle_deg": math.degrees(seg.angle),
                    }
                )
        return {"type": "path", "segments": segs}

    @staticmethod
    def _path_from_dict(d: Dict[str, Any]) -> PathInput:
        kind = d["type"]
        if kind == "line":
            return Line(Vec(*d["start"]), Vec(*d["end"]))
        if kind == "arc":
            return Arc(
                center=Vec(*d["center"]),
                normal=Vec(*d["normal"]),
                start=Vec(*d["start"]),
                angle=math.radians(d["angle_deg"]),
            )
        # path
        p = Path()
        for seg in d["segments"]:
            if seg["type"] == "line":
                p.add_line(Vec(*seg["start"]), Vec(*seg["end"]))
            else:
                p.add_arc(
                    center=Vec(*seg["center"]),
                    normal=Vec(*seg["normal"]),
                    start=Vec(*seg["start"]),
                    angle=math.radians(seg["angle_deg"]),
                )
        return p

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["path"] = self._path_to_dict(self.path)
        d["profile"] = [p.to_tuple() for p in self.profile]
        if self.up is not None:
            d["up"] = self.up.to_tuple()
        if self.start_clip is not None:
            d["start_clip"] = _plane_to_dict(self.start_clip)
        if self.end_clip is not None:
            d["end_clip"] = _plane_to_dict(self.end_clip)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingSweptBeam":
        path = cls._path_from_dict(cls._require(d, "path"))
        profile = [Vec(*pt) for pt in cls._require(d, "profile")]
        up_raw = d.get("up")
        up = Vec(*up_raw) if up_raw is not None else None
        return cls(
            path=path,
            profile=profile,
            up=up,
            start_clip=_plane_from_dict(d["start_clip"]) if "start_clip" in d else None,
            end_clip=_plane_from_dict(d["end_clip"]) if "end_clip" in d else None,
            name=d.get("name", ""),
            style=cls._style_from_dict(d),
        )
