"""
gh_create_revolved_beam.py  —  GH Script component: "Create IFC Revolved Beam"
================================================================================

Stateless component: serializes arc-based beam paths to JSON strings.
Handles single arc paths → IfcRevolvedAreaSolid via PendingRevolvedBeam.

Component inputs
----------------
arc_curve    : Rhino ArcCurve — The arc sweep path (center, start, angle).
profile_pts  : list — Rhino Point3d objects defining the cross-section
                    polygon in the local XY plane (X = width, Y = up).
                    Minimum 3 points; no closing duplicate needed.
profile_json: str  — JSON string from gh_profile.py (alternative to profile_pts).
                    Takes precedence if both are provided.
name         : str  — Optional element name prefix.

Component outputs
-----------------
out      : str  — Status message.
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
import ifckit.builders.revolved_beam
import ifckit.elements
import ifckit.rhinokit

importlib.reload(ifckit.geometry)
importlib.reload(ifckit.elements)
importlib.reload(ifckit.builders)
importlib.reload(ifckit.builders.beam_factory)
importlib.reload(ifckit.builders.revolved_beam)
importlib.reload(ifckit.rhinokit)
importlib.reload(ifckit)

from ifckit import PendingRevolvedBeam, Vec
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

if arc_curve:
    arc = rk.arc_to_arc(arc_curve)
    if not arc:
        messages.append("ERR: invalid arc curve")
    else:
        prof = _get_profile()
        if not prof:
            messages.append("ERR: no profile (provide profile_pts or profile_json)")
        else:
            path_type = classify_path(arc)
            if path_type != PathType.SINGLE_ARC:
                messages.append(f"ERR: expected single arc path, got {path_type}")
            else:
                try:
                    el_name = name or "RevolvedBeam"
                    # DEBUG: show the arc being used
                    print(f"DEBUG: start={arc.start}, center={arc.center}, angle={arc.angle}, tangent={arc.tangent_at_start()}, normal={arc.normal}")
                    beam = PendingRevolvedBeam(arc=arc, profile=prof, name=el_name)
                    json_outputs.append(beam.to_json())
                    angle_deg = math.degrees(abs(arc.angle))
                    messages.append(f"OK  {el_name} ({angle_deg:.0f}° arc)")
                except Exception as exc:
                    messages.append(f"ERR {el_name}: {exc}")

elif not arc_curve:
    messages.append("No arc curve")

out = "\n".join(messages) if messages else "No beams processed."
print(out)
json_out = json_outputs if json_outputs else []