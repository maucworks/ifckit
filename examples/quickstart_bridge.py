"""
quickstart_bridge.py
====================

Minimal runnable example: a single I-beam in an IFC4X3 bridge.

Profile dimensions (millimetres → converted to metres internally):
    w   = 300 mm   flange width
    h   = 600 mm   total height
    tw  =  10 mm   web thickness
    tf  =  10 mm   flange thickness
    anchor = 's'   origin at mid bottom of bottom flange

Beam length: 3000 mm = 3.0 m, placed along the X axis at Z = 0.

Run from the project root::

    python examples/quickstart_bridge.py
    # writes:  output/quickstart_bridge.ifc
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ifckit import (
    IfcModel, IfcSchema,
    PendingBeam, Vec, Line,
    BridgePartType, validate,
    IBeamProfile,
)
from ifckit.builders import default_registry
from ifckit.builders._geom import get_body_context


# ---------------------------------------------------------------------------
# Dimensions in metres (convert from mm)
# ---------------------------------------------------------------------------

W  = 300 / 1000   # 0.300 m  flange width
H  = 600 / 1000   # 0.600 m  total height
TW =  10 / 1000   # 0.010 m  web thickness
TF =  10 / 1000   # 0.010 m  flange thickness
L  = 3000 / 1000  # 3.000 m  beam length

profile = IBeamProfile(
    height=H,
    width=W,
    web_thickness=TW,
    flange_thickness=TF,
    anchor='s',
)

model  = IfcModel(name="Bridge Quickstart", schema=IfcSchema.IFC4X3, author="you")
site   = model.add_site("Site A")
bridge = model.add_bridge(site, "Main Bridge")
deck   = model.add_bridge_part(bridge, "Deck", BridgePartType.DECK.value)

beam = PendingBeam(
    axis=Line(Vec(0, 0, 0), Vec(L, 0, 0)),
    profile=[Vec(y, z) for y, z in profile.get_profile_points()],
    name="I-Beam 300x600x10",
)

result = validate(beam)
assert result.ok, result.errors

reg = default_registry()
ctx = get_body_context(model.ifc_file)
reg.get("basic_beam").build(model.ifc_file, beam, deck.entity, ctx)

os.makedirs("output", exist_ok=True)
model.save("output/quickstart_bridge.ifc")
print("Saved: output/quickstart_bridge.ifc")
print(f"  Profile area: {profile.area * 1e6:.0f} mm²")
