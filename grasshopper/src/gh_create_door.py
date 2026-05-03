"""
gh_create_door.py  —  GH Script component: "ifckit Door"
=========================================================

@component  nickname:"ifckit Door"
@group "Elements"
@input  overall_width  : float item — Overall door width (m)
@input  overall_height : float item — Overall door height (m)
@input  operation_type : str   item — Door operation type (SINGLE_SWING_LEFT, SINGLE_SWING_RIGHT, DOUBLE_SWING_LEFT, DOUBLE_SWING_RIGHT, SLIDING_TO_LEFT, SLIDING_TO_RIGHT, NOTDEFINED)
@input  type_ref       : str   item — Optional type_key or name of an IfcDoorType to assign
@input  name           : str   item — Optional element name
@input  properties     : str   item — JSON dict of user properties e.g. {"FireRating": "EI30"}
@output out      : str  item — Status message
@output json_out : str  item — Fill envelope JSON: {"doors":[{...}]} — connect to Opening node fills input

Output connects to Opening node (fills input). Opening nests this fill.
"""

import json
from ifckit.elements.opening import PendingDoor
from ifckit import rhinokit as rk


messages = []
json_out = ""

if overall_width and overall_height:
    el_name = str(name) if name else "Door"
    try:
        op_type = str(operation_type).strip().upper() if operation_type else "NOTDEFINED"
        door = PendingDoor(
            overall_width=float(overall_width),
            overall_height=float(overall_height),
            operation_type=op_type,
            type_ref=str(type_ref) if type_ref else None,
            name=el_name,
            properties=rk.parse_user_properties(properties),
        )
        d = door.to_dict()
        json_out = json.dumps({"doors": [d]})
        messages.append(f"OK  {el_name}  {overall_width}x{overall_height}m")
    except Exception as exc:
        messages.append(f"ERR {el_name}: {exc}")
else:
    messages.append("ERR: overall_width and overall_height required")

out = "\n".join(messages) if messages else "No door processed."
