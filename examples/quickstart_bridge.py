"""
quickstart_bridge.py
====================

Minimal runnable example: a single I-beam in an IFC4X3 bridge.

All dimensions are in millimetres. The model is created with
LengthUnit.MILLIMETRE so IFC viewers interpret the values correctly.

Profile:
    w   = 300 mm   flange width
    h   = 600 mm   total height
    tw  =  10 mm   web thickness
    tf  =  10 mm   flange thickness
    anchor = 's'   origin at mid bottom of bottom flange

Beam length: 3000 mm, placed along the X axis at Z = 0.

Run from the project root::

    python examples/quickstart_bridge.py
    # writes:  output/quickstart_bridge.ifc
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ifckit import (
    IfcModel,
    IfcSchema,
    LengthUnit,
    PendingBeam,
    Vec,
    Plane,
    Line,
    BridgePartType,
    IBeamProfile,
)

# ---------------------------------------------------------------------------
# Model — millimetres throughout, no conversion needed
# ---------------------------------------------------------------------------

model = IfcModel(
    name="Bridge Quickstart",
    schema=IfcSchema.IFC4X3,
    author="you",
    unit=LengthUnit.MILLIMETRE,
)
bridge = model.add_site("Site A").add_bridge("Main Bridge")
deck = bridge.add_bridge_part("Deck", BridgePartType.DECK.value)

profile = IBeamProfile(
    height=600,
    width=300,
    web_thickness=10,
    flange_thickness=10,
    anchor="nw",
)

# profile object passed directly — no list comprehension needed
beam = PendingBeam(
    axis=Line(Vec(0, 0, 0), Vec(3000, 0, 0)),
    up=Vec(0, 1, 1),
    profile=profile,
    name="I-Beam 300x600x10",
)

beam1 = PendingBeam(
    axis=Line(Vec(0, 500, 0), Vec(3000, 500, 0)),
    profile=profile,
    start_clip=Plane(Vec(600, 0, 0), Vec(1, 0, 1), Vec(0, 1, 0)),  # 45° mitre at start
    end_clip=Plane(Vec(2400, 0, 0), Vec(-1, 0, 1), Vec(0, -1, 0)),  # 45° mitre at end
    name="I-Beam clipped",
)

# Validate and build in one call — raises ValueError if invalid
deck.add(beam)
deck.add(beam1)

os.makedirs("output", exist_ok=True)
model.save("output/quickstart_bridge.ifc")
print("Saved: output/quickstart_bridge.ifc")
print(f"  Profile area: {profile.area:.0f} mm²")
