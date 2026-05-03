"""
gh_create_window_type.py  —  GH Script component: "ifckit WindowType"
======================================================================

@component  nickname:"ifckit WindowType"
@group "Types"
@input  overall_width    : float item — Overall window width (m)
@input  overall_height   : float item — Overall window height (m)
@input  window_type      : str   item — Window type (SINGLE_PANEL, SIDE_HUNG_RIGHT_HAND, SIDE_HUNG_LEFT_HAND, TILT_AND_TURN_RIGHT_HAND, FIXED_CASEMENT, NOTDEFINED)
@input  name             : str   item — Type name (also used as type_ref from Window component)
@input  lining_depth     : float item — Lining depth (m, optional)
@input  lining_thickness : float item — Lining thickness (m, optional)
@input  transom_thickness: float item — Transom thickness (m, optional)
@input  mullion_thickness: float item — Mullion thickness (m, optional)
@input  panel_depth      : float item — Panel depth (m, optional)
@input  panel_operation  : str   item — Panel operation (SIDEHUNGRIGHTHAND, SIDEHUUNGLEFTHAND, TILTANDTURNRIGHTHAND, TILTANDTURNLEFTHAND, TOPLEFTHUNG, BOTTOMHUNG, PIVOTHORIZONTAL, PIVOTVERTICAL, SLIDINGVERTICAL, SLIDINGHORIZONTAL, REMOVABLECASEMENT, FIXEDCASEMENT, OTHEROPERATION, NOTDEFINED, optional)
@input  properties       : str   item — JSON dict of user properties
@output out      : str item — Status message
@output json_out : str list — Envelope JSON strings: {"window_types":[{...}]}

Stateless: serializes window type parameters → keyed envelope JSON string.
Connect json_out to gh_merge, then gh_storey, then gh_build_json.
Use the name value as type_ref in the ifckit Window component.
"""

import json
from ifckit.elements.types import PendingWindowType
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
        wt = str(window_type).strip().upper() if window_type else "NOTDEFINED"
        wtype = PendingWindowType(
            overall_width=float(overall_width),
            overall_height=float(overall_height),
            window_type=wt,
            name=str(name) if name else "",
            lining_depth=_opt_float(lining_depth),
            lining_thickness=_opt_float(lining_thickness),
            transom_thickness=_opt_float(transom_thickness),
            mullion_thickness=_opt_float(mullion_thickness),
            panel_depth=_opt_float(panel_depth),
            panel_operation=str(panel_operation).strip() if panel_operation else None,
            properties=rk.parse_user_properties(properties),
        )
        json_outputs.append(json.dumps({"window_types": [wtype.to_dict()]}))
        messages.append(f"OK  WindowType '{wtype.name or wtype.type_key[:8]}'")
    except Exception as exc:
        messages.append(f"ERR WindowType: {exc}")

out = "\n".join(messages) if messages else "No window types processed."
json_out = json_outputs if json_outputs else []
