"""
simple_bridge.py
================

Runnable example: a modular bridge in IFC4X3 with:
  - A composite horizontal alignment (two tangents + a circular arc)
  - One bridge with a deck part and a substructure part
  - Longitudinal deck beams placed along the bridge axis

Run from the project root::

    python examples/simple_bridge.py
    # writes:  output/simple_bridge.ifc

The output can be opened in any IFC4X3-capable viewer (e.g. BlenderBIM).
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ifckit import (
    IfcModel, IfcSchema,
    PendingAlignment, PendingBeam, PendingSlab,
    AlignmentSegment, BridgePartType,
    Vec, Plane, Line, Arc,
    validate,
)
from ifckit.builders import default_registry
from ifckit.builders._geom import get_body_context


# ---------------------------------------------------------------------------
# Bridge parameters
# ---------------------------------------------------------------------------

SPAN_LENGTH = 50.0          # m  straight approach tangent
CURVE_RADIUS = 40.0         # m  horizontal curve
CURVE_ANGLE = math.pi / 4   # 45° right-hand curve
EXIT_TANGENT = 30.0         # m  exit tangent
DECK_WIDTH = 8.0            # m
BEAM_SPACING = 2.0          # m  between longitudinal beams
NUM_BEAMS = int(DECK_WIDTH / BEAM_SPACING)

# Rectangular beam profile in cross-section XY plane:
# X = horizontal (width), Y = vertical (height), centred on (0,0)
BEAM_PROFILE = [
    Vec(-0.2, -0.3),
    Vec( 0.2, -0.3),
    Vec( 0.2,  0.3),
    Vec(-0.2,  0.3),
]


def build_alignment() -> PendingAlignment:
    """
    Composite alignment:
        Tangent 1  (0,0,0) → (50,0,0)          straight 50 m
        Arc        R=40 m, right-hand 45°       starts at (50,0,0)
        Tangent 2  follows the arc exit direction, 30 m
    """
    # Segment 1: straight tangent along X
    seg1 = AlignmentSegment(
        geometry=Line(Vec(0, 0, 0), Vec(SPAN_LENGTH, 0, 0)),
        station_start=0.0,
    )

    # Segment 2: right-hand circular arc (negative angle = CW in XY)
    # Center is perpendicular-right of the tangent at start of arc
    # Tangent at (50,0) is +X, right is -Y, so center = (50, -CURVE_RADIUS, 0)
    arc_center = Vec(SPAN_LENGTH, -CURVE_RADIUS, 0)
    arc = Arc(
        center=arc_center,
        normal=Vec(0, 0, 1),
        start=Vec(SPAN_LENGTH, 0, 0),
        angle=-CURVE_ANGLE,   # CW
    )
    seg2 = AlignmentSegment(geometry=arc, station_start=SPAN_LENGTH)

    # Segment 3: exit tangent — starts at arc.end, direction rotated by -CURVE_ANGLE
    arc_end = arc.end
    exit_dir_x = math.cos(-CURVE_ANGLE)
    exit_dir_y = math.sin(-CURVE_ANGLE)
    seg3 = AlignmentSegment(
        geometry=Line(
            start=Vec(arc_end.x, arc_end.y, arc_end.z),
            end=Vec(
                arc_end.x + EXIT_TANGENT * exit_dir_x,
                arc_end.y + EXIT_TANGENT * exit_dir_y,
                arc_end.z,
            ),
        ),
        station_start=SPAN_LENGTH + abs(CURVE_ANGLE) * CURVE_RADIUS,
    )

    alignment = PendingAlignment(
        segments=[seg1, seg2, seg3],
        name="BridgeAlignment",
    )

    result = validate(alignment)
    assert result.ok, f"Alignment validation failed: {result.errors}"
    for w in result.warnings:
        print(f"  [WARN] {w}")

    return alignment


def build_deck_beams(model, deck, reg, ctx) -> None:
    """Add longitudinal deck beams (simplified: parallel to bridge X-axis)."""
    total_length = SPAN_LENGTH + abs(CURVE_ANGLE) * CURVE_RADIUS + EXIT_TANGENT
    y_start = -(DECK_WIDTH / 2)

    for i in range(NUM_BEAMS + 1):
        y = y_start + i * BEAM_SPACING
        beam = PendingBeam(
            axis=Line(Vec(0, y, 0), Vec(total_length * 0.6, y, 0)),
            profile=BEAM_PROFILE,
            name=f"DeckBeam_{i}",
        )
        result = validate(beam)
        assert result.ok, f"Beam validation failed: {result.errors}"
        reg.get("basic_beam").build(model.ifc_file, beam, deck.entity, ctx)


def main(output_path: str = "output/simple_bridge.ifc") -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    model = IfcModel(
        name="ModuloBrug",
        schema=IfcSchema.IFC4X3,
        author="ifckit example",
    )

    site = model.add_site("Bridge Site")
    bridge = model.add_bridge(site, "Modulo Brug")
    deck = model.add_bridge_part(bridge, "Deck", BridgePartType.DECK.value)
    sub = model.add_bridge_part(bridge, "Substructure", BridgePartType.SUBSTRUCTURE.value)
    align_handle = model.add_alignment(site, "BridgeAlignment")

    reg = default_registry()
    ctx = get_body_context(model.ifc_file)

    # Build and attach alignment geometry
    alignment = build_alignment()
    reg.get("alignment").build(
        model.ifc_file, alignment, align_handle.entity, None
    )

    # Add deck beams
    build_deck_beams(model, deck, reg, ctx)

    model.save(output_path)
    print(f"Saved: {output_path}")

    f = model.ifc_file
    print(f"  IfcBridge:              {len(f.by_type('IfcBridge'))}")
    print(f"  IfcBridgePart:          {len(f.by_type('IfcBridgePart'))}")
    print(f"  IfcAlignment:           {len(f.by_type('IfcAlignment'))}")
    print(f"  IfcAlignmentSegment:    {len(f.by_type('IfcAlignmentSegment'))}")
    print(f"  IfcBeam:                {len(f.by_type('IfcBeam'))}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "output/simple_bridge.ifc"
    main(out)
