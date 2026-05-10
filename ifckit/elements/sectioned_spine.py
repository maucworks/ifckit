"""
PendingSectionedSpine — Sectioned Spine pending element.

A sectioned spine sweeps a profile along a 3D spine curve, with potentially
different profiles at each position along the spine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

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
        style: Optional = None,
        properties: Optional = None,
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
