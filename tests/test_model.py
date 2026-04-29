"""Tests for ifckit.model — IfcModel hierarchy (IFC4 and IFC4X3)"""

import math
import pytest
import ifcopenshell
from ifckit.schema import IfcSchema
from ifckit.model import (
    IfcModel,
    SiteHandle,
    BuildingHandle,
    StoreyHandle,
    BridgeHandle,
    BridgePartHandle,
    AlignmentHandle,
    EntityHandle,
)
from ifckit.geometry import Vec, Line, Arc, Path, Plane
from ifckit.elements.structural import PendingBeam, PendingColumn, PendingRevolvedBeam
from ifckit.elements.swept import PendingSweptBeam
from ifckit.elements.building import PendingWall, PendingSlab


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ifc4():
    return IfcModel(name="TestProject", schema=IfcSchema.IFC4, author="pytest")


@pytest.fixture
def ifc4x3():
    return IfcModel(name="BridgeProject", schema=IfcSchema.IFC4X3, author="pytest")


# ---------------------------------------------------------------------------
# IfcModel construction
# ---------------------------------------------------------------------------


class TestIfcModelInit:
    def test_project_exists(self, ifc4):
        projects = ifc4.ifc_file.by_type("IfcProject")
        assert len(projects) == 1
        assert projects[0].Name == "TestProject"

    def test_schema_ifc4(self, ifc4):
        assert ifc4.schema == IfcSchema.IFC4

    def test_schema_ifc4x3(self, ifc4x3):
        assert ifc4x3.schema == IfcSchema.IFC4X3

    def test_ifc4_file_schema_string(self, ifc4):
        s = ifc4.to_string()
        assert "IFC4" in s

    def test_ifc4x3_file_schema_string(self, ifc4x3):
        s = ifc4x3.to_string()
        assert "IFC4X3" in s

    def test_units_assigned(self, ifc4):
        assert len(ifc4.ifc_file.by_type("IfcUnitAssignment")) == 1

    def test_context_created(self, ifc4):
        assert len(ifc4.ifc_file.by_type("IfcGeometricRepresentationContext")) >= 1


# ---------------------------------------------------------------------------
# IFC4 hierarchy
# ---------------------------------------------------------------------------


class TestIfc4Hierarchy:
    def test_add_site(self, ifc4):
        site = ifc4.add_site("Site A")
        assert isinstance(site, SiteHandle)
        assert len(ifc4.ifc_file.by_type("IfcSite")) == 1

    def test_add_site_description(self, ifc4):
        site = ifc4.add_site("Site A", description="Main site")
        assert site.entity.Description == "Main site"

    def test_add_building(self, ifc4):
        site = ifc4.add_site("Site A")
        building = ifc4.add_building(site, "Building 1")
        assert isinstance(building, BuildingHandle)
        assert len(ifc4.ifc_file.by_type("IfcBuilding")) == 1

    def test_add_building_description(self, ifc4):
        site = ifc4.add_site("Site A")
        b = ifc4.add_building(site, "B", description="Main building")
        assert b.entity.Description == "Main building"

    def test_add_storey(self, ifc4):
        site = ifc4.add_site("S")
        building = ifc4.add_building(site, "B")
        storey = ifc4.add_storey(building, "Ground Floor", elevation=0.0)
        assert isinstance(storey, StoreyHandle)
        assert len(ifc4.ifc_file.by_type("IfcBuildingStorey")) == 1
        assert storey.entity.Elevation == pytest.approx(0.0)

    def test_storey_elevation(self, ifc4):
        site = ifc4.add_site("S")
        b = ifc4.add_building(site, "B")
        s1 = ifc4.add_storey(b, "L1", elevation=3.5)
        assert s1.entity.Elevation == pytest.approx(3.5)

    def test_add_element(self, ifc4):
        site = ifc4.add_site("S")
        b = ifc4.add_building(site, "B")
        s = ifc4.add_storey(b, "L0")
        wall = ifc4.add_element(s, "IfcWall", name="W1")
        assert isinstance(wall, EntityHandle)
        assert len(ifc4.ifc_file.by_type("IfcWall")) == 1
        assert wall.entity.Name == "W1"

    def test_element_contained_in_storey(self, ifc4):
        site = ifc4.add_site("S")
        b = ifc4.add_building(site, "B")
        s = ifc4.add_storey(b, "L0")
        ifc4.add_element(s, "IfcSlab", name="Slab1")
        rels = ifc4.ifc_file.by_type("IfcRelContainedInSpatialStructure")
        assert len(rels) == 1

    def test_site_aggregated_under_project(self, ifc4):
        ifc4.add_site("S")
        rels = ifc4.ifc_file.by_type("IfcRelAggregates")
        relating = [r.RelatingObject for r in rels]
        assert any(e.is_a("IfcProject") for e in relating)

    def test_building_aggregated_under_site(self, ifc4):
        site = ifc4.add_site("S")
        ifc4.add_building(site, "B")
        rels = ifc4.ifc_file.by_type("IfcRelAggregates")
        relating = [r.RelatingObject for r in rels]
        assert any(e.is_a("IfcSite") for e in relating)

    def test_multiple_storeys(self, ifc4):
        site = ifc4.add_site("S")
        b = ifc4.add_building(site, "B")
        ifc4.add_storey(b, "L0", elevation=0.0)
        ifc4.add_storey(b, "L1", elevation=3.5)
        ifc4.add_storey(b, "L2", elevation=7.0)
        assert len(ifc4.ifc_file.by_type("IfcBuildingStorey")) == 3


# ---------------------------------------------------------------------------
# IFC4X3 bridge hierarchy
# ---------------------------------------------------------------------------


class TestIfc4x3Hierarchy:
    def _setup(self, model):
        return model.add_site("Site")

    def test_add_bridge(self, ifc4x3):
        site = self._setup(ifc4x3)
        bridge = ifc4x3.add_bridge(site, "Brug")
        assert isinstance(bridge, BridgeHandle)
        assert len(ifc4x3.ifc_file.by_type("IfcBridge")) == 1

    def test_add_bridge_description(self, ifc4x3):
        site = self._setup(ifc4x3)
        bridge = ifc4x3.add_bridge(site, "Brug", description="Main bridge")
        assert bridge.entity.Description == "Main bridge"

    def test_add_bridge_part(self, ifc4x3):
        site = self._setup(ifc4x3)
        bridge = ifc4x3.add_bridge(site, "Brug")
        part = ifc4x3.add_bridge_part(bridge, "Deck", part_type="DECK")
        assert isinstance(part, BridgePartHandle)
        assert len(ifc4x3.ifc_file.by_type("IfcBridgePart")) == 1

    def test_add_alignment(self, ifc4x3):
        site = self._setup(ifc4x3)
        alignment = ifc4x3.add_alignment(site, "Alignment A")
        assert isinstance(alignment, AlignmentHandle)
        assert alignment.entity is not None
        assert len(ifc4x3.ifc_file.by_type("IfcAlignment")) == 1

    def test_add_element_to_part(self, ifc4x3):
        site = self._setup(ifc4x3)
        bridge = ifc4x3.add_bridge(site, "Brug")
        part = ifc4x3.add_bridge_part(bridge, "Deck", part_type="DECK")
        beam = ifc4x3.add_element_to_part(part, "IfcBeam", name="Beam1")
        assert isinstance(beam, EntityHandle)
        assert len(ifc4x3.ifc_file.by_type("IfcBeam")) == 1

    def test_bridge_part_predefined_type(self, ifc4x3):
        site = self._setup(ifc4x3)
        bridge = ifc4x3.add_bridge(site, "Brug")
        part = ifc4x3.add_bridge_part(bridge, "Sub", part_type="SUBSTRUCTURE")
        assert str(part.entity.PredefinedType) == "SUBSTRUCTURE"

    def test_bridge_aggregated_under_site(self, ifc4x3):
        site = self._setup(ifc4x3)
        ifc4x3.add_bridge(site, "Brug")
        rels = ifc4x3.ifc_file.by_type("IfcRelAggregates")
        relating = [r.RelatingObject for r in rels]
        assert any(e.is_a("IfcSite") for e in relating)

    def test_full_bridge_hierarchy(self, ifc4x3):
        """Project → Site → Bridge → Part → Beam"""
        site = ifc4x3.add_site("Site")
        bridge = ifc4x3.add_bridge(site, "Brug")
        part = ifc4x3.add_bridge_part(bridge, "Deck", part_type="DECK")
        ifc4x3.add_element_to_part(part, "IfcBeam", name="B1")
        ifc4x3.add_element_to_part(part, "IfcBeam", name="B2")
        assert len(ifc4x3.ifc_file.by_type("IfcBeam")) == 2
        assert len(ifc4x3.ifc_file.by_type("IfcBridgePart")) == 1
        assert len(ifc4x3.ifc_file.by_type("IfcBridge")) == 1


# ---------------------------------------------------------------------------
# Schema guard
# ---------------------------------------------------------------------------


class TestSchemaGuard:
    def test_add_bridge_on_ifc4_raises(self, ifc4):
        site = ifc4.add_site("S")
        with pytest.raises(ValueError, match="IFC4X3"):
            ifc4.add_bridge(site, "Brug")

    def test_add_bridge_part_on_ifc4_raises(self, ifc4):
        # Create a dummy handle — the guard fires before any lookup
        from ifckit.model import BridgeHandle

        dummy = BridgeHandle(ifc4.ifc_file.by_type("IfcProject")[0], ifc4)
        with pytest.raises(ValueError, match="IFC4X3"):
            ifc4.add_bridge_part(dummy, "Deck")

    def test_add_alignment_on_ifc4_raises(self, ifc4):
        site = ifc4.add_site("S")
        with pytest.raises(ValueError, match="IFC4X3"):
            ifc4.add_alignment(site, "Align")


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class TestExport:
    def test_save(self, ifc4, tmp_path):
        ifc4.add_site("S")
        path = str(tmp_path / "out.ifc")
        ifc4.save(path)
        reopened = ifcopenshell.open(path)
        assert len(reopened.by_type("IfcProject")) == 1

    def test_to_string(self, ifc4):
        s = ifc4.to_string()
        assert isinstance(s, str)
        assert "IFCPROJECT" in s

    def test_save_and_reopen_bridge(self, ifc4x3, tmp_path):
        site = ifc4x3.add_site("S")
        bridge = ifc4x3.add_bridge(site, "Brug")
        ifc4x3.add_bridge_part(bridge, "Deck", part_type="DECK")
        path = str(tmp_path / "bridge.ifc")
        ifc4x3.save(path)
        f = ifcopenshell.open(path)
        assert len(f.by_type("IfcBridge")) == 1
        assert len(f.by_type("IfcBridgePart")) == 1

    def test_ifc_file_property(self, ifc4):
        assert isinstance(ifc4.ifc_file, ifcopenshell.file)


# ---------------------------------------------------------------------------
# model.add()
# ---------------------------------------------------------------------------

_SQUARE_PROFILE = [Vec(-0.1, -0.1), Vec(0.1, -0.1), Vec(0.1, 0.1), Vec(-0.1, 0.1)]
_BEAM_AXIS = Line(Vec(0, 0, 0), Vec(5, 0, 0))
_FOOTPRINT = [Vec(0, 0, 0), Vec(4, 0, 0), Vec(4, 3, 0), Vec(0, 3, 0)]


@pytest.fixture
def model_with_storey():
    m = IfcModel(name="Test", schema=IfcSchema.IFC4)
    site = m.add_site("Site")
    bldg = m.add_building(site, "Building")
    storey = m.add_storey(bldg, "Ground Floor", elevation=0.0)
    return m, storey


@pytest.fixture
def model_with_bridge_part():
    m = IfcModel(name="Bridge", schema=IfcSchema.IFC4X3)
    site = m.add_site("Site")
    bridge = m.add_bridge(site, "B")
    part = m.add_bridge_part(bridge, "Deck", part_type="DECK")
    return m, part


class TestModelAdd:
    def test_add_beam_returns_entity_handle(self, model_with_storey):
        m, storey = model_with_storey
        pending = PendingBeam(_BEAM_AXIS, _SQUARE_PROFILE, name="B1")
        handle = m.add(pending, storey)
        assert isinstance(handle, EntityHandle)
        assert handle.entity.is_a("IfcBeam")

    def test_add_beam_name_passed_through(self, model_with_storey):
        m, storey = model_with_storey
        pending = PendingBeam(_BEAM_AXIS, _SQUARE_PROFILE, name="MyBeam")
        handle = m.add(pending, storey)
        assert handle.entity.Name == "MyBeam"

    def test_add_column(self, model_with_storey):
        m, storey = model_with_storey
        col_axis = Line(Vec(0, 0, 0), Vec(0, 0, 3))
        pending = PendingColumn(col_axis, _SQUARE_PROFILE, name="C1")
        handle = m.add(pending, storey)
        assert handle.entity.is_a("IfcColumn")

    def test_add_wall(self, model_with_storey):
        m, storey = model_with_storey
        pending = PendingWall(
            footprint=_FOOTPRINT,
            plane=Plane.world_xy(),
            height=3.0,
            name="W1",
        )
        handle = m.add(pending, storey)
        assert handle.entity.is_a("IfcWall")

    def test_add_slab(self, model_with_storey):
        m, storey = model_with_storey
        pending = PendingSlab(
            footprint=_FOOTPRINT,
            plane=Plane.world_xy(),
            thickness=0.2,
            name="Slab1",
        )
        handle = m.add(pending, storey)
        assert handle.entity.is_a("IfcSlab")

    def test_add_revolved_beam(self, model_with_storey):
        m, storey = model_with_storey
        arc = Arc(Vec(0, 1, 0), Vec(0, 0, 1), Vec(0, 0, 0), math.pi / 2)
        pending = PendingRevolvedBeam(arc, _SQUARE_PROFILE, name="RB1")
        handle = m.add(pending, storey)
        assert handle.entity.is_a("IfcBeam")

    def test_add_swept_beam_line(self, model_with_storey):
        m, storey = model_with_storey
        pending = PendingSweptBeam(_BEAM_AXIS, _SQUARE_PROFILE, name="SW1")
        handle = m.add(pending, storey)
        assert handle.entity.is_a("IfcBeam")

    def test_add_swept_beam_arc(self, model_with_storey):
        m, storey = model_with_storey
        arc = Arc(Vec(0, 1, 0), Vec(0, 0, 1), Vec(0, 0, 0), math.pi / 2)
        pending = PendingSweptBeam(arc, _SQUARE_PROFILE, name="SW2")
        handle = m.add(pending, storey)
        assert handle.entity.is_a("IfcBeam")

    def test_add_swept_beam_path(self, model_with_storey):
        m, storey = model_with_storey
        p = Path()
        p.add_line(Vec(0, 0, 0), Vec(3, 0, 0))
        p.add_arc(Vec(3, 1, 0), Vec(0, 0, 1), Vec(3, 0, 0), math.pi / 2)
        pending = PendingSweptBeam(p, _SQUARE_PROFILE, name="SW3")
        handle = m.add(pending, storey)
        assert handle.entity.is_a("IfcBeam")

    def test_add_beam_with_clips(self, model_with_storey):
        m, storey = model_with_storey
        start_clip = Plane(Vec(1, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))
        end_clip = Plane(Vec(4, 0, 0), Vec(-1, 0, 0), Vec(0, 0, 1))
        pending = PendingBeam(
            _BEAM_AXIS, _SQUARE_PROFILE, start_clip=start_clip, end_clip=end_clip, name="Clipped"
        )
        handle = m.add(pending, storey)
        assert handle.entity.is_a("IfcBeam")
        assert len(m.ifc_file.by_type("IfcBooleanClippingResult")) == 2

    def test_add_invalid_element_raises_value_error(self, model_with_storey):
        m, storey = model_with_storey
        # Zero-length axis → validation error
        bad = PendingBeam(Line(Vec(0, 0, 0), Vec(0, 0, 0)), _SQUARE_PROFILE)
        with pytest.raises(ValueError, match="Validation failed"):
            m.add(bad, storey)

    def test_add_wrong_container_raises_type_error(self, model_with_storey):
        m, storey = model_with_storey
        pending = PendingBeam(_BEAM_AXIS, _SQUARE_PROFILE)
        with pytest.raises(TypeError, match="StoreyHandle or BridgePartHandle"):
            m.add(pending, "not-a-handle")

    def test_add_beam_to_bridge_part(self, model_with_bridge_part):
        m, part = model_with_bridge_part
        pending = PendingBeam(_BEAM_AXIS, _SQUARE_PROFILE, name="BridgeBeam")
        handle = m.add(pending, part)
        assert handle.entity.is_a("IfcBeam")

    def test_add_emits_warning_for_short_axis(self, model_with_storey):
        import warnings

        m, storey = model_with_storey
        # 5 mm axis — valid but very short → should warn
        short = PendingBeam(Line(Vec(0, 0, 0), Vec(0.005, 0, 0)), _SQUARE_PROFILE)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            m.add(short, storey)
        assert any("very short" in str(w.message) for w in caught)

    def test_add_multiple_beams_in_same_storey(self, model_with_storey):
        m, storey = model_with_storey
        for i in range(3):
            axis = Line(Vec(0, i, 0), Vec(5, i, 0))
            m.add(PendingBeam(axis, _SQUARE_PROFILE, name=f"B{i}"), storey)
        assert len(m.ifc_file.by_type("IfcBeam")) == 3

    def test_add_returns_entity_with_global_id(self, model_with_storey):
        m, storey = model_with_storey
        handle = m.add(PendingBeam(_BEAM_AXIS, _SQUARE_PROFILE), storey)
        assert handle.entity.GlobalId is not None
        assert len(handle.entity.GlobalId) == 22  # IFC GlobalId length


# ---------------------------------------------------------------------------
# Handle chaining
# ---------------------------------------------------------------------------


class TestHandleChaining:
    def test_site_add_building_returns_building_handle(self):
        m = IfcModel(name="T", schema=IfcSchema.IFC4)
        site = m.add_site("Site")
        bldg = site.add_building("Building")
        assert isinstance(bldg, BuildingHandle)
        assert bldg.entity.is_a("IfcBuilding")

    def test_building_add_storey_returns_storey_handle(self):
        m = IfcModel(name="T", schema=IfcSchema.IFC4)
        site = m.add_site("Site")
        bldg = site.add_building("Building")
        storey = bldg.add_storey("Ground Floor", elevation=0.0)
        assert isinstance(storey, StoreyHandle)
        assert storey.entity.is_a("IfcBuildingStorey")

    def test_full_ifc4_chain(self):
        m = IfcModel(name="T", schema=IfcSchema.IFC4)
        floor = m.add_site("Site").add_building("Building").add_storey("GF")
        assert isinstance(floor, StoreyHandle)

    def test_storey_add_beam(self):
        m = IfcModel(name="T", schema=IfcSchema.IFC4)
        floor = m.add_site("S").add_building("B").add_storey("GF")
        handle = floor.add(PendingBeam(_BEAM_AXIS, _SQUARE_PROFILE, name="B1"))
        assert isinstance(handle, EntityHandle)
        assert handle.entity.is_a("IfcBeam")
        assert handle.entity.Name == "B1"

    def test_storey_add_column(self):
        m = IfcModel(name="T", schema=IfcSchema.IFC4)
        floor = m.add_site("S").add_building("B").add_storey("GF")
        col_axis = Line(Vec(0, 0, 0), Vec(0, 0, 3))
        handle = floor.add(PendingColumn(col_axis, _SQUARE_PROFILE))
        assert handle.entity.is_a("IfcColumn")

    def test_storey_add_validates_and_raises(self):
        m = IfcModel(name="T", schema=IfcSchema.IFC4)
        floor = m.add_site("S").add_building("B").add_storey("GF")
        bad = PendingBeam(Line(Vec(0, 0, 0), Vec(0, 0, 0)), _SQUARE_PROFILE)
        with pytest.raises(ValueError, match="Validation failed"):
            floor.add(bad)

    def test_storey_add_equals_model_add(self):
        """floor.add(p) and model.add(p, floor) produce the same IFC class."""
        m = IfcModel(name="T", schema=IfcSchema.IFC4)
        site = m.add_site("S")
        bldg = site.add_building("B")
        floor = bldg.add_storey("GF")
        # via floor.add
        h1 = floor.add(PendingBeam(_BEAM_AXIS, _SQUARE_PROFILE))
        # via model.add on a second storey
        floor2 = m.add_storey(bldg, "Level 2", elevation=3.0)
        h2 = m.add(PendingBeam(_BEAM_AXIS, _SQUARE_PROFILE), floor2)
        assert h1.entity.is_a() == h2.entity.is_a()

    def test_full_ifc4x3_chain(self):
        m = IfcModel(name="Bridge", schema=IfcSchema.IFC4X3)
        part = m.add_site("S").add_bridge("B").add_bridge_part("Deck", part_type="DECK")
        assert isinstance(part, BridgePartHandle)
        assert part.entity.is_a("IfcBridgePart")

    def test_bridge_part_add_beam(self):
        m = IfcModel(name="Bridge", schema=IfcSchema.IFC4X3)
        part = m.add_site("S").add_bridge("B").add_bridge_part("Deck", part_type="DECK")
        handle = part.add(PendingBeam(_BEAM_AXIS, _SQUARE_PROFILE, name="Girder"))
        assert handle.entity.is_a("IfcBeam")
        assert handle.entity.Name == "Girder"

    def test_flat_api_still_works(self):
        """model.add_building(site, ...) etc. remain valid."""
        m = IfcModel(name="T", schema=IfcSchema.IFC4)
        site = m.add_site("Site")
        bldg = m.add_building(site, "Building")
        floor = m.add_storey(bldg, "GF")
        handle = m.add(PendingBeam(_BEAM_AXIS, _SQUARE_PROFILE), floor)
        assert handle.entity.is_a("IfcBeam")

    def test_multiple_storeys_via_chaining(self):
        m = IfcModel(name="T", schema=IfcSchema.IFC4)
        bldg = m.add_site("S").add_building("B")
        gf = bldg.add_storey("Ground Floor", elevation=0.0)
        l1 = bldg.add_storey("Level 1", elevation=3.5)
        gf.add(PendingBeam(_BEAM_AXIS, _SQUARE_PROFILE, name="GF Beam"))
        l1.add(PendingBeam(_BEAM_AXIS, _SQUARE_PROFILE, name="L1 Beam"))
        assert len(m.ifc_file.by_type("IfcBeam")) == 2
        assert len(m.ifc_file.by_type("IfcBuildingStorey")) == 2


# ---------------------------------------------------------------------------
# TC1 — model.export()
# ---------------------------------------------------------------------------


class TestModelExport:
    """TC1: model.export() writes a valid file for each supported format."""

    def _model_with_beam(self):
        m = IfcModel(name="ExportTest", schema=IfcSchema.IFC4)
        floor = m.add_site("S").add_building("B").add_storey("GF")
        floor.add(PendingBeam(_BEAM_AXIS, _SQUARE_PROFILE, name="Beam"))
        return m

    def test_export_ifc(self, tmp_path):
        m = self._model_with_beam()
        out = str(tmp_path / "out.ifc")
        m.export(out)
        import ifcopenshell

        f = ifcopenshell.open(out)
        assert len(f.by_type("IfcBeam")) == 1

    def test_export_unknown_extension_raises(self, tmp_path):
        m = self._model_with_beam()
        with pytest.raises((ValueError, ImportError)):
            m.export(str(tmp_path / "out.xyz"))


# ---------------------------------------------------------------------------
# TC3 — handle.add() raises ValueError on invalid element
# ---------------------------------------------------------------------------


class TestHandleAddValidation:
    """TC3: storey.add() / bridge_part.add() raises ValueError on bad element."""

    def test_add_zero_length_beam_raises(self):
        m = IfcModel(name="T", schema=IfcSchema.IFC4)
        floor = m.add_site("S").add_building("B").add_storey("GF")
        zero_axis = Line(Vec(0, 0, 0), Vec(0, 0, 0))
        with pytest.raises(ValueError):
            # Line with zero length → validator error → ValueError from model.add
            floor.add(PendingBeam(zero_axis, _SQUARE_PROFILE))

    def test_add_beam_with_too_few_profile_points_raises(self):
        m = IfcModel(name="T", schema=IfcSchema.IFC4)
        floor = m.add_site("S").add_building("B").add_storey("GF")
        tiny_profile = [Vec(0, 0), Vec(1, 0)]  # only 2 points
        with pytest.raises(ValueError):
            floor.add(PendingBeam(_BEAM_AXIS, tiny_profile))


# ---------------------------------------------------------------------------
# TC5 — LengthUnit.FOOT / INCH raise NotImplementedError in IfcModel
# ---------------------------------------------------------------------------


class TestLengthUnitImperial:
    """TC5: IfcModel raises NotImplementedError for FOOT and INCH units."""

    def test_foot_raises(self):
        from ifckit.schema import LengthUnit

        with pytest.raises(NotImplementedError, match="LengthUnit.FOOT"):
            IfcModel(name="T", schema=IfcSchema.IFC4, unit=LengthUnit.FOOT)

    def test_inch_raises(self):
        from ifckit.schema import LengthUnit

        with pytest.raises(NotImplementedError, match="LengthUnit.INCH"):
            IfcModel(name="T", schema=IfcSchema.IFC4, unit=LengthUnit.INCH)
