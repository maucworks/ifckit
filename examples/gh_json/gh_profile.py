"""
gh_profile.py  —  GH Script component: "Create Standard Profile"
================================================================

Stateless component: generates standard steel section profiles.

Component inputs
----------------
profile_type : str  — "I" for I-beam, "L" for L-beam.
height       : float — Total height (I-beam) or leg length A (L-beam), in meters.
width        : float — Flange width (I-beam) or leg length B (L-beam), in meters.
web_thickness: float — Web thickness (I-beam only), in meters.
flange_thickness: float — Flange thickness (both), in meters.
name         : str  — Optional profile name.

Component outputs
-----------------
out      : str — Status message.
json_out : str — JSON string representing the profile as a list of Vec tuples.
                 Can be used as profile input for beams, columns, etc.

Example — I-beam 200 mm height, 100 mm width, 6 mm web, 10 mm flange (in meters):
    profile_type = "I"
    height = 0.2
    width = 0.1
    web_thickness = 0.006
    flange_thickness = 0.01
"""

import json
from ifckit import IBeamProfile, LBeamProfile, Vec

profile_type = (profile_type or "").strip().upper()
messages = []
json_out = ""

if profile_type in ("I", "L"):
    try:
        h = float(height or 0)
        w = float(width or 0)
        wt = float(web_thickness or 0)
        ft = float(flange_thickness or 0)

        if h <= 0 or w <= 0:
            messages.append("ERR: height and width required")
        elif profile_type == "I" and (wt <= 0 or ft <= 0):
            messages.append("ERR: web_thickness and flange_thickness required for I-beam")
        elif profile_type == "L" and ft <= 0:
            messages.append("ERR: flange_thickness required for L-beam")
        else:
            if profile_type == "I":
                profile = IBeamProfile(
                    height=h, width=w, web_thickness=wt, flange_thickness=ft, name=name
                )
            else:
                profile = LBeamProfile(
                    height=h, width=w, flange_thickness=ft, name=name
                )

            pts = profile.get_profile_points()
            vecs = [Vec(x, y, 0) for x, y in pts]
            profile_data = [v.to_tuple() for v in vecs]

            json_out = json.dumps({"profile": profile_data, "name": name or f"{profile_type}-Profile"})
            messages.append(f"OK  {profile_type}-beam ({h*1000:.0f}×{w*1000:.0f}mm)")
    except Exception as exc:
        messages.append(f"ERR: {exc}")
else:
    messages.append("ERR: profile_type must be 'I' or 'L'")

out = "\n".join(messages) if messages else "No profile processed."