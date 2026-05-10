"""
ifckit.elements.wall_graph
=========================

PendingWallGraph: a wall graph defined by vertices + edges, or by a
Path.  Path-based walls use offset geometry (single extrusion, no
boolean tree).  Edge-based walls (with T/X junctions) use Shapely
buffer geometry (single extrusion, no boolean tree).
"""

from __future__ import annotations

from ifckit.elements.base import PendingElement, UserProperties
from ifckit.elements.style import RenderStyle
from ifckit.geometry import Path, Plane, Vec


class PendingWallGraph(PendingElement):
    """
    A wall defined by a graph of edges or a continuous Path.

    **Path mode** (``path`` argument):
        The wall centerline follows the Path.  The footprint is created
        by offsetting the Path outward/inward by ``thickness / 2``.
        Closed paths produce a single ``IfcExtrudedAreaSolid`` with a
        void (no boolean tree).  Open paths produce a single
        ``IfcExtrudedAreaSolid`` with a mitered-corner footprint computed
        by offsetting both sides of the centerline.

    **Edge mode** (``vertices + edges``):
        Edges are buffered via Shapely into a single closed polygon and
        extruded as one ``IfcExtrudedAreaSolid``.  Supports T-junctions
        and X-junctions with correct shoulder fill at branching vertices.

    Args:
        vertices:   3D positions (edge mode).
        edges:      Edge index pairs (edge mode).
        path:       Continuous centerline Path (path mode).
        plane:      Placement plane (Z = up).  Defaults to path._plane.
        thickness:  Wall thickness (mm).
        height:     Wall height (mm).
        name:       Element name.
        style:      Optional RenderStyle.
        properties: Optional UserProperties dict.
        angle_step_deg: Arc sampling resolution (default 5°).
    """

    element_type = "wall_graph"

    def __init__(
        self,
        vertices: list[Vec] | None = None,
        edges: list[tuple[int, int]] | None = None,
        path: Path | None = None,
        plane: Plane | None = None,
        thickness: float = 200,
        height: float = 3000,
        name: str = "",
        style: RenderStyle | None = None,
        properties: UserProperties | None = None,
        angle_step_deg: float = 5.0,
    ) -> None:
        super().__init__(name=name, style=style, properties=properties)
        self.thickness = float(thickness)
        self.height = float(height)
        self.angle_step_deg = float(angle_step_deg)

        if path is not None:
            self._path = path
            self.plane = (
                plane
                if plane is not None
                else (
                    path._plane if path._plane else Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
                )
            )
            self.from_path = True
            # sampled vertices + edges for backward compat (used in previews etc.)
            pts = path.sample(angle_step_deg).points
            self.vertices = pts
            self.edges = [(i, i + 1) for i in range(len(pts) - 1)]
            if path.is_closed and len(pts) > 1:
                self.edges.append((len(pts) - 1, 0))
        else:
            self.vertices = list(vertices) if vertices else []
            self.edges = list(edges) if edges else []
            if plane is None:
                raise ValueError("PendingWallGraph requires a plane in edge mode")
            self.plane = plane
            self.from_path = False

    def to_dict(self) -> dict:
        d = super().to_dict()  # includes "type", "name", style, hatch_pattern, properties
        if self.from_path:
            raise NotImplementedError(
                "PendingWallGraph in path mode cannot be serialised to dict: "
                "the original Path segments are not preserved. "
                "Construct the element from a dict in edge mode, or implement "
                "path serialisation before calling to_dict()."
            )
        d.update(
            {
                "vertices": [
                    (v.to_dict() if hasattr(v, "to_dict") else (v.x, v.y, v.z))
                    for v in self.vertices
                ],
                "edges": self.edges,
                "plane": self.plane.to_dict() if hasattr(self.plane, "to_dict") else {},
                "thickness": self.thickness,
                "height": self.height,
            }
        )
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PendingWallGraph":
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
