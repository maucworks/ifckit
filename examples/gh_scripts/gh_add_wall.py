"""
gh_add_wall.py  —  GH Script component: "Add IFC Wall"
=======================================================

Paste the contents of this file into a Grasshopper Python 3 Script
component (Rhino 8+).

Execution chain
---------------
Wire the ``done`` output of the previous component (Init or another
element component) to the ``trigger`` input of this component.  Wire
the ``done`` output of this component to the ``trigger`` of the next.

    [Init done] --> [AddWall trigger]
                    [AddWall done] --> [AddBeam trigger / Export trigger]

This guarantees that Init has completed (and sc.sticky is populated)
before any wall is added.

Component inputs
----------------
trigger     : bool  — Wire from previous component's ``done`` output.
                      This component does nothing unless trigger is True.
clear       : bool  — If True, remove all existing walls before adding new ones.
                      Use this when editing geometry to avoid accumulating elements.
wall_curves : list  — One or more closed planar Rhino curves (Polyline or
                      PolylineCurve) representing the wall base footprints.
height      : float — Wall height in the model's length unit.
name        : str   — Optional element name prefix.

Component outputs
-----------------
done : bool — True when all walls have been added to the storey.
              Wire to the next component's ``trigger`` input.
out  : str  — Status / error messages.
"""

import sys
import scriptcontext as sc

from ifckit import PendingWall, validate
from ifckit.geometry import Vec, Plane

# ── converters ────────────────────────────────────────────────────────────────


def _pt(pt):
    return Vec(pt.X, pt.Y, pt.Z)


def _polyline_to_footprint(crv):
    pl = crv.ToPolyline() if hasattr(crv, "ToPolyline") else crv
    pts = [_pt(p) for p in pl]
    if len(pts) > 1:
        f, l = pts[0], pts[-1]
        if abs(f.x - l.x) < 1e-6 and abs(f.y - l.y) < 1e-6:
            pts = pts[:-1]
    return pts


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

    curves = wall_curves if hasattr(wall_curves, "__iter__") else [wall_curves]

    for i, crv in enumerate(curves):
        if crv is None:
            continue
        try:
            footprint = _polyline_to_footprint(crv)
            el_name = f"{name or 'Wall'}-{i + 1}"
            wall = PendingWall(
                footprint=footprint,
                plane=Plane.world_xy(),
                height=float(height),
                name=el_name,
            )
            result = validate(wall)
            if result.ok:
                storey.add(wall)
                messages.append(f"OK  {el_name}")
            else:
                messages.append(f"ERR {el_name}: {', '.join(result.errors)}")
            for w in result.warnings:
                messages.append(f"WARN {el_name}: {w}")
        except Exception as exc:
            messages.append(f"ERR curve[{i}]: {exc}")

    done = True
    out = "\n".join(messages) if messages else "No walls processed."
