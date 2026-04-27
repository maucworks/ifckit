"""
Tests for ifckit.validator — full coverage of all validation rules.
"""
from __future__ import annotations

import math
import pytest

from ifckit.validator import validate, ValidationResult
from ifckit.geometry import Vec, Plane, Line, Arc
from ifckit.elements.building import PendingWall, PendingSlab
from ifckit.elements.structural import PendingBeam, PendingColumn, PendingRevolvedBeam
from ifckit.elements.bridge import (
    AlignmentSegment,
    BridgePartType,
    PendingAlignment,
    PendingBridgePart,
    PendingBridge,
)


# ---------------------------------------------------------------------------
# Fixtures — valid minimal objects
# ---------------------------------------------------------------------------

SQUARE = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0), Vec(0, 1, 0)]
BOX_PROFILE = [Vec(0, 0), Vec(0.2, 0), Vec(0.2, 0.2), Vec(0, 0.2)]
AXIS = Line(Vec(0, 0, 0), Vec(5, 0, 0))
PLANE = Plane.world_xy()


def _wall(**kw) -> PendingWall:
    defaults = dict(footprint=SQUARE, plane=PLANE, height=3.0, name="W")
    defaults.update(kw)
    return PendingWall(**defaults)


def _slab(**kw) -> PendingSlab:
    defaults = dict(footprint=SQUARE, plane=PLANE, thickness=0.3, name="S")
    defaults.update(kw)
    return PendingSlab(**defaults)


def _beam(**kw) -> PendingBeam:
    defaults = dict(axis=AXIS, profile=BOX_PROFILE, name="B")
    defaults.update(kw)
    return PendingBeam(**defaults)


def _column(**kw) -> PendingColumn:
    defaults = dict(axis=AXIS, profile=BOX_PROFILE, name="C")
    defaults.update(kw)
    return PendingColumn(**defaults)


def _arc() -> Arc:
    return Arc(center=Vec(0, 5, 0), normal=Vec(0, 0, 1),
               start=Vec(0, 0, 0), angle=math.pi / 2)


def _revolved_beam(**kw) -> PendingRevolvedBeam:
    defaults = dict(arc=_arc(), profile=BOX_PROFILE, name="RB")
    defaults.update(kw)
    return PendingRevolvedBeam(**defaults)


def _line_seg(start=(0, 0, 0), end=(10, 0, 0)) -> AlignmentSegment:
    return AlignmentSegment(geometry=Line(Vec(*start), Vec(*end)))


def _alignment(segments=None, **kw) -> PendingAlignment:
    if segments is None:
        segments = [_line_seg()]
    return PendingAlignment(segments=segments, name=kw.get("name", "A"))


def _bridge_part(**kw) -> PendingBridgePart:
    defaults = dict(part_type=BridgePartType.DECK, name="BP")
    defaults.update(kw)
    return PendingBridgePart(**defaults)


def _bridge(**kw) -> PendingBridge:
    defaults = dict(parts=[_bridge_part()], name="Br")
    defaults.update(kw)
    return PendingBridge(**defaults)


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------

class TestValidationResult:
    def test_ok_truthy(self):
        r = ValidationResult(ok=True)
        assert bool(r) is True

    def test_not_ok_falsy(self):
        r = ValidationResult(ok=False)
        assert bool(r) is False

    def test_default_empty_lists(self):
        r = ValidationResult(ok=True)
        assert r.errors == []
        assert r.warnings == []


# ---------------------------------------------------------------------------
# PendingWall
# ---------------------------------------------------------------------------

class TestValidateWall:
    def test_valid_wall_passes(self):
        assert validate(_wall()).ok

    def test_too_few_points(self):
        r = validate(_wall(footprint=[Vec(0, 0, 0), Vec(1, 0, 0)]))
        assert not r.ok
        assert any("3 points" in e for e in r.errors)

    def test_zero_area_footprint(self):
        # Collinear points → zero area
        pts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(2, 0, 0)]
        r = validate(_wall(footprint=pts))
        assert not r.ok
        assert any("area" in e for e in r.errors)

    def test_zero_height(self):
        r = validate(_wall(height=0.0))
        assert not r.ok
        assert any("height" in e for e in r.errors)

    def test_negative_height(self):
        r = validate(_wall(height=-1.0))
        assert not r.ok

    def test_small_height_warning(self):
        r = validate(_wall(height=0.001))
        assert r.ok        # warnings don't fail
        assert any("height" in w for w in r.warnings)

    def test_small_perimeter_warning(self):
        tiny = [Vec(0, 0, 0), Vec(0.001, 0, 0), Vec(0.001, 0.001, 0), Vec(0, 0.001, 0)]
        r = validate(_wall(footprint=tiny))
        assert r.ok
        assert any("perimeter" in w for w in r.warnings)


# ---------------------------------------------------------------------------
# PendingSlab
# ---------------------------------------------------------------------------

class TestValidateSlab:
    def test_valid_slab_passes(self):
        assert validate(_slab()).ok

    def test_too_few_points(self):
        r = validate(_slab(footprint=[Vec(0, 0, 0), Vec(1, 0, 0)]))
        assert not r.ok

    def test_zero_area(self):
        pts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(2, 0, 0)]
        r = validate(_slab(footprint=pts))
        assert not r.ok

    def test_zero_thickness(self):
        r = validate(_slab(thickness=0.0))
        assert not r.ok
        assert any("thickness" in e for e in r.errors)

    def test_negative_thickness(self):
        r = validate(_slab(thickness=-0.1))
        assert not r.ok

    def test_small_thickness_warning(self):
        r = validate(_slab(thickness=0.001))
        assert r.ok
        assert any("thickness" in w for w in r.warnings)


# ---------------------------------------------------------------------------
# PendingBeam
# ---------------------------------------------------------------------------

class TestValidateBeam:
    def test_valid_beam_passes(self):
        assert validate(_beam()).ok

    def test_zero_length_axis(self):
        zero_axis = Line(Vec(0, 0, 0), Vec(0, 0, 0))
        r = validate(_beam(axis=zero_axis))
        assert not r.ok
        assert any("axis length" in e for e in r.errors)

    def test_short_axis_warning(self):
        short_axis = Line(Vec(0, 0, 0), Vec(0.005, 0, 0))
        r = validate(_beam(axis=short_axis))
        assert r.ok
        assert any("axis is very short" in w for w in r.warnings)

    def test_too_few_profile_points(self):
        r = validate(_beam(profile=[Vec(0, 0, 0), Vec(0, 1, 0)]))
        assert not r.ok
        assert any("profile" in e for e in r.errors)

    def test_zero_area_profile(self):
        collinear = [Vec(0, 0, 0), Vec(0, 1, 0), Vec(0, 2, 0)]
        r = validate(_beam(profile=collinear))
        assert not r.ok
        assert any("area" in e for e in r.errors)


# ---------------------------------------------------------------------------
# PendingColumn
# ---------------------------------------------------------------------------

class TestValidateColumn:
    def test_valid_column_passes(self):
        assert validate(_column()).ok

    def test_zero_length_axis(self):
        r = validate(_column(axis=Line(Vec(0, 0, 0), Vec(0, 0, 0))))
        assert not r.ok

    def test_short_axis_warning(self):
        r = validate(_column(axis=Line(Vec(0, 0, 0), Vec(0, 0, 0.005))))
        assert r.ok
        assert r.warnings

    def test_too_few_profile_points(self):
        r = validate(_column(profile=[Vec(0, 0, 0), Vec(0, 1, 0)]))
        assert not r.ok

    def test_zero_area_profile(self):
        r = validate(_column(profile=[Vec(0, 0, 0), Vec(0, 1, 0), Vec(0, 2, 0)]))
        assert not r.ok


# ---------------------------------------------------------------------------
# PendingRevolvedBeam
# ---------------------------------------------------------------------------

class TestValidateRevolvedBeam:
    def test_valid_revolved_beam_passes(self):
        assert validate(_revolved_beam()).ok

    def test_zero_arc_angle(self):
        zero_arc = Arc(center=Vec(0, 5, 0), normal=Vec(0, 0, 1),
                       start=Vec(0, 0, 0), angle=0.0)
        r = validate(_revolved_beam(arc=zero_arc))
        assert not r.ok
        assert any("angle" in e for e in r.errors)

    def test_tiny_arc_warning(self):
        # arc_len = angle * radius = 1e-4 * 5 = 5e-4 m < _WARN_SHORT (0.01)
        tiny_arc = Arc(center=Vec(0, 5, 0), normal=Vec(0, 0, 1),
                       start=Vec(0, 0, 0), angle=1e-4)
        r = validate(_revolved_beam(arc=tiny_arc))
        assert r.ok
        assert any("arc length" in w for w in r.warnings)

    def test_too_few_profile_points(self):
        r = validate(_revolved_beam(profile=[Vec(0, 0, 0), Vec(0, 1, 0)]))
        assert not r.ok

    def test_zero_area_profile(self):
        r = validate(_revolved_beam(
            profile=[Vec(0, 0, 0), Vec(0, 1, 0), Vec(0, 2, 0)]
        ))
        assert not r.ok


# ---------------------------------------------------------------------------
# PendingAlignment
# ---------------------------------------------------------------------------

class TestValidateAlignment:
    def test_valid_alignment_passes(self):
        assert validate(_alignment()).ok

    def test_no_segments(self):
        r = validate(_alignment(segments=[]))
        assert not r.ok
        assert any("one segment" in e for e in r.errors)

    def test_zero_length_segment(self):
        zero_seg = AlignmentSegment(geometry=Line(Vec(0, 0, 0), Vec(0, 0, 0)))
        r = validate(_alignment(segments=[zero_seg]))
        assert not r.ok
        assert any("zero or negative length" in e for e in r.errors)

    def test_gap_between_segments(self):
        seg1 = _line_seg(start=(0, 0, 0), end=(10, 0, 0))
        seg2 = _line_seg(start=(20, 0, 0), end=(30, 0, 0))  # gap!
        r = validate(_alignment(segments=[seg1, seg2]))
        assert not r.ok
        assert any("gap" in e for e in r.errors)

    def test_continuous_segments_pass(self):
        seg1 = _line_seg(start=(0, 0, 0), end=(10, 0, 0))
        seg2 = _line_seg(start=(10, 0, 0), end=(20, 0, 0))
        r = validate(_alignment(segments=[seg1, seg2]))
        assert r.ok

    def test_arc_segment_passes(self):
        arc_seg = AlignmentSegment(geometry=_arc())
        r = validate(_alignment(segments=[arc_seg]))
        assert r.ok

    def test_short_segment_warning(self):
        short_seg = AlignmentSegment(geometry=Line(Vec(0, 0, 0), Vec(0.005, 0, 0)))
        r = validate(_alignment(segments=[short_seg]))
        assert r.ok
        assert any("very short" in w for w in r.warnings)

    def test_arc_then_line_continuous(self):
        # Arc ends at a known point; next Line starts there
        arc = Arc(center=Vec(0, 5, 0), normal=Vec(0, 0, 1),
                  start=Vec(0, 0, 0), angle=math.pi / 2)
        # arc.end should be roughly (5, 5, 0)
        arc_end = arc.end
        line_seg = AlignmentSegment(
            geometry=Line(Vec(arc_end.x, arc_end.y, arc_end.z),
                          Vec(arc_end.x + 10, arc_end.y, arc_end.z))
        )
        arc_seg = AlignmentSegment(geometry=arc)
        r = validate(_alignment(segments=[arc_seg, line_seg]))
        assert r.ok

    def test_arc_then_line_gap(self):
        arc = Arc(center=Vec(0, 5, 0), normal=Vec(0, 0, 1),
                  start=Vec(0, 0, 0), angle=math.pi / 2)
        # deliberate gap
        line_seg = _line_seg(start=(100, 0, 0), end=(110, 0, 0))
        r = validate(_alignment(segments=[AlignmentSegment(geometry=arc), line_seg]))
        assert not r.ok
        assert any("gap" in e for e in r.errors)


# ---------------------------------------------------------------------------
# PendingBridgePart
# ---------------------------------------------------------------------------

class TestValidateBridgePart:
    def test_valid_part_passes(self):
        assert validate(_bridge_part()).ok

    def test_part_with_valid_elements(self):
        part = PendingBridgePart(
            part_type=BridgePartType.DECK,
            elements=[_beam()],
            name="BP",
        )
        assert validate(part).ok

    def test_part_with_invalid_element_propagates(self):
        bad_beam = _beam(axis=Line(Vec(0, 0, 0), Vec(0, 0, 0)))
        part = PendingBridgePart(
            part_type=BridgePartType.DECK,
            elements=[bad_beam],
            name="BP",
        )
        r = validate(part)
        assert not r.ok
        assert any("element 0" in e for e in r.errors)

    def test_part_with_warning_element_propagates(self):
        """Warning from a child element must bubble up through BridgePart."""
        warn_beam = _beam(axis=Line(Vec(0, 0, 0), Vec(0.005, 0, 0)))  # short → warning
        part = PendingBridgePart(
            part_type=BridgePartType.DECK,
            elements=[warn_beam],
            name="BP",
        )
        r = validate(part)
        assert r.ok
        assert any("element 0" in w for w in r.warnings)

    def test_part_alignment_warning_propagates(self):
        short_seg = AlignmentSegment(geometry=Line(Vec(0, 0, 0), Vec(0.005, 0, 0)))
        warn_align = PendingAlignment(segments=[short_seg], name="Tiny")
        part = PendingBridgePart(
            part_type=BridgePartType.DECK,
            alignment=warn_align,
            name="BP",
        )
        r = validate(part)
        assert r.ok
        assert any("alignment" in w for w in r.warnings)

    def test_part_with_valid_alignment(self):
        part = PendingBridgePart(
            part_type=BridgePartType.DECK,
            alignment=_alignment(),
            name="BP",
        )
        assert validate(part).ok

    def test_part_with_invalid_alignment_propagates(self):
        bad_align = PendingAlignment(segments=[], name="Bad")
        part = PendingBridgePart(
            part_type=BridgePartType.DECK,
            alignment=bad_align,
            name="BP",
        )
        r = validate(part)
        assert not r.ok
        assert any("alignment" in e for e in r.errors)


# ---------------------------------------------------------------------------
# PendingBridge
# ---------------------------------------------------------------------------

class TestValidateBridge:
    def test_valid_bridge_passes(self):
        assert validate(_bridge()).ok

    def test_no_parts(self):
        r = validate(_bridge(parts=[]))
        assert not r.ok
        assert any("one part" in e for e in r.errors)

    def test_invalid_part_propagates(self):
        bad_part = PendingBridgePart(
            part_type=BridgePartType.DECK,
            elements=[_beam(axis=Line(Vec(0, 0, 0), Vec(0, 0, 0)))],
            name="Bad",
        )
        r = validate(_bridge(parts=[bad_part]))
        assert not r.ok
        assert any("part 0" in e for e in r.errors)

    def test_bridge_warning_part_propagates(self):
        warn_part = PendingBridgePart(
            part_type=BridgePartType.DECK,
            elements=[_beam(axis=Line(Vec(0, 0, 0), Vec(0.005, 0, 0)))],  # short
            name="WP",
        )
        r = validate(_bridge(parts=[warn_part]))
        assert r.ok
        assert any("part 0" in w for w in r.warnings)

    def test_bridge_alignment_warning_propagates(self):
        short_seg = AlignmentSegment(geometry=Line(Vec(0, 0, 0), Vec(0.005, 0, 0)))
        warn_align = PendingAlignment(segments=[short_seg], name="Tiny")
        br = PendingBridge(
            parts=[_bridge_part()],
            alignment=warn_align,
            name="Br",
        )
        r = validate(br)
        assert r.ok
        assert any("alignment" in w for w in r.warnings)

    def test_bridge_with_alignment(self):
        br = PendingBridge(
            parts=[_bridge_part()],
            alignment=_alignment(),
            name="Br",
        )
        assert validate(br).ok

    def test_bridge_with_invalid_alignment(self):
        bad_align = PendingAlignment(segments=[], name="Bad")
        br = PendingBridge(
            parts=[_bridge_part()],
            alignment=bad_align,
            name="Br",
        )
        r = validate(br)
        assert not r.ok
        assert any("alignment" in e for e in r.errors)


# ---------------------------------------------------------------------------
# Unknown type raises TypeError
# ---------------------------------------------------------------------------

class TestUnknownType:
    def test_unregistered_type_raises(self):
        from ifckit.elements.base import PendingElement

        class Alien(PendingElement):
            element_type = "alien"

            def to_dict(self):
                return {}

            @classmethod
            def from_dict(cls, d):
                return cls()

        with pytest.raises(TypeError, match="No validator"):
            validate(Alien())
