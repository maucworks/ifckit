"""
gh_create_door_type.py  —  GH Script component: "ifckit DoorType"
==================================================================

@component  nickname:"ifckit DoorType"
@group "Types"
@input  overall_width   : float item — Overall door width (m)
@input  overall_height  : float item — Overall door height (m)
@input  operation_type  : str   item — Door operation type (SINGLE_SWING_LEFT, SINGLE_SWING_RIGHT, DOUBLE_SWING_LEFT, DOUBLE_SWING_RIGHT, SLIDING_TO_LEFT, SLIDING_TO_RIGHT, NOTDEFINED)
@input  name            : str   item — Type name (also used as type_ref from Door component)
@input  lining_depth    : float item — Lining depth (m, optional)
@input  lining_thickness: float item — Lining thickness (m, optional)
@input  threshold_depth : float item — Threshold depth (m, optional)
@input  panel_depth     : float item — Panel depth (m, optional)
@input  panel_operation : str   item — Panel operation (SWINGING, DOUBLE_ACTING, SLIDING, FOLDING, REVOLVING, ROLLINGUP, NOTDEFINED, optional)
@input  properties      : str   item — JSON dict of user properties
@output out      : str item — Status message
@output json_out : str list — Envelope JSON strings: {"door_types":[{...}]}

Stateless: serializes door type parameters → keyed envelope JSON string.
Connect json_out to gh_merge, then gh_storey, then gh_build_json.
Use the name value as type_ref in the ifckit Door component.
"""

import json
from ifckit.elements.types import PendingDoorType
from ifckit import rhinokit as rk


def _opt_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except Exception:
        return None


messages = []
json_outputs = []

if overall_width and overall_height:
    try:
        op_type = str(operation_type).strip().upper() if operation_type else "NOTDEFINED"
        dt = PendingDoorType(
            overall_width=float(overall_width),
            overall_height=float(overall_height),
            operation_type=op_type,
            name=str(name) if name else "",
            lining_depth=_opt_float(lining_depth),
            lining_thickness=_opt_float(lining_thickness),
            threshold_depth=_opt_float(threshold_depth),
            panel_depth=_opt_float(panel_depth),
            panel_operation=str(panel_operation).strip() if panel_operation else None,
            properties=rk.parse_user_properties(properties),
        )
        json_outputs.append(json.dumps({"door_types": [dt.to_dict()]}))
        messages.append(f"OK  DoorType '{dt.name or dt.type_key[:8]}'")
    except Exception as exc:
        messages.append(f"ERR DoorType: {exc}")

out = "\n".join(messages) if messages else "No door types processed."
json_out = json_outputs if json_outputs else []
