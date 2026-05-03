"""
ifckit.profiles
===============

Profile types for use with PendingBeam, PendingColumn, PendingWall, PendingSlab,
and PendingSpace.

Shape profiles
--------------
    PolygonProfile          — arbitrary closed polygon (straight edges)
    RoundedPolygonProfile   — polygon with per-corner arc fillets
    RectangleProfile        — parametric rectangle  → IfcRectangleProfileDef
    CircleProfile           — parametric circle     → IfcCircleProfileDef
    HollowCircleProfile     — hollow circle (tube)  → IfcCircleHollowProfileDef

Section profiles
----------------
    IBeamProfile            — symmetric I/H section → IfcIShapeProfileDef
    LBeamProfile            — L-section (angle)     → IfcLShapeProfileDef

Steel lookup
------------
    SteelProfile.from_name("HEA200")  — returns a pre-filled IBeamProfile
    SteelProfile.from_name("CHS168.3x10")  — returns a HollowCircleProfile

Base class / registry
---------------------
    Profile                 — abstract base class; use Profile.dispatch_from_dict(d)
                              for polymorphic reconstruction from JSON dicts.

Examples::

    from ifckit.profiles import (
        PolygonProfile, RoundedPolygonProfile,
        RectangleProfile, CircleProfile, HollowCircleProfile,
        IBeamProfile, LBeamProfile, SteelProfile, Profile,
    )

    # Rounded footprint for a wall/slab/space:
    pts = [(0, 0), (5, 0), (5, 4), (0, 4)]
    fp = RoundedPolygonProfile(pts, radius=0.1)

    # Standard steel beam:
    p = SteelProfile.from_name("IPE300")
    ifc_entity = p.to_ifc(ifc_file)

    # Polymorphic round-trip:
    d = p.to_dict()
    p2 = Profile.dispatch_from_dict(d)
"""

from ifckit.profiles.base import Profile
from ifckit.profiles.i_beam import IBeamProfile
from ifckit.profiles.l_beam import LBeamProfile
from ifckit.profiles.shapes import (
    CircleProfile,
    HollowCircleProfile,
    PolygonProfile,
    RectangleProfile,
    RoundedPolygonProfile,
)
from ifckit.profiles.steel import SteelProfile

__all__ = [
    # Base
    "Profile",
    # Shape profiles
    "PolygonProfile",
    "RoundedPolygonProfile",
    "RectangleProfile",
    "CircleProfile",
    "HollowCircleProfile",
    # Section profiles
    "IBeamProfile",
    "LBeamProfile",
    # Steel lookup
    "SteelProfile",
]
