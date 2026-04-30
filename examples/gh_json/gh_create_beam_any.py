"""
gh_create_beam_any.py  —  GH Script component: "Create IFC Beam (Any Path)"
============================================================================

Stateless component: auto-detects path type and routes to correct builder.
- Line path → IfcExtrudedAreaSolid (via PendingBeam)
- Arc path → IfcRevolvedAreaSolid (via PendingRevolvedBeam)

Component inputs
----------------
path_curve   : Rhino Curve — LineCurve or ArcCurve defining the beam path.
profile_pts  : list — Rhino Point3d objects defining the cross-section
                    polygon in the local XY plane (X = width, Y = up).
                    Minimum 3 points; no closing duplicate needed.
profile_json: str  — JSON string from gh_profile.py (alternative to profile_pts).
                    Takes precedence if both are provided.
name         : str  — Optional element name prefix.

Component outputs
-----------------
out      : str  — Status message.
path_type: str  — Detected path type (single_line, single_arc, multi_segment, non_planar).
json_out : list — List of JSON strings (one per beam).
"""

import math
import json
import os
import sys
import importlib

_fallback_path = r'/Users/Mauc/L140-py-ifckit'
pkg_path = os.environ.get('IFCKIT_PATH', _fallback_path)
if pkg_path not in sys.path:
    sys.path.insert(0, pkg_path)

import ifckit
import ifckit.geometry
import ifckit.builders
import ifckit.builders.beam_factory
import ifckit.elements
import ifckit.rhinokit

importlib.reload(ifckit.geometry)
importlib.reload(ifckit.elements)
importlib.reload(ifckit.builders)
importlib.reload(ifckit.builders.beam_factory)
importlib.reload(ifckit.rhinokit)
importlib.reload(ifckit)

from ifckit import PendingBeam, PendingRevolvedBeam, Vec
import ifckit.rhinokit as rk
from ifckit.builders.beam_factory import PathType, classify_path


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