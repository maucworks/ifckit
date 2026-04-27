"""
Integration tests for IFC output.

Each test:
  1. Builds a model via the public ifckit API
  2. Calls builder(s) to add geometry
  3. Saves to tmp_path / re-opens with ifcopenshell.open()
  4. Asserts entity counts, relationships, and geometry presence
"""
from __future__ import annotations

import math
import pytest
import ifcopenshell

import ifckit
from ifckit import (
    IfcModel, IfcSchema,
    PendingWall, PendingSlab, PendingBeam, PendingColumn,
    PendingRevolvedBeam, PendingAlignment, PendingBridge, PendingBridgePart,
    AlignmentSegment, BridgePartType,
    Vec, Plane, Line, Arc,
)
from ifckit.builders import default_registry
from ifckit.builders._geom import get_body_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count(f: ifcopenshell.file, ifc_type: str) -> int:
    return len(f.by_type(ifc_type))


def _has_rel(f: ifcopenshell.file, rel_type: str,
             parent_type: str, child_type: str) -> bool:
    for rel in f.by_type(rel_type):
        relating = getattr(rel, "RelatingObject", None) or getattr(rel, "RelatingStructure", None)
        related = getattr(rel, "RelatedObjects", None) or getattr(rel, "RelatedElements", None)
        if relating and related:
            if relating.is_a(parent_type):
                if any(c.is_a(child_type) for c in related):
                    return True
    return False


SQUARE = [Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 3, 0), Vec(0, 3, 0)]
BOX_PROFILE = [Vec(0, 0), Vec(0.3, 0), Vec(0.3, 0.3), Vec(0, 0.3)]
BEAM_PROFILE = [Vec(0, -0.15), Vec(0.3, -0.15), Vec(0.3, 0.15), Vec(0, 0.15)]


# ---------------------------------------------------------------------------
# Scenario 1: Minimal IFC4 building — 1 wall, 1 slab, 1 storey
# ---------------------------------------------------------------------------

class TestMinimalIfc4Building:
    @pytest.fixture
    def saved_file(self, tmp_path):
        model = IfcModel(name="MinBuilding", schema=IfcSchema.IFC4, author="pytest")
        site = model.add_site("Site")
        bldg = model.add_building(site, "Bldg")
        storey = model.add_storey(bldg, "L0", elevation=0.0)

        reg = default_registry()
        ctx = get_body_context(model.ifc_file)

        wall = PendingWall(footprint=SQUARE, plane=Plane.world_xy(),
                           height=3.0, name="W1")
        reg.get("basic_wall").build(model.ifc_file, wall, storey.entity, ctx)

        slab = PendingSlab(footprint=SQUARE, plane=Plane.world_xy(),
                           thickness=0.3, name="S1")
        reg.get("basic_slab").build(model.ifc_file, slab, storey.entity, ctx)

        path = str(tmp_path / "minimal.ifc")
        model.save(path)
        return ifcopenshell.open(path)

    def test_schema_is_ifc4(self, saved_file):
        assert saved_file.schema.startswith("IFC4")

    def test_project_present(self, saved_file):
        assert _count(saved_file, "IfcProject") == 1

    def test_site_present(self, saved_file):
        assert _count(saved_file, "IfcSite") == 1

    def test_building_present(self, saved_file):
        assert _count(saved_file, "IfcBuilding") == 1

    def test_storey_present(self, saved_file):
        assert _count(saved_file, "IfcBuildingStorey") == 1

    def test_wall_present(self, saved_file):
        assert _count(saved_file, "IfcWall") == 1

    def test_slab_present(self, saved_file):
        assert _count(saved_file, "IfcSlab") == 1

    def test_extruded_solids_present(self, saved_file):
        assert _count(saved_file, "IfcExtrudedAreaSolid") == 2

    def test_profiles_present(self, saved_file):
        assert _count(saved_file, "IfcArbitraryClosedProfileDef") == 2

    def test_wall_contained_in_storey(self, saved_file):
        assert _has_rel(saved_file, "IfcRelContainedInSpatialStructure",
                        "IfcBuildingStorey", "IfcWall")

    def test_slab_contained_in_storey(self, saved_file):
        assert _has_rel(saved_file, "IfcRelContainedInSpatialStructure",
                        "IfcBuildingStorey", "IfcSlab")

    def test_wall_has_representation(self, saved_file):
        walls = saved_file.by_type("IfcWall")
        assert walls[0].Representation is not None

    def test_slab_depth_in_output(self, saved_file):
        solids = saved_file.by_type("IfcExtrudedAreaSolid")
        depths = [s.Depth for s in solids]
        assert 0.3 in depths or any(abs(d - 0.3) < 1e-6 for d in depths)


# ---------------------------------------------------------------------------
# Scenario 2: Multi-storey IFC4 building — 3 storeys, mixed elements
# ---------------------------------------------------------------------------

class TestMultiStoreyIfc4:
    @pytest.fixture
    def saved_file(self, tmp_path):
        model = IfcModel(name="MultiStorey", schema=IfcSchema.IFC4, author="pytest")
        site = model.add_site("Site")
        bldg = model.add_building(site, "Bldg")

        reg = default_registry()
        ctx = get_body_context(model.ifc_file)

        for level in range(3):
            storey = model.add_storey(bldg, f"L{level}", elevation=float(level * 3.5))
            # Add a wall and a column per storey
            wall = PendingWall(footprint=SQUARE, plane=Plane.world_xy(),
                               height=3.5, name=f"W{level}")
            reg.get("basic_wall").build(model.ifc_file, wall, storey.entity, ctx)

            col_axis = Line(Vec(0, 0, level * 3.5), Vec(0, 0, level * 3.5 + 3.5))
            col = PendingColumn(axis=col_axis, profile=BOX_PROFILE, name=f"C{level}")
            reg.get("basic_column").build(model.ifc_file, col, storey.entity, ctx)

        path = str(tmp_path / "multi.ifc")
        model.save(path)
        return ifcopenshell.open(path)

    def test_three_storeys(self, saved_file):
        assert _count(saved_file, "IfcBuildingStorey") == 3

    def test_three_walls(self, saved_file):
        assert _count(saved_file, "IfcWall") == 3

    def test_three_columns(self, saved_file):
        assert _count(saved_file, "IfcColumn") == 3

    def test_six_extruded_solids(self, saved_file):
        assert _count(saved_file, "IfcExtrudedAreaSolid") == 6

    def test_storey_aggregated_in_building(self, saved_file):
        assert _has_rel(saved_file, "IfcRelAggregates",
                        "IfcBuilding", "IfcBuildingStorey")


# ---------------------------------------------------------------------------
# Scenario 3: IFC4 building with beam and revolved beam
# ---------------------------------------------------------------------------

class TestBeamElements:
    @pytest.fixture
    def saved_file(self, tmp_path):
        model = IfcModel(name="BeamTest", schema=IfcSchema.IFC4, author="pytest")
        site = model.add_site("Site")
        bldg = model.add_building(site, "Bldg")
        storey = model.add_storey(bldg, "L0")

        reg = default_registry()
        ctx = get_body_context(model.ifc_file)

        # Straight beam
        beam = PendingBeam(
            axis=Line(Vec(0, 0, 0), Vec(10, 0, 0)),
            profile=BEAM_PROFILE,
            name="Beam1",
        )
        reg.get("basic_beam").build(model.ifc_file, beam, storey.entity, ctx)

        # Revolved beam (90° arc, radius 5)
        arc = Arc(center=Vec(0, 5, 0), normal=Vec(0, 0, 1),
                  start=Vec(0, 0, 0), angle=math.pi / 2)
        rb = PendingRevolvedBeam(arc=arc, profile=BEAM_PROFILE, name="RBeam1")
        reg.get("revolved_beam").build(model.ifc_file, rb, storey.entity, ctx)

        path = str(tmp_path / "beams.ifc")
        model.save(path)
        return ifcopenshell.open(path)

    def test_two_beams(self, saved_file):
        assert _count(saved_file, "IfcBeam") == 2

    def test_straight_beam_extruded_solid(self, saved_file):
        assert _count(saved_file, "IfcExtrudedAreaSolid") == 1

    def test_revolved_beam_revolved_solid(self, saved_file):
        assert _count(saved_file, "IfcRevolvedAreaSolid") == 1

    def test_both_beams_contained_in_storey(self, saved_file):
        assert _has_rel(saved_file, "IfcRelContainedInSpatialStructure",
                        "IfcBuildingStorey", "IfcBeam")

    def test_beam_has_profile(self, saved_file):
        assert _count(saved_file, "IfcArbitraryClosedProfileDef") >= 1


# ---------------------------------------------------------------------------
# Scenario 4: IFC4X3 bridge — bridge + 2 parts + alignment
# ---------------------------------------------------------------------------

class TestIfc4x3Bridge:
    @pytest.fixture
    def saved_file(self, tmp_path):
        model = IfcModel(name="BridgeTest", schema=IfcSchema.IFC4X3, author="pytest")
        site = model.add_site("Site")
        bridge = model.add_bridge(site, "ModuloBrug")
        deck = model.add_bridge_part(bridge, "Deck", BridgePartType.DECK.value)
        sub = model.add_bridge_part(bridge, "Sub", BridgePartType.SUBSTRUCTURE.value)
        align_handle = model.add_alignment(bridge, "MainAlignment")

        # Populate alignment geometry
        reg = default_registry()
        seg1 = AlignmentSegment(geometry=Line(Vec(0, 0, 0), Vec(50, 0, 0)))
        seg2 = AlignmentSegment(
            geometry=Arc(center=Vec(50, 20, 0), normal=Vec(0, 0, 1),
                         start=Vec(50, 0, 0), angle=math.pi / 4)
        )
        alignment = PendingAlignment(segments=[seg1, seg2], name="MainAlignment")
        reg.get("alignment").build(
            model.ifc_file, alignment, align_handle.entity, None
        )

        path = str(tmp_path / "bridge.ifc")
        model.save(path)
        return ifcopenshell.open(path)

    def test_schema_is_ifc4x3(self, saved_file):
        assert "IFC4X3" in saved_file.schema

    def test_bridge_present(self, saved_file):
        assert _count(saved_file, "IfcBridge") == 1

    def test_two_bridge_parts(self, saved_file):
        assert _count(saved_file, "IfcBridgePart") == 2

    def test_alignment_present(self, saved_file):
        assert _count(saved_file, "IfcAlignment") == 1

    def test_alignment_horizontal_present(self, saved_file):
        assert _count(saved_file, "IfcAlignmentHorizontal") == 1

    def test_two_alignment_segments(self, saved_file):
        assert _count(saved_file, "IfcAlignmentSegment") == 2

    def test_line_segment_type(self, saved_file):
        segs = saved_file.by_type("IfcAlignmentSegment")
        types = [s.DesignParameters.PredefinedType for s in segs]
        assert "LINE" in types

    def test_arc_segment_type(self, saved_file):
        segs = saved_file.by_type("IfcAlignmentSegment")
        types = [s.DesignParameters.PredefinedType for s in segs]
        assert "CIRCULARARC" in types

    def test_bridge_aggregated_in_site(self, saved_file):
        assert _has_rel(saved_file, "IfcRelAggregates", "IfcSite", "IfcBridge")

    def test_parts_aggregated_in_bridge(self, saved_file):
        assert _has_rel(saved_file, "IfcRelAggregates", "IfcBridge", "IfcBridgePart")

    def test_line_segment_length(self, saved_file):
        segs = saved_file.by_type("IfcAlignmentSegment")
        line_segs = [s for s in segs if s.DesignParameters.PredefinedType == "LINE"]
        assert abs(line_segs[0].DesignParameters.SegmentLength - 50.0) < 1e-4


# ---------------------------------------------------------------------------
# Scenario 5: IFC4X3 bridge with beams placed in a deck part
# ---------------------------------------------------------------------------

class TestIfc4x3BridgeWithBeams:
    @pytest.fixture
    def saved_file(self, tmp_path):
        model = IfcModel(name="BridgeBeams", schema=IfcSchema.IFC4X3, author="pytest")
        site = model.add_site("Site")
        bridge = model.add_bridge(site, "Brug")
        deck = model.add_bridge_part(bridge, "Deck", BridgePartType.DECK.value)

        reg = default_registry()
        ctx = get_body_context(model.ifc_file)

        # Add 3 beams to the deck part
        for i in range(3):
            beam = PendingBeam(
                axis=Line(Vec(i * 0.5, 0, 0), Vec(i * 0.5, 20, 0)),
                profile=BEAM_PROFILE,
                name=f"DeckBeam{i}",
            )
            entity = reg.get("basic_beam").build(
                model.ifc_file, beam, deck.entity, ctx
            )

        path = str(tmp_path / "bridge_beams.ifc")
        model.save(path)
        return ifcopenshell.open(path)

    def test_three_beams_in_output(self, saved_file):
        assert _count(saved_file, "IfcBeam") == 3

    def test_beams_contained_in_deck(self, saved_file):
        assert _has_rel(saved_file, "IfcRelContainedInSpatialStructure",
                        "IfcBridgePart", "IfcBeam")

    def test_deck_part_present(self, saved_file):
        assert _count(saved_file, "IfcBridgePart") == 1

    def test_three_extruded_solids(self, saved_file):
        assert _count(saved_file, "IfcExtrudedAreaSolid") == 3


# ---------------------------------------------------------------------------
# Scenario 6: to_string() produces valid parseable IFC
# ---------------------------------------------------------------------------

class TestToString:
    def test_ifc4_to_string_parseable(self, tmp_path):
        model = IfcModel(name="Str4", schema=IfcSchema.IFC4, author="pytest")
        site = model.add_site("S")
        bldg = model.add_building(site, "B")
        _ = model.add_storey(bldg, "L0")
        s = model.to_string()
        assert "IFC4" in s
        assert "IFCPROJECT" in s.upper()

    def test_ifc4x3_to_string_parseable(self, tmp_path):
        model = IfcModel(name="Str4x3", schema=IfcSchema.IFC4X3, author="pytest")
        site = model.add_site("S")
        _ = model.add_bridge(site, "Br")
        s = model.to_string()
        assert "IFC4X3" in s.upper()
        assert "IFCBRIDGE" in s.upper()
