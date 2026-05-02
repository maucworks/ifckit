"""
gh_collector.py — GH Script: "Collect Elements"
================================================

One collector per storey. Multiple collectors feed into Build JSON.

Flow:  [Collector A] ──┐
       [Collector B] ──┼──→ [Build JSON] ──→ [Export/Preview]
       [Collector C] ──┘

Inputs
------
elements      : list  — List of JSON strings (walls, beams, etc.)
storey_name   : str   — Storey name, e.g. "Ground Floor"
elevation     : float — Storey floor elevation in model units (default 0.0)

Output
------
out      : str — Status message.
json_out : str — {"storey_name": ..., "elevation": ..., "elements": [...]}
"""

import json

messages = []
all_elements = []

if elements:
    elems = elements if isinstance(elements, list) else [elements]
    all_elements.extend([e for e in elems if e])
    messages.append("Added {} elements".format(len(all_elements)))

out = ", ".join(messages) if messages else "No elements"

sname = str(storey_name) if storey_name else "Default"
elev = float(elevation) if elevation is not None else 0.0

output_data = {
    "storey_name": sname,
    "elevation": elev,
    "elements": all_elements,
}
json_out = json.dumps(output_data, separators=(",", ":"))

print(out)
