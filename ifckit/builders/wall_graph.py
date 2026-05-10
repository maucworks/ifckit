"""
ifckit.builders.wall_graph
==========================

WallGraphBuilder: PendingWallGraph -> IfcWall.

- **Path mode (closed):**  offsets the centerline outward/inward by
  ``thickness / 2`` and creates a single ``IfcExtrudedAreaSolid``
  with a void — a clean SweptSolid, no boolean tree.
- **Path mode (open):**  samples the path to a polyline, offsets
  left/right, intersects for mitered corners, extrudes single solid.
- **Graph mode (edge mode):**  buffers all edges as a Shapely
  MultiLineString by ``thickness / 2`` — handles T/X mitering and
  capped open ends automatically — producing a single closed polygon
  extruded as one ``IfcExtrudedAreaSolid`` with optional holes.
"""

from __future__ import annotations

import math
import warnings

import ifcopenshell
import ifcopenshell.api

from ifckit.builders._geom import (
    _signed_area_2d,
    axis2placement3d,
    extrude_profile,
    local_placement,
    product_definition_shape,
    profile_from_points,
    shape_representation,
    shapely_polygon_to_ifc_profile,
)
from ifckit.builders.base import BaseBuilder
from ifckit.builders.psets import write_psets
from ifckit.elements.base import PendingElement
from ifckit.geometry import Vec
from ifckit.geometry.path import _line_line_intersect_2d

try:
    from shapely.geometry import LineString, MultiPolygon, Polygon
    from shapely.ops import unary_union

    _SHAPELY_AVAILABLE = True
except ImportError:
    _SHAPELY_AVAILABLE = False


def _junction_fill(
    jx: float,
    jy: float,
    arm_directions: list[tuple[float, float]],
    half_t: float,
) -> "Polygon":
    """Convex hull of ht-offset shoulder points for all arms.

    For each arm direction (dx, dy) away from the junction,
    compute the two perpendicular shoulder points at distance
    half_t.  The convex hull of all shoulders (plus the junction
    centre) fills the corner without rounding.
    """
    shoulders: list[tuple[float, float]] = [(jx, jy)]
    for dx, dy in arm_directions:
        L = math.hypot(dx, dy)
        if L < 1e-12:
            continue
        ux, uy = dx / L, dy / L
        px, py = -uy, ux  # perpendicular (left)
        shoulders.append((jx + px * half_t, jy + py * half_t))
        shoulders.append((jx - px * half_t, jy - py * half_t))
    return Polygon(shoulders).convex_hull


def _miter_offset_segments(
    segs: list[tuple[Vec, Vec]],
    end_pt: Vec,
) -> list[Vec]:
    """Intersect consecutive offset segments for mitered corners.

    Args:
        segs:    List of (anchor_point, direction) pairs, one per segment.
        end_pt:  The final cap point of the last segment.

    Returns:
        List of corner points forming one side of the wall footprint.
    """
    if not segs:
        return []
    result: list[Vec] = [segs[0][0]]
    for i in range(1, len(segs)):
        p1, d1 = segs[i - 1]
        p2, d2 = segs[i]
        ip = _line_line_intersect_2d(p1, d1, p2, d2)
        result.append(ip if ip is not None else p2)
    result.append(end_pt)
    return result


class WallGraphBuilder(BaseBuilder):
    """Builds an IfcWall from a PendingWallGraph."""

    entity_type = "wall_graph"

    def _create_geometry(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        if not hasattr(pending, "element_type") or pending.element_type != "wall_graph":
            raise TypeError(
                f"WallGraphBuilder expects PendingWallGraph, got {type(pending).__name__}"
            )

        if getattr(pending, "from_path", False):
            if pending._path.is_closed:
                try:
                    geometry, rep_type = self._build_from_path(ifc_file, pending)
                except ValueError as exc:
                    warnings.warn(
                        f"WallGraph: closed-path offset failed ({exc}); "
                        "falling back to open-path extrusion.",
                        stacklevel=2,
                    )
                    geometry, rep_type = self._build_from_open_path(ifc_file, pending)
            else:
                geometry, rep_type = self._build_from_open_path(ifc_file, pending)
        else:
            geometry, rep_type = self._build_from_graph_offset(ifc_file, pending)

        shape_rep = shape_representation(ifc_file, context, geometry, rep_type=rep_type)
        prod_rep = product_definition_shape(ifc_file, shape_rep)

        wall = ifcopenshell.api.run(
            "root.create_entity", ifc_file, ifc_class="IfcWall", name=pending.name
        )
        wall.Representation = prod_rep
        wall.ObjectPlacement = local_placement(
            ifc_file, pending.plane, relative_to=container.ObjectPlacement
        )
        ifcopenshell.api.run(
            "spatial.assign_container",
            ifc_file,
            products=[wall],
            relating_structure=container,
        )
        write_psets(ifc_file, wall, pending)
        return wall

    # ── Path mode (closed) ──────────────────────────────────────────

    @staticmethod
    def _build_from_path(
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
    ) -> tuple[ifcopenshell.entity_instance, str]:
        """Offset centerline outward/inward → one ExtrudedAreaSolid with void."""
        ht = pending.thickness / 2
        path = pending._path

        outer = path.offset(-ht)
        inner = path.offset(+ht)

        oa = abs(_signed_area_2d(outer.to_profile_points(plane=pending.plane)))
        ia = abs(_signed_area_2d(inner.to_profile_points(plane=pending.plane)))
        if ia > oa:
            outer, inner = inner, outer

        outer = outer.with_hole(inner)
        profile = profile_from_points(ifc_file, outer)
        pos = axis2placement3d(ifc_file, Vec(0, 0, 0), pending.plane.z_axis, pending.plane.x_axis)
        solid = extrude_profile(ifc_file, profile, pending.height, position=pos)
        return solid, "SweptSolid"

    # ── Path mode (open) ────────────────────────────────────────────

    @staticmethod
    def _build_from_open_path(
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
    ) -> tuple[ifcopenshell.entity_instance, str]:
        """Offset open centerline left/right → closed footprint → one extrusion."""
        pts = pending.vertices  # already sampled in __init__
        n = len(pts)
        if n < 2:
            raise ValueError("open-path wall needs at least 2 points")

        ht = pending.thickness / 2
        normal = pending.plane.z_axis

        # Shifted segment anchors and directions (left side = +perp, right = -perp)
        left_segs: list[tuple[Vec, Vec]] = []
        right_segs: list[tuple[Vec, Vec]] = []
        for i in range(n - 1):
            d = (pts[i + 1] - pts[i]).normalized()
            perp = d**normal
            left_segs.append((pts[i] + perp * ht, d))
            right_segs.append((pts[i] - perp * ht, d))

        # Last segment's end anchor
        d_last = (pts[-1] - pts[-2]).normalized()
        perp_last = d_last**normal
        left_end = pts[-1] + perp_last * ht
        right_end = pts[-1] - perp_last * ht

        # Intersect consecutive offset segments for mitered corners
        left_pts = _miter_offset_segments(left_segs, left_end)
        right_pts = _miter_offset_segments(right_segs, right_end)

        # Closed footprint: left polyline + right polyline reversed
        footprint = left_pts + right_pts[::-1]

        profile = profile_from_points(ifc_file, footprint)
        pos = axis2placement3d(ifc_file, Vec(0, 0, 0), pending.plane.z_axis, pending.plane.x_axis)
        solid = extrude_profile(ifc_file, profile, pending.height, position=pos)
        return solid, "SweptSolid"

    # ── Graph mode (offset-based) ────────────────────────────────────

    @staticmethod
    def _build_from_graph_offset(
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
    ) -> tuple[ifcopenshell.entity_instance, str]:
        """Buffer graph edges via Shapely → single closed polygon → one extrusion.

        Strategy: group edges into connected components, then per component:

        - **Simple path / chain** (all degrees ≤ 2): order nodes into a
          sequence and buffer as a single ``LineString``.  Shapely miters
          every corner correctly with no "two rectangles" artefact.
        - **Branching (T/X, degree ≥ 3)**: buffer each segment with flat
          caps, then fill each junction vertex with a *shoulder polygon*
          (convex hull of the ht-offset shoulder points of all arms).
          This eliminates the notch that appears at acute-angle junctions
          without introducing circular arcs or extra vertices.

        All component polygons are merged via ``unary_union``.  Interior
        holes (enclosed courtyards) become ``IfcArbitraryProfileDefWithVoids``
        voids automatically.
        """
        if not _SHAPELY_AVAILABLE:
            raise ImportError(
                "WallGraphBuilder (graph mode) requires shapely. "
                "Install it with: pip install shapely"
            )

        plane = pending.plane
        ht = pending.thickness / 2

        # Project all vertices to plane-local 2D coords once.
        local_pts: list[tuple[float, float]] = []
        for v in pending.vertices:
            loc = plane.to_local(v)
            local_pts.append((loc.x, loc.y))

        # Collect valid edges (skip zero-length segments).
        valid_edges: list[tuple[int, int]] = []
        for vi, vj in pending.edges:
            p0 = pending.vertices[vi]
            p1 = pending.vertices[vj]
            if abs(p1 - p0) >= 1e-6:
                valid_edges.append((vi, vj))

        if not valid_edges:
            raise ValueError("WallGraph: no valid segments to build.")

        # ── Connected components via BFS (no external dependency) ──────
        adjacency: dict[int, list[int]] = {}
        for vi, vj in valid_edges:
            adjacency.setdefault(vi, []).append(vj)
            adjacency.setdefault(vj, []).append(vi)

        visited: set[int] = set()
        components: list[list[int]] = []
        for start in adjacency:
            if start in visited:
                continue
            queue = [start]
            comp: list[int] = []
            while queue:
                node = queue.pop()
                if node in visited:
                    continue
                visited.add(node)
                comp.append(node)
                queue.extend(adjacency[node])
            components.append(comp)

        # ── Per-component polygon ──────────────────────────────────────
        component_polys: list[Polygon] = []

        for comp_nodes in components:
            comp_set = set(comp_nodes)
            comp_edges = [(vi, vj) for vi, vj in valid_edges if vi in comp_set]

            # Degree per node within this component
            degree: dict[int, int] = {n: 0 for n in comp_nodes}
            for vi, vj in comp_edges:
                degree[vi] += 1
                degree[vj] += 1

            max_degree = max(degree.values())

            if max_degree <= 2:
                # Simple path or closed loop — order into one LineString.
                endpoints = [n for n, d in degree.items() if d == 1]
                start = endpoints[0] if endpoints else comp_nodes[0]

                ordered: list[int] = [start]
                prev = None
                current = start
                while True:
                    neighbours = [n for n in adjacency[current] if n in comp_set and n != prev]
                    if not neighbours:
                        break
                    nxt = neighbours[0]
                    if nxt == ordered[0] and len(ordered) > 1:
                        ordered.append(nxt)  # closed loop
                        break
                    ordered.append(nxt)
                    prev, current = current, nxt

                coords = [local_pts[n] for n in ordered]
                poly = LineString(coords).buffer(ht, cap_style=2, join_style=2, mitre_limit=10.0)

            else:
                # Branching junction:
                # 1. Buffer each segment individually with flat caps.
                # 2. For every junction vertex (degree ≥ 3), add a shoulder
                #    fill polygon so acute-angle notches are eliminated.
                seg_polys: list[Polygon] = []
                for vi, vj in comp_edges:
                    seg = LineString([local_pts[vi], local_pts[vj]])
                    seg_polys.append(seg.buffer(ht, cap_style=2, join_style=2, mitre_limit=10.0))

                # Add shoulder fill for each branching vertex
                junction_nodes = [n for n, d in degree.items() if d >= 3]
                for jn in junction_nodes:
                    jx, jy = local_pts[jn]
                    # Arm directions: away from junction toward each neighbour
                    arm_dirs: list[tuple[float, float]] = []
                    for vi, vj in comp_edges:
                        if vi == jn:
                            nx, ny = local_pts[vj]
                            arm_dirs.append((nx - jx, ny - jy))
                        elif vj == jn:
                            nx, ny = local_pts[vi]
                            arm_dirs.append((nx - jx, ny - jy))
                    fill = _junction_fill(jx, jy, arm_dirs, ht)
                    seg_polys.append(fill)

                poly = unary_union(seg_polys)

            if isinstance(poly, MultiPolygon):
                warnings.warn(
                    "WallGraph: buffered component produced disconnected polygons; "
                    "keeping only the largest piece. Check for zero-thickness joints.",
                    stacklevel=4,
                )
                poly = max(poly.geoms, key=lambda g: g.area)

            if isinstance(poly, Polygon) and not poly.is_empty:
                component_polys.append(poly)

        if not component_polys:
            raise ValueError("WallGraph: Shapely buffer produced empty/invalid polygon.")

        polygon = unary_union(component_polys)

        if isinstance(polygon, MultiPolygon):
            warnings.warn(
                "WallGraph: merged wall polygon is disconnected; keeping only the largest piece. "
                "Check that all wall components share vertices or overlap.",
                stacklevel=3,
            )
            polygon = max(polygon.geoms, key=lambda g: g.area)

        if not isinstance(polygon, Polygon) or polygon.is_empty:
            raise ValueError("WallGraph: Shapely buffer produced empty/invalid polygon.")

        profile = shapely_polygon_to_ifc_profile(ifc_file, polygon)
        pos = axis2placement3d(ifc_file, Vec(0, 0, 0), plane.z_axis, plane.x_axis)
        solid = extrude_profile(ifc_file, profile, pending.height, position=pos)
        return solid, "SweptSolid"
