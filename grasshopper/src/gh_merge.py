"""
gh_merge.py  —  GH Script component: "ifckit Merge"
====================================================

@component  nickname:"ifckit Merge"
@group "Assemble"
@input  envelopes : str list — Any mix of keyed envelope JSON strings from element nodes
@output out      : str item — Status message
@output json_out : str item — Single merged envelope JSON string

Merges any number of keyed envelopes by appending lists per key.

Supported keys: elements, openings, doors, windows, door_types, window_types.
No deduplication. Order preserved. Unknown keys passed through unchanged.

Example input envelopes:
    {"elements": [...]}      ← from Wall / Slab / Beam
    {"openings": [...]}      ← from Opening
    {"doors":    [...]}      ← from Door
    {"window_types": [...]}  ← from WindowType

Output:
    {"elements": [...], "openings": [...], "doors": [...], "window_types": [...]}
"""

import json
from ifckit import rhinokit as rk

out = ""
json_out = ""

if envelopes:
    try:
        merged = rk.merge_envelopes(envelopes)
        counts = {k: len(v) for k, v in merged.items() if isinstance(v, list) and v}
        summary = ", ".join(f"{v} {k}" for k, v in counts.items()) if counts else "empty"
        out = f"Merged: {summary}"
        json_out = json.dumps(merged)
    except Exception as exc:
        out = f"ERR: {exc}"
else:
    out = "No envelopes."
