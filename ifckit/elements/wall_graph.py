"""
ifckit.elements.wall_graph
=========================

PendingWallGraph: a wall graph defined by vertices, edges, thickness,
and height.  The edges form an open graph (L, T, X junctions, …).
Each edge is extruded separately and boolean-union'd into one IfcWall.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ifckit.elements.base import PendingElement, UserProperties
from ifckit.elements.style import RenderStyle
from ifckit.geometry import Plane, Vec


class PendingWallGraph(PendingElement):
    """
    A wall defined by a graph of edges.

    Each edge ``(vi, vj)`` produces extruded rectangle of size
    ``thickness × edge_length``, swept upward by ``height``.  All
    extrusions are then boolean-union'd into a single IfcWall.

    Args:
        vertices:  3D positions of the wall vertices (Z = 0 recommended).
        edges:     List of (i, j) tuples connecting vertices.
        plane:     Placement plane (Z = up, X = reference direction).
        thickness: Wall thickness (mm).
        height:    Wall height (mm).
        name:      Element name.
        style:     Optional RenderStyle.
        properties: Optional UserProperties dict.
    """

    element_type = "wall_graph"

    def __init__(
        self,
        vertices: List[Vec],
        edges: List[Tuple[int, int]],
        plane: Plane,
        thickness: float,
        height: float,
        name: str = "",
        style: Optional[RenderStyle] = None,
        properties: Optional[UserProperties] = None,
    ) -> None:
        super().__init__(name=name, style=style, properties=properties)
        self.vertices = list(vertices)
        self.edges = list(edges)
        self.plane = plane
        self.thickness = float(thickness)
        self.height = float(height)

    def to_dict(self) -> Dict:
        d: Dict = {
            "vertices": [
                v.to_dict() if hasattr(v, "to_dict") else (v.x, v.y, v.z) for v in self.vertices
            ],
            "edges": self.edges,
            "plane": self.plane.to_dict() if hasattr(self.plane, "to_dict") else {},
            "thickness": self.thickness,
            "height": self.height,
        }
        if self.name:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> "PendingWallGraph":
        verts = [Vec(*p) for p in d.get("vertices", [])]
        edges = [(int(a), int(b)) for a, b in d.get("edges", [])]
        plane = Plane.from_dict(d.get("plane", {}))
        return cls(
            vertices=verts,
            edges=edges,
            plane=plane,
            thickness=float(d.get("thickness", 200)),
            height=float(d.get("height", 3000)),
            name=d.get("name", ""),
        )
