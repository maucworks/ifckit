"""
ifckit.profiles.i_beam
======================

IBeamProfile: symmetric I-section (wide-flange) profile.

Anchor points (where (0, 0) is placed relative to the profile):

        nw    n    ne
         |    |    |
    w----+----+----+----e
         |    |    |
    sw    s    se

    sw  bottom-left corner
    s   mid bottom
    se  bottom-right corner
    w   mid left
    c   centroid (geometric centre of bounding box)
    e   mid right
    nw  top-left corner
    n   mid top
    ne  top-right corner

Points are returned in the local YZ plane (Y = horizontal, Z = vertical),
suitable for use as a PendingBeam / PendingColumn profile in ifckit.
"""

from __future__ import annotations

from typing import List, Tuple


# Anchor → (x_fraction_of_width, y_fraction_of_height)
# Applied as: offset = (-fraction * width, -fraction * height)
_ANCHOR_OFFSETS: dict[str, Tuple[float, float]] = {
    'sw': (-0.5,  0.0),
    's':  ( 0.0,  0.0),
    'se': ( 0.5,  0.0),
    'w':  (-0.5,  0.5),
    'c':  ( 0.0,  0.5),
    'e':  ( 0.5,  0.5),
    'nw': (-0.5,  1.0),
    'n':  ( 0.0,  1.0),
    'ne': ( 0.5,  1.0),
}


class IBeamProfile:
    """
    Symmetric I-section profile.

    Args:
        height:           Total height (m).
        width:            Flange width (m).
        web_thickness:    Web thickness (m).
        flange_thickness: Flange thickness (m).
        anchor:           Origin anchor point (default 's' = mid bottom).
        name:             Profile name.
    """

    def __init__(
        self,
        height: float = 0.5,
        width: float = 0.3,
        web_thickness: float = 0.02,
        flange_thickness: float = 0.025,
        anchor: str = 's',
        name: str = "I-Profile",
    ) -> None:
        self.height = float(height)
        self.width = float(width)
        self.web_thickness = float(web_thickness)
        self.flange_thickness = float(flange_thickness)
        self.anchor = anchor.lower()
        self.name = name
        self._validate()

    def _validate(self) -> None:
        if self.height <= 0:
            raise ValueError("height must be positive")
        if self.width <= 0:
            raise ValueError("width must be positive")
        if self.web_thickness <= 0 or self.web_thickness >= self.width:
            raise ValueError("web_thickness must be > 0 and < width")
        if self.flange_thickness <= 0 or self.flange_thickness * 2 >= self.height:
            raise ValueError("flange_thickness must be > 0 and < height/2")
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
    def web_height(self) -> float:
        """Clear height between flanges."""
        return self.height - 2 * self.flange_thickness

    @property
    def area(self) -> float:
        return (
            2 * self.width * self.flange_thickness
            + self.web_height * self.web_thickness
        )

    @property
    def centroid_z(self) -> float:
        """Z coordinate of centroid measured from bottom of profile (anchor-independent)."""
        return self.height / 2  # symmetric section

    # ------------------------------------------------------------------
    # Profile points
    # ------------------------------------------------------------------

    def get_profile_points(self) -> List[Tuple[float, float]]:
        """
        Return 12 (y, z) points defining the closed I-section in the local YZ plane.
        The closing duplicate is NOT included; profile_from_points() adds it automatically.

        Point order (counter-clockwise from bottom-left):

             8---7
             |   |     ← top flange
            9|   |6
             |   |     ← web
           10|   |5
             |   |     ← bottom flange
             1---4
             0   3  ← anchor-offset origin
        """
        oy, oz = self._origin_offset()
        # negate so that anchor='s' places origin at mid-bottom
        oy = -oy
        oz = -oz

        h  = self.height
        w  = self.width
        tf = self.flange_thickness
        tw = self.web_thickness

        hw  = w  / 2
        htw = tw / 2

        return [
            (-hw,       oz        ),   # 0  bottom-left  outer flange
            ( hw,       oz        ),   # 1  bottom-right outer flange
            ( hw,       oz + tf   ),   # 2  bottom-right inner flange
            ( htw,      oz + tf   ),   # 3  web bottom-right
            ( htw,      oz + h-tf ),   # 4  web top-right
            ( hw,       oz + h-tf ),   # 5  top-right inner flange
            ( hw,       oz + h    ),   # 6  top-right outer flange
            (-hw,       oz + h    ),   # 7  top-left  outer flange
            (-hw,       oz + h-tf ),   # 8  top-left  inner flange
            (-htw,      oz + h-tf ),   # 9  web top-left
            (-htw,      oz + tf   ),   # 10 web bottom-left
            (-hw,       oz + tf   ),   # 11 bottom-left inner flange
        ]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "height": self.height,
            "width": self.width,
            "web_thickness": self.web_thickness,
            "flange_thickness": self.flange_thickness,
            "anchor": self.anchor,
            "area": self.area,
            "centroid_z": self.centroid_z,
        }
