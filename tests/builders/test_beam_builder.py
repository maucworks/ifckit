"""Tests for ExtrudedElementBuilder (beam + column) and RevolvedBeamBuilder."""

import math
import pytest
import ifcopenshell

from ifckit.geometry import Vec, Line, Arc, Path, Plane
from ifckit.elements.structural import PendingBeam, PendingColumn, PendingRevolvedBeam
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
        assert solid.Angle == pytest.approx(-math.pi / 2)  # negative = CW sweep (C# approach)

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
        assert solid.Angle == pytest.approx(-math.pi)  # negative = CW sweep (C# approach)

    def test_file_parses_after_save(self, ifc4_model, ifc4_storey, body_context, tmp_path):
        pending = PendingRevolvedBeam(QUARTER_ARC, SQUARE_PROFILE)
        RevolvedBeamBuilder().build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        path = str(tmp_path / "revbeam.ifc")
        ifc4_model.save(path)
        reopened = ifcopenshell.open(path)
        assert len(reopened.by_type("IfcBeam")) == 1
        assert len(reopened.by_type("IfcRevolvedAreaSolid")) == 1
