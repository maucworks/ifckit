"""
ifckit.elements.structural
==========================

Pending structural elements: PendingBeam, PendingColumn, PendingRevolvedBeam.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from ifckit.elements.base import PendingElement, UserProperties
from ifckit.elements.style import RenderStyle
from ifckit.geometry import Arc, Line, Path, Plane, Vec

# A profile point can be a Vec or a plain (x, y) or (x, y, z) tuple.
# A profile source can also be any object with get_profile_points(), or a Profile.
ProfilePoint = Union[Vec, Tuple[float, float], Tuple[float, float, float]]
ProfileInput = Union[Sequence[ProfilePoint], Any]  # Any = duck-typed profile object


def _coerce_profile(profile: ProfileInput) -> List[Vec]:
    """
    Coerce a profile to List[Vec].

    Accepts:
      - A ``Profile`` subclass instance (``ifckit.profiles.base.Profile``) — calls
        ``get_profile_points()`` to obtain the outline.
      - Any object with a ``get_profile_points()`` method (legacy duck-typing).
      - A sequence of Vec.
      - A sequence of (x, y) or (x, y, z) tuples.
    """
    if hasattr(profile, "get_profile_points"):
        profile = profile.get_profile_points()
    result = []
    for p in profile:
        if isinstance(p, Vec):
            result.append(p)
        elif len(p) == 2:  # type: ignore[arg-type]
            result.append(Vec(p[0], p[1], 0.0))
        else:
            result.append(Vec(p[0], p[1], p[2]))  # type: ignore[index]
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
    if abs(up) < 1e-12:
        raise ValueError(f"{cls_name}: up vector must not be zero-length")
    t = axis.direction.normalized()
    u = up.normalized()
    if abs(t @ u) > 0.999:
        raise ValueError(
            f"{cls_name}: up vector {up!r} is parallel to beam axis "
            f"{axis.direction!r} — cannot define a cross-section frame"
        )


class PendingExtrudedElement(PendingElement):
    """
    Shared base for straight extruded structural elements (beam, column).

    Holds the common data: axis, profile, up, clips.
    Subclasses must declare ``element_type``.

    ``clips`` is a list of ``Plane`` objects (world space).  Each plane's
    z_axis points toward the material to keep.  Applied in order as
    IfcBooleanClippingResult.

    For backwards compatibility, ``start_clip`` and ``end_clip`` keyword
    arguments are still accepted and prepended to ``clips``.
    """

    def __init__(
        self,
        axis: Line,
        profile: "Sequence[ProfilePoint]",
        up: Optional[Vec] = None,
        clips: Optional[List[Plane]] = None,
        # backwards-compat — converted to clips entries
        start_clip: Optional[Plane] = None,
        end_clip: Optional[Plane] = None,
        name: str = "",
        style: Optional[RenderStyle] = None,
        properties: Optional[UserProperties] = None,
    ) -> None:
        # Build clips list: explicit clips first, then legacy start/end
        merged: List[Plane] = list(clips) if clips else []
        if start_clip is not None:
            merged.insert(0, start_clip)
        if end_clip is not None:
            merged.append(end_clip)
        super().__init__(name=name, clips=merged, style=style, properties=properties)
        self.axis = axis
        self._profile_source = profile  # preserve original Profile object if given
        self.profile = _coerce_profile(profile)
        if up is not None:
            _validate_up(up, axis, type(self).__name__)
        self.up = up

    @classmethod
    def from_plane(
        cls,
        axis: Line,
        profile: "List[Vec]",
        plane: Plane,
        up: Optional[Vec] = None,
        clips: Optional[List[Plane]] = None,
        name: str = "",
    ) -> "PendingExtrudedElement":
        """Construct with up extracted from plane.y_axis."""
        return cls(
            axis=axis,
            profile=profile,
            up=plane.y_axis,
            clips=clips,
            name=name,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["axis"] = {
            "start": self.axis.start.to_tuple(),
            "end": self.axis.end.to_tuple(),
        }
        # Prefer to serialize the original profile object (preserves type + metadata).
        from ifckit.profiles.base import Profile as _Profile

        if isinstance(self._profile_source, _Profile):
            d["profile"] = self._profile_source.to_dict()
        else:
            d["profile"] = [p.to_tuple() for p in self.profile]
        if self.up is not None:
            d["up"] = self.up.to_tuple()
        return d

    @classmethod
    def _from_dict_fields(cls, d: Dict[str, Any]) -> "PendingExtrudedElement":
        """Shared from_dict logic; subclasses call this."""
        axis_d = cls._require(d, "axis")
        axis = Line(Vec(*axis_d["start"]), Vec(*axis_d["end"]))
        profile_raw = cls._require(d, "profile")
        # Profile can be a dict (Profile subclass) or a list of point tuples.
        if isinstance(profile_raw, dict) and "profile_type" in profile_raw:
            from ifckit.profiles.base import Profile as _Profile

            profile: Any = _Profile.dispatch_from_dict(profile_raw)
        else:
            profile = [Vec(*pt) for pt in profile_raw]
        up_raw = d.get("up")
        up = Vec(*up_raw) if up_raw is not None else None

        # Support both new "clips" list and legacy "start_clip"/"end_clip" keys.
        clips = cls._clips_from_dict(d)
        if not clips:
            legacy: List[Plane] = []
            if "start_clip" in d:
                legacy.insert(0, _plane_from_dict(d["start_clip"]))
            if "end_clip" in d:
                legacy.append(_plane_from_dict(d["end_clip"]))
            clips = legacy

        return cls(
            axis=axis,
            profile=profile,
            up=up,
            clips=clips,
            name=d.get("name", ""),
            style=cls._style_from_dict(d),
            properties=d.get("properties") or {},
        )


class PendingBeam(PendingExtrudedElement):
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
        clips:      Optional list of Planes for boolean clipping. Each
                    plane's z_axis points toward the material to keep.
        name:       Element name.
        ref_line:   Optional reference line for web orientation.
    """

    element_type = "basic_beam"

    def __init__(
        self,
        axis: Line,
        profile: "Sequence[ProfilePoint]",
        up: Optional[Vec] = None,
        clips: Optional[List[Plane]] = None,
        # backwards-compat
        start_clip: Optional[Plane] = None,
        end_clip: Optional[Plane] = None,
        name: str = "",
        ref_line: Optional[Line] = None,
        style: Optional[RenderStyle] = None,
        properties: Optional[UserProperties] = None,
    ) -> None:
        super().__init__(
            axis=axis,
            profile=profile,
            up=up,
            clips=clips,
            start_clip=start_clip,
            end_clip=end_clip,
            name=name,
            style=style,
            properties=properties,
        )
        self.ref_line = ref_line

    @classmethod
    def from_plane(  # type: ignore[override]
        cls,
        axis: Line,
        profile: "List[Vec]",
        plane: Plane,
        up: Optional[Vec] = None,
        clips: Optional[List[Plane]] = None,
        name: str = "",
        ref_line: Optional[Line] = None,
    ) -> "PendingBeam":
        """Construct with up extracted from plane.y_axis."""
        return cls(
            axis=axis,
            profile=profile,
            up=plane.y_axis,
            clips=clips,
            name=name,
            ref_line=ref_line,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        if self.ref_line is not None:
            d["ref_line"] = {
                "start": self.ref_line.start.to_tuple(),
                "end": self.ref_line.end.to_tuple(),
            }
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingBeam":
        obj = cls._from_dict_fields(d)  # type: ignore[return-value]
        ref_line_d = d.get("ref_line")
        if ref_line_d is not None:
            obj.ref_line = Line(Vec(*ref_line_d["start"]), Vec(*ref_line_d["end"]))
        return obj  # type: ignore[return-value]


class PendingColumn(PendingExtrudedElement):
    """
    A column defined by an axis (Line) and a cross-section profile.

    Args:
        axis:       Line from base to top of the column.
        profile:    Closed list of Vec points defining the cross-section.
        up:         Optional guide-up vector (world space).  Defines the
                    profile Y direction.  Must not be parallel to the
                    column axis — raises ValueError immediately if it is.
                    Defaults to world +Z (or +Y if axis is vertical).
        clips:      Optional list of Planes for boolean clipping.
        name:       Element name.
    """

    element_type = "basic_column"

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingColumn":
        return cls._from_dict_fields(d)  # type: ignore[return-value]


class PendingTaperedExtrusion(PendingElement):
    """
    A tapered extrusion defined by a plane, start profile, end profile, and height.

    Produces ``IfcExtrudedAreaSolidTapered`` in IFC, where the cross-section
    linearly transitions from *start_profile* to *end_profile* along the
    extrusion axis.

    Both profiles must have the same number of points.

    Args:
        plane:          Placement plane (defines position and orientation).
        start_profile:  Start profile — a ``Path`` or ``List[Vec]``.
        end_profile:    End profile — a ``Path`` or ``List[Vec]``
                        (same type + same point count as start).
        height:         Extrusion distance along ``plane.z_axis`` (metres).
        name:           Element name.
    """

    element_type = "tapered_extrusion"

    def __init__(
        self,
        plane: Plane,
        start_profile: Union[Path, List[Vec]],
        end_profile: Union[Path, List[Vec]],
        height: float,
        name: str = "",
        style: Optional[RenderStyle] = None,
        properties: Optional[UserProperties] = None,
    ) -> None:
        super().__init__(name=name, style=style, properties=properties)
        self.plane = plane
        self._start_src = start_profile
        self._end_src = end_profile

        self._start_len = self._profile_point_count(start_profile, plane)
        self._end_len = self._profile_point_count(end_profile, plane)

        if self._start_len < 3:
            raise ValueError("start_profile must have at least 3 points")
        if self._start_len != self._end_len:
            raise ValueError(
                f"start_profile ({self._start_len} pts) and "
                f"end_profile ({self._end_len} pts) must have equal point count"
            )

        self.height = float(height)

    @staticmethod
    def _profile_point_count(profile: Union[Path, List[Vec]], plane: Plane) -> int:
        if isinstance(profile, Path):
            pts = profile.to_profile_points(plane)
            return len(pts)
        return len(profile)

    def _resolve_pts(self, profile: Union[Path, List[Vec]], plane: Plane) -> List[tuple]:
        """Resolve profile to a list of 2D (u, v) points in *plane* local coords."""
        if isinstance(profile, Path):
            return profile.to_profile_points(plane)
        from ifckit.builders._geom import project_profile_to_plane as _proj

        return _proj(profile, plane)

    @property
    def start_profile(self) -> List[Vec]:
        """Start profile as resolved list of Vec (projected to plane XY)."""
        if isinstance(self._start_src, Path):
            pts = self._start_src.to_profile_points(self.plane)
            return [Vec(u, v, 0) for u, v in pts]
        return list(self._start_src)

    @property
    def end_profile(self) -> List[Vec]:
        """End profile as resolved list of Vec (projected to plane XY)."""
        if isinstance(self._end_src, Path):
            pts = self._end_src.to_profile_points(self.plane)
            return [Vec(u, v, 0) for u, v in pts]
        return list(self._end_src)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["plane"] = self.plane.to_dict()
        d["height"] = self.height
        _start = self._start_src
        _end = self._end_src
        if isinstance(_start, Path):
            pts = _start.to_profile_points(self.plane)
            d["start_profile"] = {
                "type": "path",
                "pts": [[u, v] for u, v in pts],
            }
        else:
            d["start_profile"] = [p.to_tuple() for p in _start]
        if isinstance(_end, Path):
            pts = _end.to_profile_points(self.plane)
            d["end_profile"] = {
                "type": "path",
                "pts": [[u, v] for u, v in pts],
            }
        else:
            d["end_profile"] = [p.to_tuple() for p in _end]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingTaperedExtrusion":
        plane = Plane.from_dict(cls._require(d, "plane"))
        height = cls._require(d, "height")
        raw_start = cls._require(d, "start_profile")
        raw_end = cls._require(d, "end_profile")

        def _resolve(raw):
            if isinstance(raw, dict) and raw.get("type") == "path":
                pts = [plane.origin + plane.x_axis * u + plane.y_axis * v for u, v in raw["pts"]]
                return Path.from_pts(pts, closed=True)
            return [Vec(*pt) for pt in raw]

        return cls(
            plane=plane,
            start_profile=_resolve(raw_start),
            end_profile=_resolve(raw_end),
            height=height,
            name=d.get("name", ""),
            style=cls._style_from_dict(d),
            properties=d.get("properties") or {},
        )


class PendingRevolvedBeam(PendingElement):
    """
    A curved beam produced by revolving a profile along an Arc path.

    Args:
        arc:        The arc that defines the sweep path.
        profile:    Closed list of Vec points (cross-section in local YZ plane).
        name:       Element name.
        ref_line:   Optional reference line for orientation.
        cp_normal:  Canonical plane normal — if arc.normal opposes this,
                   the profile is flipped 180° to maintain continuity.
        plane:      Optional Plane — when set, ``plane.z_axis`` is used as
                   the canonical normal (equivalent to *cp_normal*).
                   Serialised for round‑trip but not used by the builder.
        clip_data:  Optional clip plane data.
    """

    element_type = "revolved_beam"

    def __init__(
        self,
        arc: Arc,
        profile: Sequence[ProfilePoint],
        name: str = "",
        ref_line: Optional[Line] = None,
        cp_normal: Optional[Vec] = None,
        plane: Optional["Plane"] = None,
        style: Optional[RenderStyle] = None,
        properties: Optional[UserProperties] = None,
    ) -> None:
        super().__init__(name=name, style=style, properties=properties)
        self.arc = arc
        self._profile_source = profile
        self.profile = _coerce_profile(profile)
        self.ref_line = ref_line
        self.cp_normal = cp_normal
        self.plane = plane

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["arc"] = {
            "center": self.arc.center.to_tuple(),
            "normal": self.arc.normal.to_tuple(),
            "start": self.arc.start.to_tuple(),
            "angle_deg": math.degrees(self.arc.angle),
        }
        d["profile"] = [p.to_tuple() for p in self.profile]
        if self.cp_normal is not None:
            d["cp_normal"] = self.cp_normal.to_tuple()
        if self.plane is not None:
            d["plane"] = {
                "origin": self.plane.origin.to_tuple(),
                "x_axis": self.plane.x_axis.to_tuple(),
                "y_axis": self.plane.y_axis.to_tuple(),
            }
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
        cp_normal = Vec(*d["cp_normal"]) if "cp_normal" in d else None
        plane_d = d.get("plane")
        if plane_d:
            plane = Plane(
                Vec(*plane_d["origin"]),
                Vec(*plane_d["x_axis"]),
                Vec(*plane_d["y_axis"]),
            )
        else:
            plane = None
        return cls(
            arc=arc,
            profile=profile,
            name=d.get("name", ""),
            cp_normal=cp_normal,
            plane=plane,
            style=cls._style_from_dict(d),
            properties=d.get("properties") or {},
        )
