"""
ifckit.geometry
===============

Framework-agnostic geometry primitives for IFC construction.
No Rhino, no Grasshopper, no external dependencies beyond the standard library.

Modules
-------
primitives  — Vec, Plane, Line, Arc, Polyline
path        — Path, assemble_path
biarc       — solve_biarc, fit_biarcs
curve       — Curve
surface     — Surface (also: occ_eval_point, occ_intersect_plane)
field       — Field, FieldPoint, trim_grid, crossing_grid, divide_trim_edge
patterns    — quad/diamond/triangle/wave/anglebox/brick/truchet/hex/hankin cells
panel_report — FieldReport, field_report, cells_report
intersection — Intersection
subdivision — catmull_clark, extract_patches, write_obj
frames      — FrameField, transport_frames, fixed_ref_frames, upvector_frames
"""

from ifckit.geometry.biarc import fit_biarcs, solve_biarc
from ifckit.geometry.curve import Curve, CurveReport
from ifckit.geometry.field import (
    Field,
    FieldPoint,
    crossing_grid,
    divide_trim_edge,
    orient_division,
    trim_grid,
)
from ifckit.geometry.frames import (
    FrameField,
    fixed_ref_frames,
    transport_frames,
    upvector_frames,
)
from ifckit.geometry.intersection import Intersection
from ifckit.geometry.panel_report import FieldReport, cells_report, field_report
from ifckit.geometry.path import Path, PathReport, assemble_path
from ifckit.geometry.patterns import (
    DiamondPattern,
    HexPattern,
    anglebox_cells,
    brick_cells,
    diamond_cells,
    hankin_cells,
    hex_cells,
    quad_cells,
    triangle_cells,
    truchet_cells,
    wave_cells,
)
from ifckit.geometry.primitives import (
    Arc,
    ArcReport,
    Line,
    LineReport,
    Plane,
    PlaneReport,
    Polyline,
    Vec,
    VecReport,
    _polygon_normal,
    _signed_area,
)
from ifckit.geometry.spiral import Spiral
from ifckit.geometry.subdivision import catmull_clark, extract_patches, write_obj
from ifckit.geometry.surface import Surface, SurfaceReport
from ifckit.geometry.transform import Transform

__all__ = [
    # primitives
    "Vec",
    "Plane",
    "Line",
    "Arc",
    "Polyline",
    "_polygon_normal",
    "_signed_area",
    # reports
    "VecReport",
    "PlaneReport",
    "LineReport",
    "ArcReport",
    "PathReport",
    "CurveReport",
    "SurfaceReport",
    # path
    "Path",
    "assemble_path",
    # curve
    "Curve",
    "solve_biarc",
    "fit_biarcs",
    # spiral
    "Spiral",
    # surface
    "Surface",
    "Intersection",
    # field
    "Field",
    "FieldPoint",
    "trim_grid",
    "crossing_grid",
    "divide_trim_edge",
    "orient_division",
    # patterns
    "quad_cells",
    "DiamondPattern",
    "diamond_cells",
    "HexPattern",
    "hex_cells",
    "wave_cells",
    "anglebox_cells",
    "brick_cells",
    "truchet_cells",
    "hankin_cells",
    "triangle_cells",
    # panel_report
    "FieldReport",
    "field_report",
    "cells_report",
    # subdivision
    "catmull_clark",
    "extract_patches",
    "write_obj",
    # frames
    "FrameField",
    "transport_frames",
    "fixed_ref_frames",
    "upvector_frames",
    # transform
    "Transform",
]
