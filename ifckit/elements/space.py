"""
ifckit.elements.space
=====================

Pending space element: PendingSpace.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ifckit.elements.base import PendingElement
from ifckit.elements.style import RenderStyle
from ifckit.geometry import Vec


class PendingSpace(PendingElement):
    """
    A space defined by a closed footprint polyline and an extrusion height.

    Corresponds to ``IfcSpace`` in the IFC schema.  The footprint is expressed
    in world XY coordinates; the height is the clear room height above the
    storey floor level.

    Args:
        footprint:    List of Vec points forming a closed (or implicitly closed)
                      polygon in world XY.
        height:       Clear height of the space (metres or document units).
        name:         Space number / identifier (e.g. ``"1.01"``).
                      Used as ``IfcSpace.Name``.
        long_name:    Descriptive room name (e.g. ``"Meeting Room"``).
                      Used as ``IfcSpace.LongName``.
        predefined_type: IFC ``PredefinedType`` string — one of ``"SPACE"``,
                      ``"PARKING"``, ``"GFA"``, ``"INTERNAL"``,
                      ``"EXTERNAL"``.  Defaults to ``"SPACE"``.
        style:        Optional ``RenderStyle`` (colour) applied to the space.
        hatch_pattern: Rhino hatch pattern name for SVG import
                      (e.g. ``"ANSI31"``).
    """

    element_type = "basic_space"

    def __init__(
        self,
        footprint: List[Vec],
        height: float,
        name: str = "",
        long_name: str = "",
        predefined_type: str = "SPACE",
        style: Optional[RenderStyle] = None,
        hatch_pattern: str = "",
    ) -> None:
        super().__init__(name=name, style=style, hatch_pattern=hatch_pattern)
        self.footprint = list(footprint)
        self.height = float(height)
        self.long_name = long_name
        self.predefined_type = predefined_type

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        d = super().to_dict()
        d["footprint"] = [p.to_tuple() for p in self.footprint]
        d["height"] = self.height
        if self.long_name:
            d["long_name"] = self.long_name
        if self.predefined_type != "SPACE":
            d["predefined_type"] = self.predefined_type
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingSpace":
        """Deserialize from a dict."""
        footprint = [Vec(*pt) for pt in cls._require(d, "footprint")]
        height = cls._require(d, "height")
        return cls(
            footprint=footprint,
            height=height,
            name=d.get("name", ""),
            long_name=d.get("long_name", ""),
            predefined_type=d.get("predefined_type", "SPACE"),
            style=cls._style_from_dict(d),
            hatch_pattern=cls._hatch_pattern_from_dict(d),
        )
