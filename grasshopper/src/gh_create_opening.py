"""
gh_create_opening.py  —  GH Script component: "ifckit Opening"
==============================================================

@component  nickname:"ifckit Opening"
@group "Elements"
@input  insert_plane : plane item — Insert plane: origin = anchor point (default bottom-centre),
                                    X = width direction (horizontal along wall face),
                                    Y = UP (height direction),
                                    Z = outward normal of wall face (extrusion through wall).
@input  width        : float item — Opening width (m)
@input  height       : float item — Opening height (m)
@input  host_json    : str   item — Envelope JSON from wall/slab node (element must have an "id")
@input  fills        : str   list — Fill JSON strings from Door/Window nodes (nested into this opening)
@input  name         : str   item — Optional element name
@input  properties   : str   item — JSON dict of user properties e.g. {"FireRating": "EI30"}
@output out      : str item — Status message
@output json_out : str item — Updated host envelope JSON with opening (incl. fills) nested inside element

Opening is nested inside the host element. Fills (doors/windows) are nested inside the opening.
IFC chain: element → openings[] → doors[]/windows[]

Plane convention (IFC spec):
  - plane.X = width direction (horizontal along the wall face)
  - plane.Y = UP (height direction)
  - plane.Z = outward normal of the wall face (the extrusion direction through the wall)
  The opening solid is extruded along Z and centred on the wall face (±depth/2).
  Default anchor "s" means the origin sits at the bottom-centre of the opening;
  the door/window frame is built in the same local XY plane.
"""

import json
from ifckit.elements.opening import PendingOpening
from ifckit import rhinokit as rk


messages = []
json_out = ""

if insert_plane and width and height and host_json:
    try:
        # Parse host envelope — must contain exactly one element with an id.
        host_envelope = json.loads(str(host_json).strip()) if isinstance(host_json, str) else host_json
        elements = rk.parse_json_list(host_envelope.get("elements", []))
        if not elements:
            raise ValueError("host_json contains no elements")
        elem = elements[0]
        if not elem.get("id"):
            raise ValueError("host element has no 'id' — add an id in the wall/slab node")

        # Build opening dict.
        ifc_plane = rk.rhino_plane_to_plane(insert_plane)
        op = PendingOpening(
            plane=ifc_plane,
            width=float(width),
            height=float(height),
            name=str(name) if name else "Opening",
            properties=rk.parse_user_properties(properties),
        )
        op_dict = op.to_dict()

        # Nest fills (doors/windows) into this opening.
        op_dict.setdefault("doors", [])
        op_dict.setdefault("windows", [])
        if fills:
            fill_list = fills if isinstance(fills, list) else [fills]
            for raw in fill_list:
                if not raw:
                    continue
                fill_env = json.loads(str(raw).strip()) if isinstance(raw, str) else raw
                for d in rk.parse_json_list(fill_env.get("doors", [])):
                    op_dict["doors"].append(d)
                for w in rk.parse_json_list(fill_env.get("windows", [])):
                    op_dict["windows"].append(w)

        # Attach opening to element.
        elem.setdefault("openings", [])
        elem["openings"].append(op_dict)

        # Rebuild envelope with updated element.
        elements[0] = elem
        out_envelope = dict(host_envelope)
        out_envelope["elements"] = elements

        n_doors = len(op_dict["doors"])
        n_windows = len(op_dict["windows"])
        messages.append(
            f"OK  {op_dict.get('name')}  {n_doors} door(s), {n_windows} window(s)"
        )
        json_out = json.dumps(out_envelope)

    except Exception as exc:
        messages.append(f"ERR: {exc}")
elif not host_json:
    messages.append("ERR: connect wall/slab json_out to host_json")
elif not insert_plane:
    messages.append("ERR: insert_plane required")
else:
    messages.append("ERR: width and height required")

out = "\n".join(messages) if messages else "No opening processed."
