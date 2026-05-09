"""
ifckit.geometry
===============

Framework-agnostic geometry primitives for IFC construction.
No Rhino, no Grasshopper, no external dependencies beyond the standard library.

Modules
-------
primitives  — Vec, Plane, Line, Arc, Polyline
path        — Path, assemble_path
frames      — FrameField, transport_frames, fixed_ref_frames, upvector_frames
"""

from ifckit.geometry.frames import (
    FrameField,
    fixed_ref_frames,
    transport_frames,
    upvector_frames,
)
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
    # frames
    "FrameField",
    "transport_frames",
    "fixed_ref_frames",
    "upvector_frames",
]
