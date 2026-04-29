"""
gh_collector.py  —  GH Script component: "Collect JSON Elements"
==================================================================

Stateless component: merges multiple JSON element lists and adds storey info.

Flow:  [Walls JSON] ─┐
                   ──┼──→ [Collector] ──→ [Combined JSON] ──→ [Export]
     [Beams JSON] ──┘

No sticky, no state - pure data flow.

Component inputs
----------------
walls_json  : list — List of JSON strings from CreateWalls.
beams_json  : list — List of JSON strings from CreateBeams.
storey_name : str  — Name of the storey for all elements.
                     Example: "Ground Floor", "Floor 1", etc.

Component outputs
-----------------
out     : str  — Status message.
json_out : str — JSON string with storey-wrapped elements.
                 Connect directly to Export.
"""

import json

messages = []
all_elements = []

if walls_json:
    walls = walls_json if isinstance(walls_json, list) else [walls_json]
    all_elements.extend([e for e in walls if e])
    messages.append(f"Added {len(walls)} walls")

if beams_json:
    beams = beams_json if isinstance(beams_json, list) else [beams_json]
    all_elements.extend([e for e in beams if e])
    messages.append(f"Added {len(beams)} beams")

out = ", ".join(messages) if messages else "No elements"

output_data = {
    "storeys": {
        storey_name if storey_name else "Default": all_elements
    }
}
json_out = json.dumps(output_data, separators=(",", ":"))