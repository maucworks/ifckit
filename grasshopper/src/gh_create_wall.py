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
@input  clips      : plane list — Optional clipping planes (z_axis points toward material to keep)
@output out      : str item — Status message
@output json_out : str list — Envelope JSON strings: {"elements":[{...}]}
@output ids      : str list — UUID assigned to each wall (use as host_id in Opening node)

Stateless: serializes wall curves → keyed envelope JSON strings.
Each wall gets a stable UUID as its "id" field.
"""

import json
import uuid
from ifckit import PendingWall, Plane, rhinokit as rk


messages = []
json_outputs = []
ids = []

if base_curve:
    curves = base_curve if hasattr(base_curve, "__iter__") else [base_curve]

    for i, crv in enumerate(curves):
        if crv is None:
            continue
        el_name = f"{name or 'Wall'}-{i + 1}"
        el_id = str(uuid.uuid4())
        try:
            footprint = rk.polyline_to_vecs(crv)
            wall = PendingWall(
                footprint=footprint,
                plane=Plane.world_xy(),
                height=float(height),
                name=el_name,
                clips=rk.parse_clips(clips),
                properties=rk.parse_user_properties(properties),
            )
            d = wall.to_dict()
            d["id"] = el_id
            json_outputs.append(json.dumps({"elements": [d]}))
            ids.append(el_id)
            messages.append(f"OK  {el_name}  id={el_id[:8]}")
        except Exception as exc:
            messages.append(f"ERR {el_name}: {exc}")

out = "\n".join(messages) if messages else "No walls processed."
json_out = json_outputs if json_outputs else []
