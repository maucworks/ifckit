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

Points are returned as (x, y) tuples in the local XY plane (X = horizontal,
Y = vertical), consistent with IBeamProfile and the profile coordinate system
used throughout ifckit builders (``_coerce_profile`` maps the first tuple value
to X, the second to Y).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from ifckit.profiles.base import Profile

if TYPE_CHECKING:
    import ifcopenshell

# Anchor → (x_fraction_of_width, y_fraction_of_height)
_ANCHOR_OFFSETS: dict[str, Tuple[float, float]] = {
    "sw": (0.0, 0.0),
    "s": (-0.5, 0.0),
    "se": (-1.0, 0.0),
    "w": (0.0, -0.5),
    "c": (-0.5, -0.5),
    "e": (-1.0, -0.5),
    "nw": (0.0, -1.0),
    "n": (-0.5, -1.0),
    "ne": (-1.0, -1.0),
}


class LBeamProfile(Profile):
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
        anchor: str = "sw",
        name: str = "L-Profile",
        rotation: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        self.height = float(height)
        self.width = float(width)
        self.thickness = float(thickness)
        self.anchor = anchor.lower()
        self.name = name
        self._validate()
        self._init_transform(rotation, offset_x, offset_y)

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
        return self.width * self.thickness + (self.height - self.thickness) * self.thickness

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
        Return 6 (x, y) points defining the closed L-section in the local XY plane.
        """
        oy, oz = self._origin_offset()

        h = self.height
        w = self.width
        t = self.thickness

        pts = [
            (oy, oz),
            (oy + w, oz),
            (oy + w, oz + t),
            (oy + t, oz + t),
            (oy + t, oz + h),
            (oy, oz + h),
        ]
        return self._apply_transform(pts)

    profile_type = "l_beam"

    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        """
        Emit ``IfcLShapeProfileDef`` (native IFC parametric L-section).

        Anchor offset and user rotation/offset combined via ``_ifc_placement_2d()``.
        """
        ox, oy = self._origin_offset()
        pos = self._ifc_placement_2d(ifc_file, anchor_x=ox, anchor_y=oy)
        return ifc_file.create_entity(
            "IfcLShapeProfileDef",
            ProfileType="AREA",
            ProfileName=self.name,
            Position=pos,
            Depth=self.height,
            Width=self.width,
            Thickness=self.thickness,
            FilletRadius=None,
            EdgeRadius=None,
            LegSlope=None,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_type": self.profile_type,
            "name": self.name,
            "height": self.height,
            "width": self.width,
            "thickness": self.thickness,
            "anchor": self.anchor,
            "area": self.area,
            "centroid_y": self.centroid_y,
            "centroid_z": self.centroid_z,
            **self._transform_dict(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LBeamProfile":
        r, ox, oy = cls._transform_from_dict(d)
        return cls(
            height=d["height"],
            width=d["width"],
            thickness=d["thickness"],
            anchor=d.get("anchor", "sw"),
            name=d.get("name", "L-Profile"),
            rotation=r,
            offset_x=ox,
            offset_y=oy,
        )
