"""
gh_create_window.py  —  GH Script component: "ifckit Window"
=============================================================

@component  nickname:"ifckit Window"
@group "Elements"
@input  overall_width  : float item — Overall window width (m)
@input  overall_height : float item — Overall window height (m)
@input  window_type    : str   item — Window type (SINGLE_PANEL, SIDE_HUNG_RIGHT_HAND, SIDE_HUNG_LEFT_HAND, TILT_AND_TURN_RIGHT_HAND, FIXED_CASEMENT, NOTDEFINED)
@input  type_ref       : str   item — Optional type_key or name of an IfcWindowType to assign
@input  name           : str   item — Optional element name
@input  properties     : str   item — JSON dict of user properties e.g. {"GlazingType": "Double"}
@output out      : str  item — Status message
@output json_out : str  item — Fill envelope JSON: {"windows":[{...}]} — connect to Opening node fills input

Output connects to Opening node (fills input). Opening nests this fill.
"""

import json
from ifckit.elements.opening import PendingWindow
from ifckit import rhinokit as rk


messages = []
json_out = ""

if overall_width and overall_height:
    el_name = str(name) if name else "Window"
    try:
        wt = str(window_type).strip().upper() if window_type else "NOTDEFINED"
        win = PendingWindow(
            overall_width=float(overall_width),
            overall_height=float(overall_height),
            window_type=wt,
            type_ref=str(type_ref) if type_ref else None,
            name=el_name,
            properties=rk.parse_user_properties(properties),
        )
        d = win.to_dict()
        json_out = json.dumps({"windows": [d]})
        messages.append(f"OK  {el_name}  {overall_width}x{overall_height}m")
    except Exception as exc:
        messages.append(f"ERR {el_name}: {exc}")
else:
    messages.append("ERR: overall_width and overall_height required")

out = "\n".join(messages) if messages else "No window processed."
