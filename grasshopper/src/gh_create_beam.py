"""
gh_create_beam.py  —  GH Script component: "ifckit Beam"
=========================================================

@component  nickname:"ifckit Beam"
@group "Elements"
@input  line_curve   : curve item — LineCurve defining the beam axis
@input  profile_pts  : point list — Cross-section polygon as Point3d list (fallback)
@input  profile_json : str   item — Profile JSON from ifckit Profile node
@input  name         : str   item — Optional element name
@output out      : str item — Status message
@output json_out : str  list — List of element JSON strings

Stateless: serializes linear beam paths → IfcExtrudedAreaSolid via PendingBeam.
"""

import json

from ifckit import PendingBeam, Vec
from ifckit.profiles import Profile
import ifckit.rhinokit as rk
from ifckit.builders.beam_factory import PathType, classify_path


def _get_profile():
    """Get profile from profile_json (Profile.to_dict() format) or profile_pts."""
    if profile_json:
        try:
            data = json.loads(profile_json)
            if "profile_type" in data:
                return Profile.dispatch_from_dict(data)
        except Exception:
            pass

    if profile_pts:
        return rk.pts_to_vecs(profile_pts)

    return None


messages = []
json_outputs = []

if line_curve:
    line = rk.curve_to_line(line_curve)
    if not line:
        messages.append("ERR: invalid line curve")
    else:
        prof = _get_profile()
        if not prof:
            messages.append("ERR: no profile (provide profile_pts or profile_json)")
        else:
            path_type = classify_path(line)
            if path_type != PathType.SINGLE_LINE:
                messages.append(f"ERR: expected single line path, got {path_type}")
            else:
                try:
                    el_name = name or "Beam"
                    beam = PendingBeam(axis=line, profile=prof, name=el_name)
                    json_outputs.append(beam.to_json())
                    messages.append(f"OK  {el_name}")
                except Exception as exc:
                    messages.append(f"ERR {el_name}: {exc}")

elif not line_curve:
    messages.append("No line curve")

out = "\n".join(messages) if messages else "No beams processed."
print(out)
json_out = json_outputs if json_outputs else []