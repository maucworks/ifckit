"""
gh_add_beam.py  —  GH Script component: "Add IFC Beam"
=======================================================

Paste the contents of this file into a Grasshopper Python 3 Script
component (Rhino 8+).

Execution chain
---------------
    [Init done] --> [AddWall done] --> [AddBeam trigger]
                                       [AddBeam done] --> [Export trigger]

Component inputs
----------------
trigger      : bool  — Wire from previous component's ``done`` output.
clear        : bool  — If True, remove all existing beams before adding new ones.
                       Use this when editing geometry to avoid accumulating elements.
beam_lines   : list  — One or more Rhino Line objects (beam axes).
profile_pts  : list  — Rhino Point3d objects defining the cross-section
                       polygon in the local XY plane (X = width, Y = up).
                       All beams share the same profile shape.
                       Minimum 3 points; no closing duplicate needed.
name         : str   — Optional element name prefix.

Component outputs
-----------------
done : bool — True when all beams have been added to the storey.
out  : str  — Status / error messages.

Profile example — 200 × 300 mm rectangle (model unit = mm):
    profile_pts = [(-100,0,0), (100,0,0), (100,300,0), (-100,300,0)]
"""

import sys
import scriptcontext as sc

from ifckit import PendingBeam, validate
from ifckit.geometry import Vec, Line

# ── converters ────────────────────────────────────────────────────────────────


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


# ── main ──────────────────────────────────────────────────────────────────────

done = False
messages = []

if not trigger:
    out = "Waiting for trigger."
elif "ifckit_storey" not in sc.sticky:
    out = "ERROR: no model in sc.sticky — run Init first (reset=True)."
else:
    storey = sc.sticky["ifckit_storey"]

    if clear:
        removed = storey.clear()
        messages.append(f"Cleared {removed} existing elements.")

    lines = beam_lines if hasattr(beam_lines, "__iter__") else [beam_lines]
    prof = _profile(profile_pts)

    for i, ln in enumerate(lines):
        if ln is None:
            continue
        try:
            el_name = f"{name or 'Beam'}-{i + 1}"
            beam = PendingBeam(axis=_line(ln), profile=prof, name=el_name)
            result = validate(beam)
            if result.ok:
                storey.add(beam)
                messages.append(f"OK  {el_name}")
            else:
                messages.append(f"ERR {el_name}: {', '.join(result.errors)}")
            for w in result.warnings:
                messages.append(f"WARN {el_name}: {w}")
        except Exception as exc:
            messages.append(f"ERR line[{i}]: {exc}")

    done = True
    out = "\n".join(messages) if messages else "No beams processed."
