"""
ifckit.builders.wall_graph
==========================

WallGraphBuilder: PendingWallGraph -> IfcWall.

- **Path mode (closed):**  offsets the centerline outward/inward by
  ``thickness / 2`` and creates a single ``IfcExtrudedAreaSolid``
  with a void — a clean SweptSolid, no boolean tree.
- **Path mode (open):**  samples the path to a polyline and creates
  individual segment extrusions with boolean union.
- **Edge mode:**  each edge is extruded separately and boolean-union'd
  (required for T/X junctions).
"""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api

from ifckit.builders._geom import (
    axis2placement3d,
    extrude_profile,
    local_placement,
    product_definition_shape,
    profile_from_points,
    shape_representation,
)
from ifckit.builders.base import BaseBuilder
from ifckit.builders.psets import write_psets
from ifckit.elements.base import PendingElement
from ifckit.geometry import Vec
from ifckit.profiles.shapes import RectangleProfile


def _polygon_area(pts: list[tuple[float, float]]) -> float:
    """Signed area of a 2D polygon (positive = CCW)."""
    n = len(pts)
    if n < 3:
        return 0.0
    return (
        sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
        / 2.0
    )


def _ll_intersect(p1: Vec, d1: Vec, p2: Vec, d2: Vec) -> Vec | None:
    """Intersection of 2D lines ``p1 + t*d1`` and ``p2 + s*d2``."""
    denom = d1.x * (-d2.y) - d1.y * (-d2.x)
    if abs(denom) < 1e-12:
        return None
    dx, dy = p2.x - p1.x, p2.y - p1.y
    t = (dx * (-d2.y) - dy * (-d2.x)) / denom
    return Vec(p1.x + t * d1.x, p1.y + t * d1.y, p1.z + t * d1.z)


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
                except (ValueError, IndexError):
                    geometry, rep_type = self._build_from_open_path(ifc_file, pending)
            else:
                geometry, rep_type = self._build_from_open_path(ifc_file, pending)
        else:
            geometry, rep_type = self._build_from_edges(ifc_file, pending)

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

        oa = abs(_polygon_area(outer.to_profile_points(plane=pending.plane)))
        ia = abs(_polygon_area(inner.to_profile_points(plane=pending.plane)))
        if ia > oa:
            outer, inner = inner, outer

        outer.with_hole(inner)
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
        def _intersect(
            segs: list[tuple[Vec, Vec]],
            end_pt: Vec,
        ) -> list[Vec]:
            if not segs:
                return []
            result: list[Vec] = [segs[0][0]]
            for i in range(1, len(segs)):
                p1, d1 = segs[i - 1]
                p2, d2 = segs[i]
                ip = _ll_intersect(p1, d1, p2, d2)
                result.append(ip if ip is not None else p2)
            result.append(end_pt)
            return result

        left_pts = _intersect(left_segs, left_end)
        right_pts = _intersect(right_segs, right_end)

        # Closed footprint: left polyline + right polyline reversed
        footprint = left_pts + right_pts[::-1]

        profile = profile_from_points(ifc_file, footprint)
        pos = axis2placement3d(ifc_file, Vec(0, 0, 0), pending.plane.z_axis, pending.plane.x_axis)
        solid = extrude_profile(ifc_file, profile, pending.height, position=pos)
        return solid, "SweptSolid"

    # ── Edge mode ───────────────────────────────────────────────────

    @staticmethod
    def _build_from_edges(
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
    ) -> tuple[ifcopenshell.entity_instance, str]:
        """Extrude each edge as a rectangle, boolean-union together."""
        thickness = pending.thickness
        height = pending.height
        plane = pending.plane

        solids = []
        for vi, vj in pending.edges:
            p0 = pending.vertices[vi]
            p1 = pending.vertices[vj]
            seg_dir = (p1 - p0).normalized()
            seg_len = (p1 - p0).length()
            if seg_len < 1e-6:
                continue
            mid = (p0 + p1) * 0.5
            perp = seg_dir ** Vec(0, 0, 1)

            profile = RectangleProfile(thickness, seg_len)
            prof_def = profile.to_ifc(ifc_file)
            pos = axis2placement3d(ifc_file, origin=mid, z_axis=plane.z_axis, x_axis=perp)
            solid = extrude_profile(ifc_file, prof_def, height, position=pos)
            solids.append(solid)

        if not solids:
            raise ValueError("WallGraph: no valid segments to build.")

        if len(solids) == 1:
            return solids[0], "SweptSolid"

        geometry = solids[0]
        for solid in solids[1:]:
            geometry = ifc_file.create_entity(
                "IfcBooleanResult",
                Operator="UNION",
                FirstOperand=geometry,
                SecondOperand=solid,
            )
        return geometry, "Brep"
