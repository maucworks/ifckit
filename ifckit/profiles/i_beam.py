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

Points are returned in the local XY plane (X = horizontal, Y = vertical),
suitable for use as a PendingBeam / PendingColumn profile in ifckit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from ifckit.profiles.base import Profile

if TYPE_CHECKING:
    import ifcopenshell

# Anchor → (x_fraction_of_width, y_fraction_of_height)
# Applied as: offset = (-fraction * width, -fraction * height)
_ANCHOR_OFFSETS: dict[str, Tuple[float, float]] = {
    "sw": (-0.5, 0.0),
    "s": (0.0, 0.0),
    "se": (0.5, 0.0),
    "w": (-0.5, 0.5),
    "c": (0.0, 0.5),
    "e": (0.5, 0.5),
    "nw": (-0.5, 1.0),
    "n": (0.0, 1.0),
    "ne": (0.5, 1.0),
}


class IBeamProfile(Profile):
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
        anchor: str = "s",
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
        return 2 * self.width * self.flange_thickness + self.web_height * self.web_thickness

    @property
    def centroid_z(self) -> float:
        """Z coordinate of centroid measured from bottom of profile (anchor-independent)."""
        return self.height / 2  # symmetric section

    # ------------------------------------------------------------------
    # Profile points
    # ------------------------------------------------------------------

    def get_profile_points(self) -> List[Tuple[float, float]]:
        """
        Return 12 (x, y) points defining the closed I-section in the local XY plane.
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
        ox, oy = self._origin_offset()
        # negate so that anchor='s' places origin at mid-bottom
        ox = -ox
        oy = -oy

        h = self.height
        w = self.width
        tf = self.flange_thickness
        tw = self.web_thickness

        hw = w / 2
        htw = tw / 2

        return [
            (ox - hw, oy),  # 0  bottom-left  outer flange
            (ox + hw, oy),  # 1  bottom-right outer flange
            (ox + hw, oy + tf),  # 2  bottom-right inner flange
            (ox + htw, oy + tf),  # 3  web bottom-right
            (ox + htw, oy + h - tf),  # 4  web top-right
            (ox + hw, oy + h - tf),  # 5  top-right inner flange
            (ox + hw, oy + h),  # 6  top-right outer flange
            (ox - hw, oy + h),  # 7  top-left  outer flange
            (ox - hw, oy + h - tf),  # 8  top-left  inner flange
            (ox - htw, oy + h - tf),  # 9  web top-left
            (ox - htw, oy + tf),  # 10 web bottom-left
            (ox - hw, oy + tf),  # 11 bottom-left inner flange
        ]

    profile_type = "i_beam"

    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        """
        Emit ``IfcIShapeProfileDef`` (native IFC parametric I-section).

        The 2D position is centred at the anchor origin.
        """
        ox, oy = self._origin_offset()
        # IfcIShapeProfileDef is symmetric: centre of bounding box = centroid
        # We place the 2D position at the anchor offset so the origin is correct.
        pos = ifc_file.create_entity(
            "IfcAxis2Placement2D",
            Location=ifc_file.create_entity(
                "IfcCartesianPoint", Coordinates=[-ox, -oy + self.height / 2]
            ),
        )
        return ifc_file.create_entity(
            "IfcIShapeProfileDef",
            ProfileType="AREA",
            ProfileName=self.name,
            Position=pos,
            OverallWidth=self.width,
            OverallDepth=self.height,
            WebThickness=self.web_thickness,
            FlangeThickness=self.flange_thickness,
            FilletRadius=None,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_type": self.profile_type,
            "name": self.name,
            "height": self.height,
            "width": self.width,
            "web_thickness": self.web_thickness,
            "flange_thickness": self.flange_thickness,
            "anchor": self.anchor,
            "area": self.area,
            "centroid_z": self.centroid_z,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "IBeamProfile":
        return cls(
            height=d["height"],
            width=d["width"],
            web_thickness=d["web_thickness"],
            flange_thickness=d["flange_thickness"],
            anchor=d.get("anchor", "s"),
            name=d.get("name", "I-Profile"),
        )
