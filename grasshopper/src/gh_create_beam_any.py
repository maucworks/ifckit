"""
gh_create_beam_any.py  —  GH Script component: "ifckit Beam (Any Path)"
========================================================================

@component  nickname:"ifckit Beam (Any Path)"  panel:"Elements"
@input  path_curve   : curve   item — LineCurve or ArcCurve defining the beam path
@input  profile_pts  : point   list — Cross-section polygon as Point3d list (fallback)
@input  profile_json : str     item — Profile JSON from ifckit Profile node
@input  name         : str     item — Optional element name
@output out       : str     item — Status message
@output path_type : str     item — Detected path type
@output json_out  : generic list — List of element JSON strings

Stateless: auto-detects path type (line → ExtrudedAreaSolid, arc → RevolvedAreaSolid).
"""

import math
import json
import ifckit_reload  # noqa: F401 — sets sys.path and reloads all of ifckit

from ifckit import PendingBeam, PendingRevolvedBeam, Vec
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

if path_curve:
    line = rk.curve_to_line(path_curve)
    if line:
        path = line
        detected_path_type = classify_path(path)
    else:
        arc = rk.arc_to_arc(path_curve)
        if arc:
            path = arc
            detected_path_type = classify_path(path)
        else:
            messages.append("ERR: invalid curve (not line or arc)")
            detected_path_type = "unknown"

    if detected_path_type in (PathType.SINGLE_LINE, PathType.SINGLE_ARC):
        prof = _get_profile()
        if not prof:
            messages.append("ERR: no profile (provide profile_pts or profile_json)")
        else:
            try:
                el_name = name or "Beam"

                if detected_path_type == PathType.SINGLE_LINE:
                    beam = PendingBeam(axis=path, profile=prof, name=el_name)
                    solid_type = "ExtrudedAreaSolid"
                else:
                    beam = PendingRevolvedBeam(arc=path, profile=prof, name=el_name)
                    solid_type = "RevolvedAreaSolid"
                    angle_deg = math.degrees(abs(path.angle))

                json_outputs.append(beam.to_json())
                if detected_path_type == PathType.SINGLE_LINE:
                    messages.append(f"OK  {el_name} ({solid_type})")
                else:
                    messages.append(f"OK  {el_name} ({solid_type}, {angle_deg:.0f}° arc)")
            except Exception as exc:
                messages.append(f"ERR {el_name}: {exc}")
    elif detected_path_type == PathType.MULTI_SEGMENT:
        messages.append("ERR: multi-segment path not yet implemented")
    elif detected_path_type == PathType.NON_PLANAR:
        messages.append("ERR: non-planar path not yet implemented")
    else:
        if not messages:
            messages.append("ERR: could not classify path")

elif not path_curve:
    messages.append("No path curve")

out = "\n".join(messages) if messages else "No beams processed."
print(out)
path_type = detected_path_type if 'detected_path_type' in dir() else ""
json_out = json_outputs if json_outputs else []