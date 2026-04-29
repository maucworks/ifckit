"""
ifckit.elements.building
========================

Pending building elements: PendingWall, PendingSlab.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ifckit.elements.base import ClipData, PendingElement
from ifckit.geometry import Plane, Vec


class PendingWall(PendingElement):
    """
    A wall defined by a closed footprint polyline, a placement plane,
    and an extrusion height.

    Args:
        footprint:  List of Vec points forming a closed (or implicitly closed)
                    polygon in the local XY plane.
        plane:      Placement plane (defines position and orientation in world).
        height:     Extrusion height along plane.z_axis (metres).
        name:       Element name (used as IfcWall.Name).
        clip_data:  Optional clip plane data for boolean trimming.
    """

    element_type = "basic_wall"

    def __init__(
        self,
        footprint: List[Vec],
        plane: Plane,
        height: float,
        name: str = "",
        clip_data: Optional[ClipData] = None,
    ) -> None:
        super().__init__(name=name, clip_data=clip_data)
        self.footprint = list(footprint)
        self.plane = plane
        self.height = float(height)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["footprint"] = [p.to_tuple() for p in self.footprint]
        d["height"] = self.height
        d["plane"] = self.plane.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingWall":
        footprint = [Vec(*pt) for pt in cls._require(d, "footprint")]
        height = cls._require(d, "height")
        plane = Plane.from_dict(d["plane"]) if "plane" in d else Plane.world_xy()
        return cls(
            footprint=footprint,
            plane=plane,
            height=height,
            name=d.get("name", ""),
            clip_data=d.get("clip_data"),
        )


class PendingSlab(PendingElement):
    """
    A slab defined by a closed footprint polyline, a placement plane,
    and a thickness.

    Args:
        footprint:  List of Vec points.
        plane:      Placement plane.
        thickness:  Extrusion thickness along plane.z_axis (metres).
        name:       Element name.
        clip_data:  Optional clip plane data.
    """

    element_type = "basic_slab"

    def __init__(
        self,
        footprint: List[Vec],
        plane: Plane,
        thickness: float,
        name: str = "",
        clip_data: Optional[ClipData] = None,
    ) -> None:
        super().__init__(name=name, clip_data=clip_data)
        self.footprint = list(footprint)
        self.plane = plane
        self.thickness = float(thickness)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["footprint"] = [p.to_tuple() for p in self.footprint]
        d["thickness"] = self.thickness
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingSlab":
        """
        Deserialize from dict.

        Note: Plane is not serialised. Deserialised instances always use world XY plane.
        """
        footprint = [Vec(*pt) for pt in cls._require(d, "footprint")]
        thickness = cls._require(d, "thickness")
        return cls(
            footprint=footprint,
            plane=Plane.world_xy(),
            thickness=thickness,
            name=d.get("name", ""),
            clip_data=d.get("clip_data"),
        )
