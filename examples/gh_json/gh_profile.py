"""
gh_profile.py  —  GH Script component: "Create Profile"
========================================================

Stateless component: creates any supported ifckit profile type and outputs
a JSON dict (Profile.to_dict() format) consumable by beam/wall/column nodes.

Component inputs
----------------
profile_type     : str  — One of: "I", "L", "rect", "circle", "hollow_circle", "steel"
                         (case-insensitive).

  For "I" (IBeamProfile):
    height           : float — Total height, in model units.
    width            : float — Flange width, in model units.
    web_thickness    : float — Web thickness, in model units.
    flange_thickness : float — Flange thickness, in model units.

  For "L" (LBeamProfile):
    height           : float — Leg length A (vertical), in model units.
    width            : float — Leg length B (horizontal), in model units.
    flange_thickness : float — Leg thickness, in model units.

  For "rect" (RectangleProfile):
    width            : float — Width, in model units.
    height           : float — Height, in model units.

  For "circle" (CircleProfile):
    radius           : float — Radius, in model units.

  For "hollow_circle" (HollowCircleProfile):
    radius           : float — Outer radius, in model units.
    wall_thickness   : float — Wall thickness, in model units.

  For "steel" (SteelProfile lookup):
    steel_name       : str   — Section name, e.g. "HEA200", "IPE300", "CHS168.3x10".
    unit             : str   — "m" (default) or "mm" — model unit for returned dims.

name             : str  — Optional profile name / label.

Component outputs
-----------------
out      : str — Status message.
json_out : str — JSON string (Profile.to_dict()) for use in beam/column nodes.
"""

import json
import ifckit_reload  # noqa: F401 — sets sys.path and reloads all of ifckit

from ifckit.profiles import (
    IBeamProfile, LBeamProfile,
    RectangleProfile, CircleProfile, HollowCircleProfile,
    SteelProfile,
)
from ifckit.schema import LengthUnit

_pt = (profile_type or "").strip().lower()
messages = []
json_out = ""

try:
    profile = None

    if _pt == "i":
        h  = float(height or 0)
        w  = float(width or 0)
        wt = float(web_thickness or 0)
        ft = float(flange_thickness or 0)
        if h <= 0 or w <= 0 or wt <= 0 or ft <= 0:
            raise ValueError("height, width, web_thickness, flange_thickness all required for I-beam")
        profile = IBeamProfile(height=h, width=w, web_thickness=wt, flange_thickness=ft, name=name or "I-Profile")

    elif _pt == "l":
        h  = float(height or 0)
        w  = float(width or 0)
        ft = float(flange_thickness or 0)
        if h <= 0 or w <= 0 or ft <= 0:
            raise ValueError("height, width, flange_thickness all required for L-beam")
        profile = LBeamProfile(height=h, width=w, flange_thickness=ft, name=name or "L-Profile")

    elif _pt == "rect":
        w = float(width or 0)
        h = float(height or 0)
        if w <= 0 or h <= 0:
            raise ValueError("width and height required for rect")
        profile = RectangleProfile(width=w, height=h, name=name or "Rect-Profile")

    elif _pt == "circle":
        r = float(radius or 0)
        if r <= 0:
            raise ValueError("radius required for circle")
        profile = CircleProfile(radius=r, name=name or "Circle-Profile")

    elif _pt == "hollow_circle":
        r  = float(radius or 0)
        wt = float(wall_thickness or 0)
        if r <= 0 or wt <= 0:
            raise ValueError("radius and wall_thickness required for hollow_circle")
        profile = HollowCircleProfile(radius=r, wall_thickness=wt, name=name or "HollowCircle-Profile")

    elif _pt == "steel":
        sname = (steel_name or "").strip()
        if not sname:
            raise ValueError("steel_name required for steel profile")
        u_str = (unit or "m").strip().lower()
        lu = LengthUnit.MILLIMETRE if u_str == "mm" else LengthUnit.METRE
        profile = SteelProfile.from_name(sname, unit=lu)
        if name:
            profile.name = name

    else:
        raise ValueError(
            "profile_type must be one of: 'I', 'L', 'rect', 'circle', 'hollow_circle', 'steel'"
        )

    json_out = json.dumps(profile.to_dict())
    messages.append(f"OK  {profile.name or _pt}")

except Exception as exc:
    messages.append(f"ERR: {exc}")

out = "\n".join(messages) if messages else "No profile processed."
