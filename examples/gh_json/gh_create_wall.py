"""
gh_create_wall.py  —  GH Script component: "Create IFC Wall"
==============================================================

Stateless component: serializes wall curves to JSON strings.

Component inputs
----------------
wall_curves : list  — One or more closed planar Rhino curves (Polyline or
                      PolylineCurve) representing the wall base footprints.
height      : float — Wall height in the model's length unit.
name        : str   — Optional element name prefix.

Component outputs
-----------------
out     : str  — Status message.
json_out : list — List of JSON strings (one per wall).
"""

import json
from ifckit import PendingWall, Vec, Plane


def _pt(pt):
    return Vec(pt.X, pt.Y, pt.Z)


def _polyline_to_footprint(crv):
    pl = crv.ToPolyline() if hasattr(crv, "ToPolyline") else crv
    pts = [_pt(p) for p in pl]
    if len(pts) > 1:
        f, l = pts[0], pts[-1]
        if abs(f.x - l.x) < 1e-6 and abs(f.y - l.y) < 1e-6:
            pts = pts[:-1]
    return pts


messages = []
json_outputs = []

if wall_curves:
    curves = wall_curves if hasattr(wall_curves, "__iter__") else [wall_curves]

    for i, crv in enumerate(curves):
        if crv is None:
            continue
        try:
            footprint = _polyline_to_footprint(crv)
            el_name = f"{name or 'Wall'}-{i + 1}"
            wall = PendingWall(
                footprint=footprint,
                plane=Plane.world_xy(),
                height=float(height),
                name=el_name,
            )
            json_outputs.append(wall.to_json())
            messages.append(f"OK  {el_name}")
        except Exception as exc:
            messages.append(f"ERR {el_name}: {exc}")

out = "\n".join(messages) if messages else "No walls processed."
json_out = json_outputs if json_outputs else []