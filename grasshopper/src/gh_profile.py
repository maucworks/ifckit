"""
gh_profile.py  —  GH Script component: "ifckit Profile"
=========================================================

@component  nickname:"ifckit Profile"
@group "Profiles"
@input  profile_type     : str   item — Profile type: "I","L","rect","circle","hollow_circle","steel"
@input  height           : float item — Height or leg A (m)
@input  width            : float item — Width or leg B (m)
@input  web_thickness    : float item — Web thickness (m) — I-beam only
@input  flange_thickness : float item — Flange / leg thickness (m)
@input  radius           : float item — Radius (m) — circle / hollow_circle
@input  wall_thickness   : float item — Wall thickness (m) — hollow_circle
@input  steel_name       : str   item — Steel section name, e.g. "HEA200"
@input  anchor           : str   item — Anchor point: "c" centroid, "s" mid-bottom, "sw" bottom-left (default "c")
@input  unit             : str   item — Unit for steel dims: "m" (default) or "mm"
@input  name             : str   item — Optional profile label
@output out      : str item — Status message
@output json_out : str  item — Profile JSON (Profile.to_dict() format)

Stateless: creates any supported ifckit profile type and outputs a
Profile.to_dict() JSON dict consumable by beam/wall/column nodes.
"""

import json

from ifckit.profiles import (
    IBeamProfile, LBeamProfile,
    RectangleProfile, CircleProfile, HollowCircleProfile,
    SteelProfile,
)
from ifckit.schema import LengthUnit

_pt = (profile_type or "").strip().lower()
_anchor = (anchor or "c").strip().lower()
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
        profile = IBeamProfile(height=h, width=w, web_thickness=wt, flange_thickness=ft, anchor=_anchor, name=name or "I-Profile")

    elif _pt == "l":
        h  = float(height or 0)
        w  = float(width or 0)
        ft = float(flange_thickness or 0)
        if h <= 0 or w <= 0 or ft <= 0:
            raise ValueError("height, width, flange_thickness all required for L-beam")
        profile = LBeamProfile(height=h, width=w, flange_thickness=ft, anchor=_anchor, name=name or "L-Profile")

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
        profile = SteelProfile.from_name(sname, anchor=_anchor, unit=lu)
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
