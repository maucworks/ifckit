"""
gh_create_revolved_beam.py  —  GH Script component: "Create IFC Revolved Beam"
================================================================================

Stateless component: serializes arc/line-based beam paths to JSON strings.
Handles list of arcs (from biarc reduction) → multiple IfcRevolvedAreaSolid via PendingRevolvedBeam.

Component inputs
----------------
arcs         : list — Rhino ArcCurve objects (from biarc reduction).
                  May have mixed normals (concave vs convex).
profile_pts  : list — Rhino Point3d objects defining the cross-section
                    polygon in the local XY plane (X = width, Y = up).
                    Minimum 3 points; no closing duplicate needed.
profile_json: str  — JSON string from gh_profile.py (alternative to profile_pts).
                    Takes precedence if both are provided.
name          : str  — Optional element name prefix.
plane_normal : list — [x, y, z] canonical plane normal (default: [1, 0, 0]).

Component outputs
-----------------
out      : str  — Status message.
json_out : list — List of JSON strings (one per beam segment).
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
import ifckit.elements
import ifckit.builders
import ifckit.builders.beam_factory
import ifckit.builders.revolved_beam
import ifckit.rhinokit

# Reload in dependency order: geometry first, then elements, builders, then root
importlib.reload(ifckit.geometry)
importlib.reload(ifckit.elements)
importlib.reload(ifckit.rhinokit)
importlib.reload(ifckit.builders.beam_factory)
importlib.reload(ifckit.builders.revolved_beam)
importlib.reload(ifckit.builders)
importlib.reload(ifckit)

from ifckit import PendingRevolvedBeam, Vec
from ifckit.geometry import assemble_path_planar
import ifckit.rhinokit as rk


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


def _to_ifckit_arc(rhino_arc):
    """Convert Rhino ArcCurve to ifckit Arc."""
    return rk.arc_to_arc(rhino_arc)


messages = []
json_outputs = []

if arcs:
    prof = _get_profile()
    if not prof:
        messages.append("ERR: no profile (provide profile_pts or profile_json)")
    else:
        normal = Vec(*plane_normal) if plane_normal else Vec(1, 0, 0)

        ifckit_arcs = []
        for rh_arc in arcs:
            ifckit_arc = _to_ifckit_arc(rh_arc)
            if not ifckit_arc:
                messages.append(f"ERR: invalid arc curve")
                continue
            ifckit_arcs.append(ifckit_arc)

        if not ifckit_arcs:
            messages.append("ERR: no valid arcs")
        else:
            paths = assemble_path_planar(ifckit_arcs, normal)

            for path_idx, path in enumerate(paths):
                for seg_idx, seg in enumerate(path.segments):
                    from ifckit.geometry import Arc, Line
                    if isinstance(seg, Line):
                        messages.append(f"WRN: Line segment {seg_idx} in path {path_idx} — skipped (revolved beam requires arc)")
                        continue

                    try:
                        el_name = f"{name or 'RevolvedBeam'}_{path_idx}_{seg_idx}"
                        # Pass cp_normal to ensure profile continuity when arc normals differ
                        beam = PendingRevolvedBeam(arc=seg, profile=prof, name=el_name, cp_normal=normal)
                        json_outputs.append(beam.to_json())
                        angle_deg = math.degrees(abs(seg.angle))
                        messages.append(f"OK  {el_name} ({angle_deg:.0f}° arc)")
                    except Exception as exc:
                        messages.append(f"ERR {el_name}: {exc}")

elif not arcs:
    messages.append("No arcs")

out = "\n".join(messages) if messages else "No beams processed."
print(out)
json_out = json_outputs if json_outputs else []