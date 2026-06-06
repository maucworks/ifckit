"""
PendingSectionedSpine — Sectioned Spine pending element.

A sectioned spine sweeps a profile along a 3D spine curve, with potentially
different profiles at each position along the spine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ifckit.elements.base import PendingElement

if TYPE_CHECKING:
    from ifckit.geometry import Path, Plane
    from ifckit.profiles import Profile


class PendingSectionedSpine(PendingElement):
    """Sectioned spine pending element.

    Creates an IfcSectionedSpine by sweeping cross-sectional
    profiles along a spine curve.

    Attributes:
        spine: Path (Line/Arc segments) defining the 3D curve
        profiles: List of Profile entities (one per position)
        positions: List of Plane entities defining profile
                   positions/orientations along the spine

    Example:
        from ifckit.geometry import Path, Plane, Vec
        from ifckit.profiles import RectangleProfile

        # Spine: rechte lijn
        spine = Path.from_pts([Vec(0,0,0), Vec(1000,0,0)])

        # Profiel op positie 1 en 2
        p1 = RectangleProfile(50, 70)
        p2 = RectangleProfile(50, 70)

        # Posities langs spine
        pos1 = Plane(Vec(0,0,0), Vec(1,0,0), Vec(0,1,0))
        pos2 = Plane(Vec(1000,0,0), Vec(1,0,0), Vec(0,1,0))

        pending = PendingSectionedSpine(
            spine=spine,
            profiles=[p1, p2],
            positions=[pos1, pos2],
            name="my_spine"
        )
    """

    element_type = "sectioned_spine"

    def __init__(
        self,
        spine: "Path",
        profiles: List["Profile"],
        positions: List["Plane"],
        name: str = "",
        style: Any = None,
        properties: Any = None,
        profile_segments: int = 32,
        closed: bool = False,
        profile_overrides: Optional[Dict[int, "Profile"]] = None,
    ):
        super().__init__(
            name=name,
            style=style,
            properties=properties,
        )
        self.spine = spine
        self.profiles = profiles
        self.positions = positions
        self.profile_segments = profile_segments
        self.closed = closed
        self.profile_overrides = profile_overrides if profile_overrides else {}

        # Validation
        if len(profiles) != len(positions):
            raise ValueError(
                f"profiles ({len(profiles)}) must have same length as positions ({len(positions)})"
            )
        if len(profiles) < 2:
            raise ValueError("At least 2 profiles are required")

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["spine"] = self.spine.to_dict()
        d["profiles"] = [p.to_dict() for p in self.profiles]
        d["positions"] = [p.to_dict() for p in self.positions]
        d["profile_segments"] = self.profile_segments
        d["closed"] = self.closed
        if self.profile_overrides:
            d["profile_overrides"] = {
                str(k): v.to_dict() for k, v in self.profile_overrides.items()
            }
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingSectionedSpine":
        from ifckit.geometry import Path, Plane
        from ifckit.profiles.base import Profile as _Profile

        spine = Path.from_dict(cls._require(d, "spine"))
        profile_dicts = cls._require(d, "profiles")
        profiles = [_Profile.dispatch_from_dict(pd) for pd in profile_dicts]
        position_dicts = cls._require(d, "positions")
        positions = [Plane.from_dict(p) for p in position_dicts]
        profile_segments = d.get("profile_segments", 32)
        closed = d.get("closed", False)
        profile_overrides_raw = d.get("profile_overrides")
        profile_overrides: Optional[Dict[int, "Profile"]] = None
        if profile_overrides_raw:
            profile_overrides = {
                int(k): _Profile.dispatch_from_dict(v) for k, v in profile_overrides_raw.items()
            }
        return cls(
            spine=spine,
            profiles=profiles,
            positions=positions,
            name=d.get("name", ""),
            style=cls._style_from_dict(d),
            properties=d.get("properties"),
            profile_segments=profile_segments,
            closed=closed,
            profile_overrides=profile_overrides,
        )
