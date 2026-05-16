"""
gh_create_tapered.py  —  GH Script component: "ifckit Tapered Extrusion"
=========================================================================

@component  nickname:"ifckit Tapered Extrusion"
@group "Elements"
@input  start_curve : curve item — Closed curve (polyline or arc): start profile (bottom)
@input  end_curve   : curve item — Closed curve (polyline or arc): end profile (top)
@input  height      : float item — Extrusion height (m)
@input  plane       : plane item — Placement plane (default world XY)
@input  name        : str   item — Optional element name
@input  properties  : str   item — JSON dict of user properties e.g. {"Material": "Concrete"}
@output out      : str item — Status message
@output json_out : str list — Envelope JSON strings: {"elements":[{...}]}
@output ids      : str list — UUID assigned to each element

Stateless: converts Rhino curves to ifckit Path objects (preserving arcs),
then builds PendingTaperedExtrusion → IfcExtrudedAreaSolidTapered.
"""

import json
import uuid

from ifckit import PendingTaperedExtrusion, Plane
from ifckit import rhinokit as rk

messages = []
json_outputs = []
ids = []

if start_curve and end_curve and height:
    try:
        _plane = rk.rhino_plane_to_plane(plane) if plane else Plane.world_xy()
        _start_path = rk.curves_to_path(start_curve)
        _end_path = rk.curves_to_path(end_curve)

        if not _start_path.is_closed or not _end_path.is_closed:
            raise ValueError("both start_curve and end_curve must be closed")

        el_name = str(name) if name else "Tapered"
        el_id = str(uuid.uuid4())

        tapered = PendingTaperedExtrusion(
            plane=_plane,
            start_profile=_start_path,
            end_profile=_end_path,
            height=float(height),
            name=el_name,
            properties=rk.parse_user_properties(properties),
        )
        d = json.loads(tapered.to_json())
        d["id"] = el_id
        json_outputs.append(json.dumps({"elements": [d]}))
        ids.append(el_id)

        n_start = len(_start_path._segments)
        n_end = len(_end_path._segments)
        has_arc = any(
            not hasattr(seg, "direction") for seg in _start_path._segments
        ) or any(
            not hasattr(seg, "direction") for seg in _end_path._segments
        )
        arc_note = " (arcs)" if has_arc else ""
        messages.append(
            f"OK  {el_name}  {n_start}s → {n_end}s{arc_note}  "
            f"h={height}m  id={el_id[:8]}"
        )
    except Exception as exc:
        messages.append(f"ERR {name or 'Tapered'}: {exc}")
else:
    missing = []
    if not start_curve:
        missing.append("start_curve")
    if not end_curve:
        missing.append("end_curve")
    if not height:
        missing.append("height")
    messages.append(f"ERR: missing inputs: {', '.join(missing)}")

out = "\n".join(messages) if messages else "No tapered extrusions processed."
json_out = json_outputs if json_outputs else []
