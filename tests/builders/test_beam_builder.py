"""Tests for ExtrudedElementBuilder (beam + column) and RevolvedBeamBuilder."""

import math
import pytest
import ifcopenshell

from ifckit.geometry import Vec, Line, Arc, Path, Plane
from ifckit.elements.structural import PendingBeam, PendingColumn, PendingRevolvedBeam
from ifckit.builders.beam_factory import beam_from_path
from ifckit.builders.extruded import ExtrudedElementBuilder
from ifckit.builders.revolved_beam import RevolvedBeamBuilder

_beam_builder = ExtrudedElementBuilder("basic_beam", "IfcBeam")
_column_builder = ExtrudedElementBuilder("basic_column", "IfcColumn")


# Square cross-section 0.2 × 0.2, centred at origin
SQUARE_PROFILE = [
    Vec(-0.1, -0.1, 0),
    Vec(0.1, -0.1, 0),
    Vec(0.1, 0.1, 0),
    Vec(-0.1, 0.1, 0),
]

BEAM_AXIS = Line(Vec(0, 0, 0), Vec(5, 0, 0))
COL_AXIS = Line(Vec(0, 0, 0), Vec(0, 0, 3))
QUARTER_ARC = Arc(Vec(0, 1, 0), Vec(0, 0, 1), Vec(0, 0, 0), math.pi / 2)


class TestBeamBuilder:
    def test_produces_ifc_beam(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingBeam(BEAM_AXIS, SQUARE_PROFILE, name="B1")
        entity = _beam_builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        assert entity.is_a("IfcBeam")
        assert entity.Name == "B1"

    def test_beam_has_representation(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingBeam(BEAM_AXIS, SQUARE_PROFILE)
        entity = _beam_builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        assert entity.Representation is not None

    def test_beam_has_extruded_solid(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingBeam(BEAM_AXIS, SQUARE_PROFILE)
        _beam_builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        solids = ifc4_model.ifc_file.by_type("IfcExtrudedAreaSolid")
        assert len(solids) == 1
        assert solids[0].Depth == pytest.approx(5.0)

    def test_beam_contained_in_storey(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingBeam(BEAM_AXIS, SQUARE_PROFILE)
        _beam_builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        rels = ifc4_model.ifc_file.by_type("IfcRelContainedInSpatialStructure")
        assert len(rels) == 1

    def test_beam_has_profile(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingBeam(BEAM_AXIS, SQUARE_PROFILE)
        _beam_builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        profiles = ifc4_model.ifc_file.by_type("IfcArbitraryClosedProfileDef")
        assert len(profiles) == 1

    def test_file_parses_after_save(self, ifc4_model, ifc4_storey, body_context, tmp_path):
        pending = PendingBeam(BEAM_AXIS, SQUARE_PROFILE)
        _beam_builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        path = str(tmp_path / "beam.ifc")
        ifc4_model.save(path)
        reopened = ifcopenshell.open(path)
        assert len(reopened.by_type("IfcBeam")) == 1


class TestBeamClipping:
    """Tests for start_clip / end_clip on PendingBeam."""

    def test_start_clip_produces_boolean_result(self, ifc4_model, ifc4_storey, body_context):
        # Perpendicular clip at x=1.0 from start, keeping +X side
        clip = Plane(Vec(1, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))  # z_axis = +X = keep dir
        pending = PendingBeam(BEAM_AXIS, SQUARE_PROFILE, start_clip=clip)
        _beam_builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        results = ifc4_model.ifc_file.by_type("IfcBooleanClippingResult")
        assert len(results) == 1

    def test_end_clip_produces_boolean_result(self, ifc4_model, ifc4_storey, body_context):
        clip = Plane(Vec(4, 0, 0), Vec(-1, 0, 0), Vec(0, 0, 1))  # z_axis = -X = keep start side
        pending = PendingBeam(BEAM_AXIS, SQUARE_PROFILE, end_clip=clip)
        _beam_builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        results = ifc4_model.ifc_file.by_type("IfcBooleanClippingResult")
        assert len(results) == 1

    def test_both_clips_produce_two_boolean_results(self, ifc4_model, ifc4_storey, body_context):
        start_clip = Plane(Vec(1, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))
        end_clip = Plane(Vec(4, 0, 0), Vec(-1, 0, 0), Vec(0, 0, 1))
        pending = PendingBeam(BEAM_AXIS, SQUARE_PROFILE, start_clip=start_clip, end_clip=end_clip)
        _beam_builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        results = ifc4_model.ifc_file.by_type("IfcBooleanClippingResult")
        assert len(results) == 2

    def test_no_clip_no_boolean_result(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingBeam(BEAM_AXIS, SQUARE_PROFILE)
        _beam_builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        assert len(ifc4_model.ifc_file.by_type("IfcBooleanClippingResult")) == 0

    def test_clipped_beam_parses_after_save(self, ifc4_model, ifc4_storey, body_context, tmp_path):
        clip = Plane(Vec(1, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))
        pending = PendingBeam(BEAM_AXIS, SQUARE_PROFILE, start_clip=clip)
        _beam_builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        path = str(tmp_path / "clipped_beam.ifc")
        ifc4_model.save(path)
        reopened = ifcopenshell.open(path)
        assert len(reopened.by_type("IfcBeam")) == 1
        assert len(reopened.by_type("IfcBooleanClippingResult")) == 1


class TestColumnBuilder:
    def test_produces_ifc_column(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingColumn(COL_AXIS, SQUARE_PROFILE, name="C1")
        entity = _column_builder.build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.is_a("IfcColumn")
        assert entity.Name == "C1"

    def test_column_depth_matches_axis(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingColumn(COL_AXIS, SQUARE_PROFILE)
        _column_builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        solids = ifc4_model.ifc_file.by_type("IfcExtrudedAreaSolid")
        assert solids[0].Depth == pytest.approx(3.0)

    def test_column_has_representation(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingColumn(COL_AXIS, SQUARE_PROFILE)
        entity = _column_builder.build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.Representation is not None

    def test_column_contained_in_storey(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingColumn(COL_AXIS, SQUARE_PROFILE)
        _column_builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        rels = ifc4_model.ifc_file.by_type("IfcRelContainedInSpatialStructure")
        assert len(rels) == 1

    def test_file_parses_after_save(self, ifc4_model, ifc4_storey, body_context, tmp_path):
        pending = PendingColumn(COL_AXIS, SQUARE_PROFILE)
        _column_builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        path = str(tmp_path / "col.ifc")
        ifc4_model.save(path)
        reopened = ifcopenshell.open(path)
        assert len(reopened.by_type("IfcColumn")) == 1


class TestRevolvedBeamBuilder:
    def test_produces_ifc_beam(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingRevolvedBeam(QUARTER_ARC, SQUARE_PROFILE, name="RB1")
        entity = RevolvedBeamBuilder().build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.is_a("IfcBeam")
        assert entity.Name == "RB1"

    def test_has_revolved_solid(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingRevolvedBeam(QUARTER_ARC, SQUARE_PROFILE)
        RevolvedBeamBuilder().build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        solids = ifc4_model.ifc_file.by_type("IfcRevolvedAreaSolid")
        assert len(solids) == 1

    def test_revolved_solid_angle(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingRevolvedBeam(QUARTER_ARC, SQUARE_PROFILE)
        RevolvedBeamBuilder().build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        solid = ifc4_model.ifc_file.by_type("IfcRevolvedAreaSolid")[0]
        assert solid.Angle == pytest.approx(math.pi / 2)

    def test_has_representation(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingRevolvedBeam(QUARTER_ARC, SQUARE_PROFILE)
        entity = RevolvedBeamBuilder().build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.Representation is not None

    def test_180_arc(self, ifc4_model, ifc4_storey, body_context):
        """180° arc should produce a half-circle revolved beam."""
        half_arc = Arc(Vec(0, 1, 0), Vec(0, 0, 1), Vec(0, 0, 0), math.pi)
        pending = PendingRevolvedBeam(half_arc, SQUARE_PROFILE)
        entity = RevolvedBeamBuilder().build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.is_a("IfcBeam")
        solid = ifc4_model.ifc_file.by_type("IfcRevolvedAreaSolid")[0]
        assert solid.Angle == pytest.approx(math.pi)  # positive angle, direction via axis orientation

    def test_file_parses_after_save(self, ifc4_model, ifc4_storey, body_context, tmp_path):
        pending = PendingRevolvedBeam(QUARTER_ARC, SQUARE_PROFILE)
        RevolvedBeamBuilder().build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        path = str(tmp_path / "revbeam.ifc")
        ifc4_model.save(path)
        reopened = ifcopenshell.open(path)
        assert len(reopened.by_type("IfcBeam")) == 1
        assert len(reopened.by_type("IfcRevolvedAreaSolid")) == 1

    def test_revolution_axis_is_local_y_of_rev_pos(self, ifc4_model, ifc4_storey, body_context):
        """The IfcAxis1Placement for the revolution axis must point along local Y of rev_pos.

        rev_pos is constructed with Axis=tangent_at_start, RefDirection=radial.
        The implicit Y of that frame is arc.normal, so (0,1,0) in that local frame
        resolves to arc.normal in world space — i.e. the correct revolution axis.
        This test verifies the IFC entity is literally (0,1,0).
        """
        pending = PendingRevolvedBeam(QUARTER_ARC, SQUARE_PROFILE)
        RevolvedBeamBuilder().build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        solid = ifc4_model.ifc_file.by_type("IfcRevolvedAreaSolid")[0]
        axis1 = solid.Axis  # IfcAxis1Placement
        ratios = list(axis1.Axis.DirectionRatios)
        assert ratios == pytest.approx([0.0, 1.0, 0.0], abs=1e-6)

    def test_rev_pos_ref_direction_is_radial(self, ifc4_model, ifc4_storey, body_context):
        """rev_pos RefDirection must be the radial direction (start → center, i.e. start - center normalized)."""
        arc = QUARTER_ARC
        # cpx = (arc.start - arc.center).normalized() = (0,0,0)-(0,1,0) normalized = (0,-1,0)
        cpx = (arc.start - arc.center).normalized()
        pending = PendingRevolvedBeam(arc, SQUARE_PROFILE)
        RevolvedBeamBuilder().build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        solid = ifc4_model.ifc_file.by_type("IfcRevolvedAreaSolid")[0]
        rev_pos = solid.Position  # IfcAxis2Placement3D
        ref_dir = list(rev_pos.RefDirection.DirectionRatios)
        assert ref_dir == pytest.approx([cpx.x, cpx.y, cpx.z], abs=1e-6)

    def test_non_horizontal_arc_produces_valid_solid(self, ifc4_model, ifc4_storey, body_context):
        """An arc in a non-horizontal plane (normal != world Y) must still build correctly."""
        # Arc in the XZ plane (normal = world -Y)
        arc_xz = Arc(Vec(0, 0, 1), Vec(0, -1, 0), Vec(0, 0, 0), math.pi / 2)
        pending = PendingRevolvedBeam(arc_xz, SQUARE_PROFILE)
        entity = RevolvedBeamBuilder().build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.is_a("IfcBeam")
        solids = ifc4_model.ifc_file.by_type("IfcRevolvedAreaSolid")
        assert len(solids) == 1


class TestRevolvedBeamClipping:
    """Tests for start_clip / end_clip on PendingRevolvedBeam."""

    def test_start_clip_produces_boolean_result(self, ifc4_model, ifc4_storey, body_context):
        # Clip at x=0.3 keeping +X side — cuts off the start of the arc
        clip = Plane.from_origin_and_normal(Vec(0.3, 0, 0), Vec(-1, 0, 0))
        pending = PendingRevolvedBeam(QUARTER_ARC, SQUARE_PROFILE, start_clip=clip)
        RevolvedBeamBuilder().build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        results = ifc4_model.ifc_file.by_type("IfcBooleanClippingResult")
        assert len(results) == 1

    def test_end_clip_produces_boolean_result(self, ifc4_model, ifc4_storey, body_context):
        # Clip at x=0.7 keeping -X side — cuts off the end of the arc
        clip = Plane.from_origin_and_normal(Vec(0.7, 0, 0), Vec(1, 0, 0))
        pending = PendingRevolvedBeam(QUARTER_ARC, SQUARE_PROFILE, end_clip=clip)
        RevolvedBeamBuilder().build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        results = ifc4_model.ifc_file.by_type("IfcBooleanClippingResult")
        assert len(results) == 1

    def test_no_clip_no_boolean_result(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingRevolvedBeam(QUARTER_ARC, SQUARE_PROFILE)
        RevolvedBeamBuilder().build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert len(ifc4_model.ifc_file.by_type("IfcBooleanClippingResult")) == 0

    def test_clip_wraps_revolved_solid(self, ifc4_model, ifc4_storey, body_context):
        clip = Plane.from_origin_and_normal(Vec(0.3, 0, 0), Vec(1, 0, 0))
        pending = PendingRevolvedBeam(QUARTER_ARC, SQUARE_PROFILE, start_clip=clip)
        RevolvedBeamBuilder().build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        result = ifc4_model.ifc_file.by_type("IfcBooleanClippingResult")[0]
        assert result.FirstOperand.is_a("IfcRevolvedAreaSolid")

    def test_clipped_beam_parses_after_save(self, ifc4_model, ifc4_storey, body_context, tmp_path):
        clip = Plane.from_origin_and_normal(Vec(0.3, 0, 0), Vec(-1, 0, 0))
        pending = PendingRevolvedBeam(QUARTER_ARC, SQUARE_PROFILE, start_clip=clip)
        RevolvedBeamBuilder().build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        path = str(tmp_path / "revbeam_clipped.ifc")
        ifc4_model.save(path)
        reopened = ifcopenshell.open(path)
        assert len(reopened.by_type("IfcBeam")) == 1
        assert len(reopened.by_type("IfcBooleanClippingResult")) == 1

    def test_both_clips_produce_two_boolean_results(self, ifc4_model, ifc4_storey, body_context):
        start_clip = Plane.from_origin_and_normal(Vec(0.3, 0, 0), Vec(-1, 0, 0))
        end_clip = Plane.from_origin_and_normal(Vec(0.7, 0, 0), Vec(1, 0, 0))
        pending = PendingRevolvedBeam(
            QUARTER_ARC, SQUARE_PROFILE, start_clip=start_clip, end_clip=end_clip,
        )
        RevolvedBeamBuilder().build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        results = ifc4_model.ifc_file.by_type("IfcBooleanClippingResult")
        assert len(results) == 2


class TestBeamFromPathClips:
    """Tests for clip forwarding in beam_from_path."""

    def _two_line_path(self):
        p = Path()
        p.add_line(Vec(0, 0, 0), Vec(3, 0, 0))
        p.add_line(Vec(3, 0, 0), Vec(6, 0, 0))
        return p

    def _l_shaped_path(self):
        p = Path()
        p.add_line(Vec(0, 0, 0), Vec(3, 0, 0))
        p.add_line(Vec(3, 0, 0), Vec(3, 3, 0))
        return p

    def test_clip_forwarded_only_to_intersecting_segment(self):
        """Clip at x=2 (keep +X) affects only first of two collinear X-axis segments."""
        clip = Plane.from_origin_and_normal(Vec(2, 0, 0), Vec(-1, 0, 0))
        result = beam_from_path(self._two_line_path(), SQUARE_PROFILE, clips=[clip])
        assert len(result) == 2
        assert len(result[0].clips) == 1  # 0→3 crosses x=2
        assert len(result[1].clips) == 0  # 3→6 entirely on keep side

    def test_clip_forwarded_to_all_segments_when_intersecting_all(self):
        """Clip at y=1.5 (keep +Y) affects both segments of a zigzag path."""
        def _zigzag():
            p = Path()
            p.add_line(Vec(0, 0, 0), Vec(3, 3, 0))
            p.add_line(Vec(3, 3, 0), Vec(6, 0, 0))
            return p

        clip = Plane.from_origin_and_normal(Vec(0, 1.5, 0), Vec(0, -1, 0))
        result = beam_from_path(_zigzag(), SQUARE_PROFILE, clips=[clip])
        assert len(result) == 2
        assert len(result[0].clips) == 1  # y goes 0→3, crosses 1.5
        assert len(result[1].clips) == 1  # y goes 3→0, crosses 1.5

    def test_no_clips_no_clips_on_segments(self):
        result = beam_from_path(self._two_line_path(), SQUARE_PROFILE)
        assert len(result) == 2
        assert len(result[0].clips) == 0
        assert len(result[1].clips) == 0

    def test_start_clip_forwarded_as_clip(self):
        clip = Plane.from_origin_and_normal(Vec(2, 0, 0), Vec(-1, 0, 0))
        result = beam_from_path(self._two_line_path(), SQUARE_PROFILE, start_clip=clip)
        assert len(result[0].clips) == 1

    def test_end_clip_forwarded_as_clip(self):
        clip = Plane.from_origin_and_normal(Vec(5, 0, 0), Vec(1, 0, 0))
        result = beam_from_path(self._two_line_path(), SQUARE_PROFILE, end_clip=clip)
        # Only affects second segment (3→6 crosses x=5)
        assert len(result[0].clips) == 0
        assert len(result[1].clips) == 1

    # --- Single-clip: segment fully removed / skipped ---

    def test_single_clip_fully_removes_segment(self):
        """Clip keeping x<2: seg 2 (3→6) fully removed and skipped."""
        clip = Plane.from_origin_and_normal(Vec(2, 0, 0), Vec(1, 0, 0))
        result = beam_from_path(self._two_line_path(), SQUARE_PROFILE, clips=[clip])
        assert len(result) == 1  # segment 2 skipped
        assert len(result[0].clips) == 1  # segment 1 partially clipped

    def test_segment_fully_on_remove_side_is_skipped(self):
        """L-shaped: clip keeping x<1 fully removes vertical segment (x=3)."""
        clip = Plane.from_origin_and_normal(Vec(1, 0, 0), Vec(1, 0, 0))
        result = beam_from_path(self._l_shaped_path(), SQUARE_PROFILE, clips=[clip])
        assert len(result) == 1
        assert len(result[0].clips) == 1

    # --- Single-clip on arcs ---

    def test_arc_fully_removed_by_single_clip(self):
        arc_path = Path()
        arc_path.add_arc(Vec(0, 1, 0), Vec(0, 0, 1), Vec(0, 0, 0), math.pi / 2)
        clip = Plane.from_origin_and_normal(Vec(0, 1.5, 0), Vec(0, -1, 0))
        result = beam_from_path(arc_path, SQUARE_PROFILE, clips=[clip])
        assert len(result) == 0

    def test_arc_partially_removed_not_skipped(self):
        arc_path = Path()
        arc_path.add_arc(Vec(0, 1, 0), Vec(0, 0, 1), Vec(0, 0, 0), math.pi / 2)
        clip = Plane.from_origin_and_normal(Vec(0.3, 0, 0), Vec(-1, 0, 0))
        result = beam_from_path(arc_path, SQUARE_PROFILE, clips=[clip])
        assert len(result) == 1
        assert len(result[0].clips) == 1

    # --- Boundary (sd = 0) ---

    def test_clip_at_segment_boundary_sd_zero(self):
        """Clip at x=3 keeps -X.  Seg 1 ends at x=3 (sd=0) → clip forwarded.
        Seg 2 starts at x=3 (sd=0), all x≥3 (sd≥0) → fully removed."""
        clip = Plane.from_origin_and_normal(Vec(3, 0, 0), Vec(1, 0, 0))
        result = beam_from_path(self._two_line_path(), SQUARE_PROFILE, clips=[clip])
        assert len(result) == 1  # segment 2 skipped
        assert len(result[0].clips) == 1  # segment 1 partially clipped
