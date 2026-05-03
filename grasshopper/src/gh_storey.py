"""
gh_storey.py  —  GH Script component: "ifckit Storey"
======================================================

@component  nickname:"ifckit Storey"
@group "Assemble"
@input  envelopes    : str list  — Merged or individual envelope JSON strings
@input  storey_name  : str item  — Storey name e.g. "Ground Floor"
@input  elevation    : float item — Storey elevation (m, default 0.0)
@output out      : str item — Status message
@output json_out : str item — Storey bundle JSON for gh_build_json

Merges all input envelopes then wraps in a storey bundle:

    {
        "storey_name": "Ground Floor",
        "elevation": 0.0,
        "elements":     [...],   ← openings/fills nested inside elements
        "door_types":   [...],
        "window_types": [...]
    }

door_types / window_types are hoisted to root level by gh_build_json.
Openings and their door/window fills are nested inside each element.
Multiple Storey nodes can feed one gh_build_json (one per floor).
"""

import json
from ifckit import rhinokit as rk

out = ""
json_out = ""

# ── merge all input envelopes via shared helper ───────────────────────────────
merged = rk.merge_envelopes(envelopes) if envelopes else {}

# ── build storey bundle ──────────────────────────────────────────────────────
_name = str(storey_name) if storey_name else "Storey"
_elev = float(elevation) if elevation is not None else 0.0

bundle = {
    "storey_name": _name,
    "elevation": _elev,
    "elements":     merged.get("elements", []),
    "door_types":   merged.get("door_types", []),
    "window_types": merged.get("window_types", []),
}

n_elems = len(bundle["elements"])
n_openings = sum(len(e.get("openings", [])) for e in bundle["elements"] if isinstance(e, dict))
n_fills = sum(
    len(op.get("doors", [])) + len(op.get("windows", []))
    for e in bundle["elements"] if isinstance(e, dict)
    for op in e.get("openings", [])
)
counts = {}
if n_elems:    counts["elements"] = n_elems
if n_openings: counts["openings"] = n_openings
if n_fills:    counts["fills"] = n_fills
if bundle["door_types"]:   counts["door_types"] = len(bundle["door_types"])
if bundle["window_types"]: counts["window_types"] = len(bundle["window_types"])

summary = ", ".join(f"{v} {k}" for k, v in counts.items()) if counts else "empty"
out = f"Storey '{_name}' @ {_elev}m: {summary}"
json_out = json.dumps(bundle)
