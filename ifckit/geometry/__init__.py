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
intersection — Intersection
subdivision — catmull_clark, extract_patches, write_obj
frames      — FrameField, transport_frames, fixed_ref_frames, upvector_frames
"""

from ifckit.geometry.biarc import fit_biarcs, solve_biarc
from ifckit.geometry.curve import Curve
from ifckit.geometry.frames import (
    FrameField,
    fixed_ref_frames,
    transport_frames,
    upvector_frames,
)
from ifckit.geometry.intersection import Intersection
from ifckit.geometry.path import Path, assemble_path
from ifckit.geometry.primitives import (
    Arc,
    Line,
    Plane,
    Polyline,
    Vec,
    _polygon_normal,
    _signed_area,
)
from ifckit.geometry.subdivision import catmull_clark, extract_patches, write_obj
from ifckit.geometry.surface import Surface
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
    # path
    "Path",
    "assemble_path",
    # curve
    "Curve",
    "solve_biarc",
    "fit_biarcs",
    # surface
    "Surface",
    "Intersection",
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
