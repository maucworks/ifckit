"""
tests/builders/test_type_builders.py
=====================================

Builder-level tests for build_door_type / build_window_type.
"""

import pytest
import ifcopenshell
import ifcopenshell.api

from ifckit.builders.types import build_door_type, build_window_type
from ifckit.elements.types import PendingDoorType, PendingWindowType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ifc4_file():
    f = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="P")
    ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    return f


@pytest.fixture
def ifc2x3_file():
    f = ifcopenshell.file(schema="IFC2X3")
    person = ifcopenshell.api.run("owner.add_person", f)
    org = ifcopenshell.api.run("owner.add_organisation", f)
    ifcopenshell.api.run("owner.add_person_and_organisation", f, person=person, organisation=org)
    ifcopenshell.api.run(
        "owner.add_application", f,
        application_developer=org,
        version="1",
        application_full_name="ifckit-test",
        application_identifier="ifckit-test",
    )
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="P")
    ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    return f


def _door_type(**kwargs):
    defaults = dict(overall_width=0.9, overall_height=2.1)
    defaults.update(kwargs)
    return PendingDoorType(**defaults)


def _window_type(**kwargs):
    defaults = dict(overall_width=1.2, overall_height=1.4)
    defaults.update(kwargs)
    return PendingWindowType(**defaults)


# ===========================================================================
# build_door_type — IFC4
# ===========================================================================


class TestBuildDoorTypeIfc4:
    def test_creates_ifc_door_type(self, ifc4_file):
        dt = build_door_type(ifc4_file, _door_type(name="DT1"))
        assert dt.is_a("IfcDoorType")

    def test_name_preserved(self, ifc4_file):
        dt = build_door_type(ifc4_file, _door_type(name="MyDoorType"))
        assert dt.Name == "MyDoorType"

    def test_operation_type_set(self, ifc4_file):
        dt = build_door_type(ifc4_file, _door_type(operation_type="SINGLE_SWING_LEFT"))
        assert dt.OperationType == "SINGLE_SWING_LEFT"

    def test_lining_pset_written(self, ifc4_file):
        dt = build_door_type(ifc4_file, _door_type(lining_depth=0.1, lining_thickness=0.05))
        pset_names = {
            rel.RelatingPropertyDefinition.Name
            for rel in ifc4_file.by_type("IfcRelDefinesByProperties")
            if rel.RelatedObjects and dt in rel.RelatedObjects
        }
        assert "IfcDoorLiningProperties" in pset_names

    def test_panel_pset_written(self, ifc4_file):
        dt = build_door_type(ifc4_file, _door_type(panel_depth=0.04, panel_operation="SWINGING"))
        pset_names = {
            rel.RelatingPropertyDefinition.Name
            for rel in ifc4_file.by_type("IfcRelDefinesByProperties")
            if rel.RelatedObjects and dt in rel.RelatedObjects
        }
        assert "IfcDoorPanelProperties" in pset_names

    def test_no_lining_pset_when_all_none(self, ifc4_file):
        """If no lining params are set, IfcDoorLiningProperties pset is NOT written."""
        dt = build_door_type(ifc4_file, _door_type())
        pset_names = {
            rel.RelatingPropertyDefinition.Name
            for rel in ifc4_file.by_type("IfcRelDefinesByProperties")
            if rel.RelatedObjects and dt in rel.RelatedObjects
        }
        assert "IfcDoorLiningProperties" not in pset_names

    def test_user_pset_written(self, ifc4_file):
        dt = build_door_type(ifc4_file, _door_type(properties={"material": "oak"}))
        pset_names = {
            rel.RelatingPropertyDefinition.Name
            for rel in ifc4_file.by_type("IfcRelDefinesByProperties")
            if rel.RelatedObjects and dt in rel.RelatedObjects
        }
        assert "EPset_IfcKit" in pset_names

    def test_all_lining_fields_written(self, ifc4_file):
        dt = build_door_type(ifc4_file, _door_type(
            lining_depth=0.1,
            lining_thickness=0.05,
            threshold_depth=0.02,
            threshold_thickness=0.01,
            threshold_offset=0.005,
            transom_thickness=0.04,
            transom_offset=2.0,
            lining_offset=0.005,
            casing_thickness=0.02,
            casing_depth=0.06,
            lining_to_panel_offset_x=0.01,
            lining_to_panel_offset_y=0.01,
        ))
        psets = {
            rel.RelatingPropertyDefinition.Name: rel.RelatingPropertyDefinition
            for rel in ifc4_file.by_type("IfcRelDefinesByProperties")
            if rel.RelatedObjects and dt in rel.RelatedObjects
        }
        lining_pset = psets.get("IfcDoorLiningProperties")
        assert lining_pset is not None
        assert lining_pset.LiningDepth is not None
        assert lining_pset.CasingDepth is not None
        assert lining_pset.LiningToPanelOffsetX is not None


# ===========================================================================
# build_door_type — IFC2X3
# ===========================================================================


class TestBuildDoorTypeIfc2x3:
    def test_creates_ifc_door_style(self, ifc2x3_file):
        dt = build_door_type(ifc2x3_file, _door_type(name="DS1"))
        assert dt.is_a("IfcDoorStyle")

    def test_lining_pset_written_ifc2x3(self, ifc2x3_file):
        dt = build_door_type(ifc2x3_file, _door_type(lining_depth=0.1))
        pset_names = {
            rel.RelatingPropertyDefinition.Name
            for rel in ifc2x3_file.by_type("IfcRelDefinesByProperties")
            if rel.RelatedObjects and dt in rel.RelatedObjects
        }
        assert "IfcDoorLiningProperties" in pset_names


# ===========================================================================
# build_window_type — IFC4
# ===========================================================================


class TestBuildWindowTypeIfc4:
    def test_creates_ifc_window_type(self, ifc4_file):
        wt = build_window_type(ifc4_file, _window_type(name="WT1"))
        assert wt.is_a("IfcWindowType")

    def test_name_preserved(self, ifc4_file):
        wt = build_window_type(ifc4_file, _window_type(name="MyWindowType"))
        assert wt.Name == "MyWindowType"

    def test_lining_pset_written(self, ifc4_file):
        wt = build_window_type(ifc4_file, _window_type(lining_depth=0.08, lining_thickness=0.04))
        pset_names = {
            rel.RelatingPropertyDefinition.Name
            for rel in ifc4_file.by_type("IfcRelDefinesByProperties")
            if rel.RelatedObjects and wt in rel.RelatedObjects
        }
        assert "IfcWindowLiningProperties" in pset_names

    def test_panel_pset_written(self, ifc4_file):
        wt = build_window_type(ifc4_file, _window_type(panel_depth=0.03, panel_operation="SIDEHUNGRIGHTHAND"))
        pset_names = {
            rel.RelatingPropertyDefinition.Name
            for rel in ifc4_file.by_type("IfcRelDefinesByProperties")
            if rel.RelatedObjects and wt in rel.RelatedObjects
        }
        assert "IfcWindowPanelProperties" in pset_names

    def test_no_lining_pset_when_all_none(self, ifc4_file):
        wt = build_window_type(ifc4_file, _window_type())
        pset_names = {
            rel.RelatingPropertyDefinition.Name
            for rel in ifc4_file.by_type("IfcRelDefinesByProperties")
            if rel.RelatedObjects and wt in rel.RelatedObjects
        }
        assert "IfcWindowLiningProperties" not in pset_names

    def test_all_lining_fields(self, ifc4_file):
        wt = build_window_type(ifc4_file, _window_type(
            lining_depth=0.08,
            transom_thickness=0.03,
            mullion_thickness=0.03,
            first_mullion_offset=0.4,
            second_mullion_offset=0.6,
        ))
        psets = {
            rel.RelatingPropertyDefinition.Name: rel.RelatingPropertyDefinition
            for rel in ifc4_file.by_type("IfcRelDefinesByProperties")
            if rel.RelatedObjects and wt in rel.RelatedObjects
        }
        lining = psets.get("IfcWindowLiningProperties")
        assert lining is not None
        assert lining.MullionThickness is not None
        assert lining.FirstMullionOffset is not None


# ===========================================================================
# build_window_type — IFC2X3
# ===========================================================================


class TestBuildWindowTypeIfc2x3:
    def test_creates_ifc_window_style(self, ifc2x3_file):
        wt = build_window_type(ifc2x3_file, _window_type(name="WS1"))
        assert wt.is_a("IfcWindowStyle")
