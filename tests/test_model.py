"""Tests for ifckit.model — IfcModel hierarchy (IFC4 and IFC4X3)"""
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
        dummy = BridgeHandle(ifc4.ifc_file.by_type("IfcProject")[0])
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
