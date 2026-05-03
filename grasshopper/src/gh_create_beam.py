"""
gh_create_beam.py  —  GH Script component: "ifckit Beam"
=========================================================

@component  nickname:"ifckit Beam"
@group "Elements"
@input  line_curve   : curve  item — LineCurve defining the beam axis
@input  profile_pts  : point  list — Cross-section polygon as Point3d list (fallback)
@input  profile_json : str    item — Profile JSON from ifckit Profile node
@input  name         : str    item — Optional element name
@input  properties   : str    item — JSON dict of user properties e.g. {"Supplier": "Voortman"}
@input  clips        : plane  list — Optional clipping planes (z_axis points toward material to keep)
@output out      : str item — Status message
@output json_out : str  list — Envelope JSON strings: {"elements":[{...}]}
@output ids      : str  list — UUID assigned to each beam

Stateless: serializes linear beam paths → IfcExtrudedAreaSolid via PendingBeam.
"""

import json
import uuid

from ifckit import PendingBeam, Vec
from ifckit.profiles import Profile
import ifckit.rhinokit as rk
from ifckit.builders.beam_factory import PathType, classify_path


def _get_profile():
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
ids = []

if line_curve:
    line = rk.curves_to_path(line_curve)
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
                    el_id = str(uuid.uuid4())
                    beam = PendingBeam(axis=line, profile=prof, name=el_name,
                                      clips=rk.parse_clips(clips),
                                      properties=rk.parse_user_properties(properties))
                    d = json.loads(beam.to_json())
                    d["id"] = el_id
                    json_outputs.append(json.dumps({"elements": [d]}))
                    ids.append(el_id)
                    messages.append(f"OK  {el_name}  id={el_id[:8]}")
                except Exception as exc:
                    messages.append(f"ERR {el_name}: {exc}")

elif not line_curve:
    messages.append("No line curve")

out = "\n".join(messages) if messages else "No beams processed."
json_out = json_outputs if json_outputs else []
