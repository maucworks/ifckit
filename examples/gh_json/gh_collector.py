"""
gh_collector.py — GH Script: "Collect Elements"
================================================

Stateless: merges any element JSON lists into storey structure.

Flow:  [Walls JSON] ─┐
                   ──┼──→ [Collector] ──→ [JSON] ──→ [Export]
     [Beams JSON] ──┘
     [Columns JSON] ─┘

No sticky, no state - pure data flow.

Inputs
------
elements : list — List of JSON strings (any element type: walls, beams, etc.)
storey   : str  — Storey name, e.g. "Ground Floor"

Output
------
out     : str  — Status message.
json_out : str — JSON with {"storeys": {storey_name: elements}}
"""

import json

if not elements:
    out = "No elements"
    json_out = ""
elif not storey:
    out = "No storey name"
    json_out = ""
else:
    flat_elements = elements if isinstance(elements, list) else [elements]
    valid = [e for e in flat_elements if e]

    out = f"Collected {len(valid)} elements into '{storey}'"
    json_out = json.dumps({"storeys": {storey: valid}}, separators=(",", ":"))

print(out)