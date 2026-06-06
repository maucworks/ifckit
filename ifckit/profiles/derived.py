"""
DerivedProfile — Profile derived by transformation from a parent profile.

IfcDerivedProfileDef wraps a parent profile with a 2D transformation
(translation, rotation, mirroring, scaling).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Dict, Optional

from ifckit.profiles.base import Profile

if TYPE_CHECKING:
    import ifcopenshell


class DerivedProfile(Profile):
    """Profile derived by transformation from a parent.

    Wraps a parent profile and applies a 2D transformation:
    - translation (x, y offset)
    - rotation (degrees)
    - scaling (uniform or x/y separately)
    - mirroring (via negative scale)

    Examples::

        # Scale a rectangle by 2x
        base = RectangleProfile(100, 50)
        derived = DerivedProfile(base, scale=2.0)

        # Rotate 45°
        derived = DerivedProfile(base, rotation=45)

        # Mirror (via negative scale)
        derived = DerivedProfile(base, scale_x=-1)

        # Non-uniform scale
        derived = DerivedProfile(base, scale_x=1.5, scale_y=0.8)

        # Combined
        derived = DerivedProfile(base, offset_x=50, rotation=15, scale=1.2)
    """

    profile_type = "derived"  # Auto-registered by metaclass

    def __init__(
        self,
        parent: Profile,
        *,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
        rotation: float = 0.0,
        scale: float = 1.0,
        scale_x: Optional[float] = None,
        scale_y: Optional[float] = None,
    ):
        self.parent = parent
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.rotation = rotation  # degrees
        self.scale = scale
        self.scale_x = scale_x
        self.scale_y = scale_y
        super().__init__()

    def get_profile_points(self):
        """Apply this derived transform to the parent's outline points."""
        import math as _math

        pts = self.parent.get_profile_points()
        sx = self.scale_x if self.scale_x is not None else self.scale
        sy = self.scale_y if self.scale_y is not None else self.scale
        rad = _math.radians(self.rotation)
        c = _math.cos(rad)
        s = _math.sin(rad)
        result = []
        for x, y in pts:
            xs, ys = x * sx, y * sy
            xr = c * xs - s * ys + self.offset_x
            yr = s * xs + c * ys + self.offset_y
            result.append((xr, yr))
        return result

    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        """Create IfcDerivedProfileDef."""
        # Create parent profile entity
        parent_ifc = self.parent.to_ifc(ifc_file)

        # Build transformation operator
        c = math.cos(math.radians(self.rotation))
        s = math.sin(math.radians(self.rotation))

        # Non-uniform scale values
        sx = self.scale_x if self.scale_x is not None else self.scale
        sy = self.scale_y if self.scale_y is not None else self.scale

        # IfcCartesianTransformationOperator2D
        # If only mirroring: use negative scale (but IfcMirroredProfileDef is preferred)
        if sx < 0:
            axis1 = ifc_file.create_entity(
                "IfcDirection", DirectionRatios=[-c, -s] if self.rotation != 0 else [-1.0, 0.0]
            )
        else:
            axis1 = None  # defaults to (1,0)

        if sy < 0:
            axis2 = ifc_file.create_entity("IfcDirection", DirectionRatios=[0.0, -1.0])
        else:
            axis2 = None  # defaults to (0,1)

        # Local origin (translation)
        location = ifc_file.create_entity(
            "IfcCartesianPoint", Coordinates=[self.offset_x, self.offset_y]
        )

        # Build the operator directly — no intermediate entity.
        if self.scale_x is not None or self.scale_y is not None:
            sx = self.scale_x if self.scale_x is not None else self.scale
            sy = self.scale_y if self.scale_y is not None else self.scale
            operator = ifc_file.create_entity(
                "IfcCartesianTransformationOperator2DnonUniform",
                Axis1=axis1,
                Axis2=axis2,
                LocalOrigin=location,
                Scale=sx,
                Scale2=sy,
            )
        else:
            operator = ifc_file.create_entity(
                "IfcCartesianTransformationOperator2D",
                Axis1=axis1,
                Axis2=axis2,
                LocalOrigin=location,
                Scale=self.scale,
            )

        return ifc_file.create_entity(
            "IfcDerivedProfileDef",
            ParentProfile=parent_ifc,
            Operator=operator,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_type": "derived",
            "parent": self.parent.to_dict(),
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "rotation": self.rotation,
            "scale": self.scale,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> DerivedProfile:
        parent = Profile.dispatch_from_dict(d["parent"])
        return cls(
            parent,
            offset_x=d.get("offset_x", 0.0),
            offset_y=d.get("offset_y", 0.0),
            rotation=d.get("rotation", 0.0),
            scale=d.get("scale", 1.0),
            scale_x=d.get("scale_x"),
            scale_y=d.get("scale_y"),
        )
