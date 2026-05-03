"""
gh_create_wall.py  —  GH Script component: "ifckit Wall"
=========================================================

@component  nickname:"ifckit Wall"  panel:"Elements"
@input  base_curve : curve item — Base line curve of the wall
@input  height     : float item — Wall height (m)
@input  thickness  : float item — Wall thickness (m)
@input  name       : str   item — Optional element name
@output out      : str item — Status message
@output json_out : str  list — List of element JSON strings

Stateless: serializes wall curves → JSON strings.
"""

import json
import ifckit_reload  # noqa: F401 — sets sys.path and reloads all of ifckit
from ifckit import PendingWall, Plane, rhinokit as rk

messages = []
json_outputs = []

if base_curve:
    curves = base_curve if hasattr(base_curve, "__iter__") else [base_curve]

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