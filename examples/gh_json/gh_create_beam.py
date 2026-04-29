"""
gh_create_beam.py  —  GH Script component: "Create IFC Swept Beam"
===================================================================

Stateless component: serializes swept beam paths to JSON strings.

Component inputs
----------------
path_curves  : list — Rhino LineCurve and/or ArcCurve objects defining the
                      sweep path. Connected segments are merged into one path.
profile_pts : list — Rhino Point3d objects defining the cross-section
                      polygon in the local XY plane (X = width, Y = up).
                      Minimum 3 points; no closing duplicate needed.
profile_json: str  — JSON string from gh_profile.py (alternative to profile_pts).
                      Takes precedence if both are provided.
name         : str  — Optional element name prefix.

Component outputs
-----------------
out     : str  — Status message.
json_out : list — List of JSON strings (one per beam).

Usage
-----
1. Direct profile points:
    profile_pts = [(-100,0,0), (100,0,0), (100,300,0), (-100,300,0)]

2. From gh_profile component:
    profile_json = (output from gh_profile.py)
"""

import json
from ifckit import PendingSweptBeam, Vec, rhinokit as rk


def _path_from_curves(curves):
    """Convert Rhino curve(s) to an ifckit Path via rhinokit helper."""
    return rk.curves_to_path(curves)


def _get_profile():
    """Get profile from profile_json or profile_pts."""
    if profile_json:
        try:
            data = json.loads(profile_json)
            pts = data.get("profile", [])
            return [Vec(*pt) for pt in pts]
        except Exception:
            pass

    if profile_pts:
        return rk.pts_to_vecs(profile_pts)

    return None


messages = []
json_outputs = []

if path_curves:
    curves = path_curves if hasattr(path_curves, "__iter__") else [path_curves]
    path = _path_from_curves(curves)

    if not path:
        messages.append("ERR: no valid path segments")
    else:
        prof = _get_profile()
        if not prof:
            messages.append("ERR: no profile (provide profile_pts or profile_json)")
        else:
            for i, _ in enumerate([curves[0]]):  # single beam from path
                try:
                    el_name = f"{name or 'SweptBeam'}-{i + 1}"
                    beam = PendingSweptBeam(
                        path=path,
                        profile=prof,
                        name=el_name,
                    )
                    json_outputs.append(beam.to_json())
                    messages.append(f"OK  {el_name}")
                except Exception as exc:
                    messages.append(f"ERR {el_name}: {exc}")

elif not path_curves:
    messages.append("No path curves")

out = "\n".join(messages) if messages else "No beams processed."
json_out = json_outputs if json_outputs else []
