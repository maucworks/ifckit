"""
gh_create_wall.py  —  GH Script component: "Create IFC Wall"
=============================================================

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
import ifckit_reload  # noqa: F401 — sets sys.path and reloads all of ifckit
from ifckit import PendingWall, Plane, rhinokit as rk

messages = []
json_outputs = []

if wall_curves:
    curves = wall_curves if hasattr(wall_curves, "__iter__") else [wall_curves]

    for i, crv in enumerate(curves):
        if crv is None:
            continue
        el_name = f"{name or 'Wall'}-{i + 1}"
        try:
            footprint = rk.polyline_to_vecs(crv)
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