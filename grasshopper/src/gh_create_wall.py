"""
gh_create_wall.py  —  GH Script component: "ifckit Wall"
=========================================================

@component  nickname:"ifckit Wall"
@group "Elements"
@input  base_curve : curve item — Base line curve of the wall
@input  height     : float item — Wall height (m)
@input  thickness  : float item — Wall thickness (m)
@input  name       : str   item — Optional element name
@input  properties : str   item — JSON dict of user properties e.g. {"Material": "Concrete"}
@output out      : str item — Status message
@output json_out : str  list — List of element JSON strings

Stateless: serializes wall curves → JSON strings.
"""

import json
from ifckit import PendingWall, Plane, rhinokit as rk


def _get_properties():
    if properties:
        try:
            return json.loads(properties)
        except Exception:
            pass
    return {}


messages = []
json_outputs = []

if base_curve:
    curves = base_curve if hasattr(base_curve, "__iter__") else [base_curve]

    for i, crv in enumerate(curves):
        if crv is None:
            continue
        el_name = f"{name or 'Wall'}-{i + 1}"
        footprint = rk.polyline_to_vecs(crv)
        wall = PendingWall(
            footprint=footprint,
            plane=Plane.world_xy(),
            height=float(height),
            name=el_name,
            properties=_get_properties(),
        )
        json_outputs.append(wall.to_json())
        messages.append(f"OK  {el_name}")

out = "\n".join(messages) if messages else "No walls processed."
json_out = json_outputs if json_outputs else []
