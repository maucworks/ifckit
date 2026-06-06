"""
ifckit.elements.wall_graph
=========================

PendingWallGraph: a wall graph defined by vertices + edges, or by a
Path.  Path-based walls use offset geometry (single extrusion, no
boolean tree).  Edge-based walls (with T/X junctions) use Shapely
buffer geometry (single extrusion, no boolean tree).
"""

from __future__ import annotations

from typing import Optional

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
        vertices:     3D positions (edge mode).
        edges:        Edge index pairs (edge mode).
        path:         Continuous centerline Path (path mode).
        plane:        Placement plane (Z = up).  Defaults to path._plane.
        thickness:    Wall thickness (mm).
        height:       Wall height (mm).
        offset_left:  Offset left of the path direction (mm).  ``None`` → ``thickness / 2``.
        offset_right: Offset right of the path direction (mm).  ``None`` → ``thickness / 2``.
        name:         Element name.
        style:        Optional RenderStyle.
        properties:   Optional UserProperties dict.
        angle_step_deg: Arc sampling resolution (default 5°).
    """

    element_type = "wall_graph"

    def __init__(
        self,
        vertices: Optional[list[Vec]] = None,
        edges: Optional[list[tuple[int, int]]] = None,
        path: Optional[Path] = None,
        plane: Optional[Plane] = None,
        thickness: float = 200,
        height: float = 3000,
        offset_left: Optional[float] = None,
        offset_right: Optional[float] = None,
        name: str = "",
        style: Optional[RenderStyle] = None,
        properties: Optional[UserProperties] = None,
        angle_step_deg: float = 5.0,
    ) -> None:
        super().__init__(name=name, style=style, properties=properties)
        self.offset_left = float(offset_left) if offset_left is not None else None
        self.offset_right = float(offset_right) if offset_right is not None else None
        if offset_left is not None and offset_right is not None:
            self.thickness = float(offset_left + offset_right)
        elif offset_left is not None:
            self.thickness = float(thickness)
            self.offset_right = float(thickness - offset_left)
        elif offset_right is not None:
            self.thickness = float(thickness)
            self.offset_left = float(thickness - offset_right)
        else:
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

    @property
    def path(self) -> Optional[Path]:
        """The Path in path-mode, or None in edge-mode."""
        return self._path if self.from_path else None

    @property
    def offset_pair(self) -> tuple[float, float]:
        """Return ``(offset_left, offset_right)``, falling back to ``thickness / 2``."""
        left = self.offset_left if self.offset_left is not None else self.thickness / 2
        right = self.offset_right if self.offset_right is not None else self.thickness / 2
        return left, right

    def to_dict(self) -> dict:
        d = super().to_dict()
        if self.from_path and self._path is not None:
            d["mode"] = "path"
            d["path"] = self._path.to_dict()
            d["angle_step_deg"] = self.angle_step_deg
        else:
            d["mode"] = "edge"
            d["vertices"] = [(v.x, v.y, v.z) for v in self.vertices]
            d["edges"] = self.edges
            d["plane"] = self.plane.to_dict() if hasattr(self.plane, "to_dict") else {}
        d.update(
            {
                "thickness": self.thickness,
                "height": self.height,
            }
        )
        if self.offset_left is not None:
            d["offset_left"] = self.offset_left
        if self.offset_right is not None:
            d["offset_right"] = self.offset_right
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PendingWallGraph":
        kwargs = dict(
            thickness=float(d.get("thickness", 200)),
            height=float(d.get("height", 3000)),
            name=d.get("name", ""),
            offset_left=float(d["offset_left"]) if "offset_left" in d else None,
            offset_right=float(d["offset_right"]) if "offset_right" in d else None,
        )
        if d.get("mode") == "path":
            from ifckit.geometry.path import Path as _Path

            return cls(
                path=_Path.from_dict(d["path"]),
                angle_step_deg=float(d.get("angle_step_deg", 5.0)),
                **kwargs,
            )

        # Fallback: edge mode (backward compat)
        verts = [Vec(*p) for p in d.get("vertices", [])]
        edges = [(int(a), int(b)) for a, b in d.get("edges", [])]
        plane = Plane.from_dict(d.get("plane", {}))
        return cls(vertices=verts, edges=edges, plane=plane, **kwargs)
