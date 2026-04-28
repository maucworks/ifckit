"""
ifckit.profiles.l_beam
======================

LBeamProfile: L-section (angle) profile.

Anchor points (where (0, 0) is placed relative to the profile):

        nw    n    ne
         |    |    |
    w----+----+----+----e
         |    |    |
    sw    s    se

    sw  bottom-left corner  (default)
    s   mid bottom
    se  bottom-right corner
    w   mid left
    c   centre of bounding box
    e   mid right
    nw  top-left corner
    n   mid top
    ne  top-right corner

Points are returned in the local YZ plane (Y = horizontal, Z = vertical),
suitable for use as a PendingBeam / PendingColumn profile in ifckit.
"""

from __future__ import annotations

from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ifckit.geometry import Vec


# Anchor → (x_fraction_of_width, y_fraction_of_height)
_ANCHOR_OFFSETS: dict[str, Tuple[float, float]] = {
    'sw': ( 0.0,  0.0),
    's':  (-0.5,  0.0),
    'se': (-1.0,  0.0),
    'w':  ( 0.0, -0.5),
    'c':  (-0.5, -0.5),
    'e':  (-1.0, -0.5),
    'nw': ( 0.0, -1.0),
    'n':  (-0.5, -1.0),
    'ne': (-1.0, -1.0),
}


class LBeamProfile:
    """
    L-section (angle) profile.

    Args:
        height:     Vertical leg height (m).
        width:      Horizontal leg width (m).
        thickness:  Leg thickness (m), equal for both legs.
        anchor:     Origin anchor point (default 'sw' = bottom-left corner).
        name:       Profile name.
    """

    def __init__(
        self,
        height: float = 0.3,
        width: float = 0.3,
        thickness: float = 0.02,
        anchor: str = 'sw',
        name: str = "L-Profile",
    ) -> None:
        self.height = float(height)
        self.width = float(width)
        self.thickness = float(thickness)
        self.anchor = anchor.lower()
        self.name = name
        self._validate()

    def _validate(self) -> None:
        if self.height <= 0:
            raise ValueError("height must be positive")
        if self.width <= 0:
            raise ValueError("width must be positive")
        if self.thickness <= 0 or self.thickness >= self.height or self.thickness >= self.width:
            raise ValueError("thickness must be > 0 and < both height and width")
        if self.anchor not in _ANCHOR_OFFSETS:
            raise ValueError(
                f"anchor must be one of {list(_ANCHOR_OFFSETS.keys())}, got '{self.anchor}'"
            )

    def _origin_offset(self) -> Tuple[float, float]:
        fx, fy = _ANCHOR_OFFSETS[self.anchor]
        return fx * self.width, fy * self.height

    # ------------------------------------------------------------------
    # Section properties
    # ------------------------------------------------------------------

    @property
    def area(self) -> float:
        return (
            self.width * self.thickness
            + (self.height - self.thickness) * self.thickness
        )

    @property
    def centroid_y(self) -> float:
        """Y (horizontal) distance of centroid from left edge of vertical leg."""
        t = self.thickness
        h = self.height
        w = self.width
        area_vert = t * h
        area_horiz = (w - t) * t
        return (area_vert * t / 2 + area_horiz * (t + (w - t) / 2)) / (area_vert + area_horiz)

    @property
    def centroid_z(self) -> float:
        """Z (vertical) distance of centroid from bottom edge of horizontal leg."""
        t = self.thickness
        h = self.height
        w = self.width
        area_vert = t * (h - t)
        area_horiz = w * t
        return (area_horiz * t / 2 + area_vert * (t + (h - t) / 2)) / (area_horiz + area_vert)

    # ------------------------------------------------------------------
    # Profile points
    # ------------------------------------------------------------------

    def get_profile_points(self) -> List[Tuple[float, float]]:
        """
        Return 6 (y, z) points defining the closed L-section in the local YZ plane.
        The closing duplicate is NOT included; profile_from_points() adds it automatically.

        Profile shape (anchor='sw', origin at bottom-left):

            5
            |\\
            | \\
            4  3---2
            |      |
            0------1
        """
        oy, oz = self._origin_offset()

        h = self.height
        w = self.width
        t = self.thickness

        return [
            (oy,     oz    ),   # 0  bottom-left
            (oy + w, oz    ),   # 1  bottom-right
            (oy + w, oz + t),   # 2  top of horizontal leg, right
            (oy + t, oz + t),   # 3  inner corner
            (oy + t, oz + h),   # 4  top of vertical leg, inner
            (oy,     oz + h),   # 5  top-left
        ]

    def to_beam_profile(self) -> "List[Vec]":
        """
        Return profile points as a list of ifckit Vec for use with PendingBeam/PendingColumn.

        Maps (y, z) → Vec(z, y) to match the BeamBuilder cross-section convention.
        """
        from ifckit.geometry import Vec as _Vec
        return [_Vec(z, y) for y, z in self.get_profile_points()]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "height": self.height,
            "width": self.width,
            "thickness": self.thickness,
            "anchor": self.anchor,
            "area": self.area,
            "centroid_y": self.centroid_y,
            "centroid_z": self.centroid_z,
        }
