"""
gh_create_beam.py  —  GH Script component: "Create IFC Beam"
===============================================================

Stateless component: serializes beam lines to JSON strings.

Component inputs
----------------
beam_lines   : list  — One or more Rhino Line objects (beam axes).
profile_pts  : list  — Rhino Point3d objects defining the cross-section
                       polygon in the local XY plane (X = width, Y = up).
                       All beams share the same profile shape.
                       Minimum 3 points; no closing duplicate needed.
name         : str   — Optional element name prefix.

Component outputs
-----------------
out     : str  — Status message.
json_out : list — List of JSON strings (one per beam).

Profile example — 200 × 300 mm rectangle (model unit = mm):
    profile_pts = [(-100,0,0), (100,0,0), (100,300,0), (-100,300,0)]
"""

import json
from ifckit import PendingBeam, Line, Vec


def _pt(pt):
    return Vec(pt.X, pt.Y, pt.Z)


def _line(ln):
    return Line(start=_pt(ln.From), end=_pt(ln.To))


def _profile(pts):
    vecs = [_pt(p) for p in pts]
    if len(vecs) > 1:
        f, l = vecs[0], vecs[-1]
        if abs(f.x - l.x) < 1e-6 and abs(f.y - l.y) < 1e-6:
            vecs = vecs[:-1]
    return vecs


messages = []
json_outputs = []

if beam_lines and profile_pts:
    lines = beam_lines if hasattr(beam_lines, "__iter__") else [beam_lines]
    prof = _profile(profile_pts)

    for i, ln in enumerate(lines):
        if ln is None:
            continue
        try:
            el_name = f"{name or 'Beam'}-{i + 1}"
            beam = PendingBeam(axis=_line(ln), profile=prof, name=el_name)
            json_outputs.append(beam.to_json())
            messages.append(f"OK  {el_name}")
        except Exception as exc:
            messages.append(f"ERR line[{i}]: {exc}")

out = "\n".join(messages) if messages else "No beams processed."
json_out = json_outputs if json_outputs else []