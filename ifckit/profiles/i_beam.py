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

from ifckit.profiles.anchor import VALID_ANCHORS
from ifckit.profiles.base import Profile

if TYPE_CHECKING:
    import ifcopenshell

# Anchor → extra (dx, dy) shift applied on top of the inherent x-centring
# of the I-section profile points.  (0, 0) = bottom-centre of bounding box.
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
        rotation: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        self.height = float(height)
        self.width = float(width)
        self.web_thickness = float(web_thickness)
        self.flange_thickness = float(flange_thickness)
        self.anchor = anchor.lower()
        self.name = name
        self._validate()
        self._init_transform(rotation, offset_x, offset_y)

    def _validate(self) -> None:
        if self.height <= 0:
            raise ValueError("height must be positive")
        if self.width <= 0:
            raise ValueError("width must be positive")
        if self.web_thickness <= 0 or self.web_thickness >= self.width:
            raise ValueError("web_thickness must be > 0 and < width")
        if self.flange_thickness <= 0 or self.flange_thickness * 2 >= self.height:
            raise ValueError("flange_thickness must be > 0 and < height/2")
        if self.anchor not in VALID_ANCHORS:
            raise ValueError(f"anchor must be one of {sorted(VALID_ANCHORS)}, got '{self.anchor}'")

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
        """
        ox, oy = self._origin_offset()
        ox = -ox
        oy = -oy

        h = self.height
        w = self.width
        tf = self.flange_thickness
        tw = self.web_thickness

        hw = w / 2
        htw = tw / 2

        pts = [
            (ox - hw, oy),
            (ox + hw, oy),
            (ox + hw, oy + tf),
            (ox + htw, oy + tf),
            (ox + htw, oy + h - tf),
            (ox + hw, oy + h - tf),
            (ox + hw, oy + h),
            (ox - hw, oy + h),
            (ox - hw, oy + h - tf),
            (ox - htw, oy + h - tf),
            (ox - htw, oy + tf),
            (ox - hw, oy + tf),
        ]
        return self._apply_transform(pts)

    profile_type = "i_beam"

    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        """
        Emit ``IfcIShapeProfileDef`` (native IFC parametric I-section).

        The anchor offset and user rotation/offset are combined in the
        IfcAxis2Placement2D via ``_ifc_placement_2d()``.
        """
        ox, oy = self._origin_offset()
        # IfcIShapeProfileDef centroid is at bounding-box centre.
        # Anchor offset moves the local origin relative to that centroid.
        anchor_x = -ox
        anchor_y = -oy + self.height / 2
        pos = self._ifc_placement_2d(ifc_file, anchor_x=anchor_x, anchor_y=anchor_y)
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
            **self._transform_dict(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "IBeamProfile":
        r, ox, oy = cls._transform_from_dict(d)
        return cls(
            height=d["height"],
            width=d["width"],
            web_thickness=d["web_thickness"],
            flange_thickness=d["flange_thickness"],
            anchor=d.get("anchor", "s"),
            name=d.get("name", "I-Profile"),
            rotation=r,
            offset_x=ox,
            offset_y=oy,
        )
