"""
ifckit.builders._tessellate
===========================

Tessellation helpers for sectioned-spine geometry.
"""

from __future__ import annotations

import math as _math

import ifcopenshell

from ifckit.builders._precision import round_coord
from ifckit.builders._profile import (
    _profile_def_to_rings,
    _resample_ring,
    _stitch_annulus,
    _triangulate_polygon,
)


def _tessellate_sectioned_spine(
    cross_sections: list[ifcopenshell.entity_instance],
    positions: list[ifcopenshell.entity_instance],
    segments: int = 8,
    closed: bool = False,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    from ifckit.geometry import Vec

    axis_frames = []
    for axis in positions:
        origin = axis.Location.Coordinates
        z_axis = axis.Axis.DirectionRatios if axis.Axis else (0, 0, 1)
        x_axis = axis.RefDirection.DirectionRatios if axis.RefDirection else (1, 0, 0)

        z_vec = Vec(*z_axis).normalized()
        x_vec = Vec(*x_axis).normalized()
        y_vec = z_vec.cross(x_vec).normalized()

        axis_frames.append(
            {
                "origin": Vec(*origin),
                "x": x_vec,
                "y": y_vec,
                "z": z_vec,
            }
        )

    profile_ring_sets: list[tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]] = []
    for prof_def in cross_sections:
        outer, inners = _profile_def_to_rings(prof_def, segments=segments)
        area = (
            sum(
                outer[i][0] * outer[(i + 1) % len(outer)][1]
                - outer[(i + 1) % len(outer)][0] * outer[i][1]
                for i in range(len(outer))
            )
            / 2.0
        )
        if area < 0:
            outer = list(reversed(outer))
        normalised_inners = []
        for inner in inners:
            iarea = (
                sum(
                    inner[i][0] * inner[(i + 1) % len(inner)][1]
                    - inner[(i + 1) % len(inner)][0] * inner[i][1]
                    for i in range(len(inner))
                )
                / 2.0
            )
            if iarea > 0:
                inner = list(reversed(inner))
            normalised_inners.append(inner)
        profile_ring_sets.append((outer, normalised_inners))

    def _emit_ring_3d(
        ring2d: list[tuple[float, float]],
        frame: dict,
    ) -> list[tuple[float, float, float]]:
        result = []
        for x2d, y2d in ring2d:
            pt_3d = frame["origin"] + frame["x"] * x2d + frame["y"] * y2d
            result.append((pt_3d.x, pt_3d.y, pt_3d.z))
        return result

    def _stitch_rings(
        prev_start: int,
        curr_start: int,
        prev_ring: list[tuple[float, float]],
        curr_ring: list[tuple[float, float]],
        prev_frame: dict,
        curr_frame: dict,
        verts: list,
        fcs: list,
    ) -> None:
        n_prev = len(prev_ring)
        n_curr = len(curr_ring)

        if n_prev == n_curr:
            n = n_prev
            for i in range(n):
                i_next = (i + 1) % n
                fcs.append(
                    (
                        prev_start + i,
                        prev_start + i_next,
                        curr_start + i_next,
                        curr_start + i,
                    )
                )
        else:
            n_stitch = (n_prev * n_curr) // _math.gcd(n_prev, n_curr)
            prev_resampled = _resample_ring(prev_ring, n_stitch)
            curr_resampled = _resample_ring(curr_ring, n_stitch)

            prev_stitch_start = len(verts)
            for x2d, y2d in prev_resampled:
                pt = prev_frame["origin"] + prev_frame["x"] * x2d + prev_frame["y"] * y2d
                verts.append((pt.x, pt.y, pt.z))

            curr_stitch_start = len(verts)
            for x2d, y2d in curr_resampled:
                pt = curr_frame["origin"] + curr_frame["x"] * x2d + curr_frame["y"] * y2d
                verts.append((pt.x, pt.y, pt.z))

            for i in range(n_stitch):
                i_next = (i + 1) % n_stitch
                fcs.append(
                    (
                        prev_stitch_start + i,
                        prev_stitch_start + i_next,
                        curr_stitch_start + i_next,
                        curr_stitch_start + i,
                    )
                )

    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    section_offsets: list[tuple[int, list[int]]] = []

    for section_idx in range(len(positions)):
        frame = axis_frames[section_idx]
        outer, inners = profile_ring_sets[section_idx]

        outer_start = len(vertices)
        vertices.extend(_emit_ring_3d(outer, frame))

        inner_starts: list[int] = []
        for inner in inners:
            inner_starts.append(len(vertices))
            vertices.extend(_emit_ring_3d(inner, frame))

        section_offsets.append((outer_start, inner_starts))

        if section_idx > 0:
            prev_idx = section_idx - 1
            prev_outer, prev_inners = profile_ring_sets[prev_idx]
            prev_outer_start, prev_inner_starts = section_offsets[prev_idx]
            prev_frame = axis_frames[prev_idx]

            _stitch_rings(
                prev_outer_start,
                outer_start,
                prev_outer,
                outer,
                prev_frame,
                frame,
                vertices,
                faces,
            )

            for hole_idx, (prev_is, curr_is) in enumerate(zip(prev_inner_starts, inner_starts)):
                prev_inner = prev_inners[hole_idx]
                curr_inner = inners[hole_idx]
                _stitch_rings(
                    curr_is,
                    prev_is,
                    curr_inner,
                    prev_inner,
                    frame,
                    prev_frame,
                    vertices,
                    faces,
                )

    if closed and len(section_offsets) >= 2:
        last_outer_start, last_inner_starts = section_offsets[-1]
        last_outer, last_inners = profile_ring_sets[-1]
        last_frame = axis_frames[-1]
        first_outer_start, first_inner_starts = section_offsets[0]
        first_outer, first_inners = profile_ring_sets[0]
        first_frame = axis_frames[0]

        _stitch_rings(
            last_outer_start,
            first_outer_start,
            last_outer,
            first_outer,
            last_frame,
            first_frame,
            vertices,
            faces,
        )
        for hole_idx in range(min(len(last_inner_starts), len(first_inner_starts))):
            _stitch_rings(
                first_inner_starts[hole_idx],
                last_inner_starts[hole_idx],
                first_inners[hole_idx],
                last_inners[hole_idx],
                first_frame,
                last_frame,
                vertices,
                faces,
            )

    if not closed and len(section_offsets) >= 2:
        for is_first in (True, False):
            cap_idx = 0 if is_first else len(section_offsets) - 1
            outer_start, inner_starts = section_offsets[cap_idx]
            outer, inners = profile_ring_sets[cap_idx]
            n = len(outer)

            if not inners:
                if n == 4:
                    if is_first:
                        faces.append(
                            (outer_start, outer_start + 3, outer_start + 2, outer_start + 1)
                        )
                    else:
                        faces.append(
                            (outer_start, outer_start + 1, outer_start + 2, outer_start + 3)
                        )
                else:
                    tris = _triangulate_polygon(outer)
                    for tri in tris:
                        if is_first:
                            faces.append(
                                (outer_start + tri[2], outer_start + tri[1], outer_start + tri[0])
                            )
                        else:
                            faces.append(
                                (outer_start + tri[0], outer_start + tri[1], outer_start + tri[2])
                            )
            else:
                inner = inners[0]
                inner_starts[0]

                cap_frame = axis_frames[cap_idx]
                outer_r, inner_r, quads = _stitch_annulus(outer, inner)
                n_stitch = len(outer_r)

                outer_cap_start = len(vertices)
                for x2d, y2d in outer_r:
                    pt = cap_frame["origin"] + cap_frame["x"] * x2d + cap_frame["y"] * y2d
                    vertices.append((pt.x, pt.y, pt.z))

                inner_cap_start = len(vertices)
                for x2d, y2d in inner_r:
                    pt = cap_frame["origin"] + cap_frame["x"] * x2d + cap_frame["y"] * y2d
                    vertices.append((pt.x, pt.y, pt.z))

                def _resolve_annulus(idx: int) -> int:
                    return (
                        outer_cap_start + idx
                        if idx < n_stitch
                        else inner_cap_start + (idx - n_stitch)
                    )

                for quad in quads:
                    a, b, c, d = (_resolve_annulus(q) for q in quad)
                    if is_first:
                        faces.append((d, c, b, a))
                    else:
                        faces.append((a, b, c, d))

    return vertices, faces


def sectioned_spine(
    f: ifcopenshell.file,
    spine_curve: ifcopenshell.entity_instance,
    cross_sections: list[ifcopenshell.entity_instance],
    positions: list[ifcopenshell.entity_instance],
    profile_segments: int = 32,
    closed: bool = False,
) -> ifcopenshell.entity_instance:
    """Create a sectioned spine solid geometry."""
    if len(cross_sections) != len(positions):
        raise ValueError(
            f"CrossSections ({len(cross_sections)}) must have same length "
            f"as CrossSectionPositions ({len(positions)})"
        )
    if len(cross_sections) < 2:
        raise ValueError("At least 2 cross-sections are required")

    vertices, faces = _tessellate_sectioned_spine(
        cross_sections, positions, segments=profile_segments, closed=closed
    )

    coord_list = [[round_coord(v[0]), round_coord(v[1]), round_coord(v[2])] for v in vertices]

    tris = []
    for face_indices in faces:
        if len(face_indices) == 4:
            tris.append((face_indices[0], face_indices[1], face_indices[2]))
            tris.append((face_indices[0], face_indices[2], face_indices[3]))
        elif len(face_indices) == 3:
            tris.append(face_indices)

    return f.create_entity(
        "IfcTriangulatedFaceSet",
        Coordinates=f.create_entity("IfcCartesianPointList3D", CoordList=coord_list),
        Closed=closed,
        CoordIndex=[[idx + 1 for idx in tri] for tri in tris],
    )
