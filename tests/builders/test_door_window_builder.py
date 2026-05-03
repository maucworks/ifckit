"""
tests/builders/test_door_window_builder.py
==========================================

Builder-level tests for build_door / build_window (IfcRelFillsElement).
"""

import pytest
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.guid

from ifckit.builders._geom import get_body_context
from ifckit.builders.door_window import build_door, build_window, _assign_type
from ifckit.builders.opening import build_opening
from ifckit.elements.opening import PendingDoor, PendingOpening, PendingWindow
from ifckit.geometry import Plane, Vec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ifc4_setup():
    """Returns (ifc_file, storey, opening_entity, ctx)."""
    f = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="P")
    ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    ctx_root = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    ctx = f.create_entity(
        "IfcGeometricRepresentationSubContext",
        ContextIdentifier="Body",
        ContextType="Model",
        ParentContext=ctx_root,
        TargetView="MODEL_VIEW",
    )
    storey = ifcopenshell.api.run(
        "root.create_entity", f, ifc_class="IfcBuildingStorey", name="GF"
    )
    ax = f.create_entity(
        "IfcAxis2Placement3D",
        Location=f.create_entity("IfcCartesianPoint", Coordinates=[0.0, 0.0, 0.0]),
    )
    storey.ObjectPlacement = f.create_entity(
        "IfcLocalPlacement", RelativePlacement=ax
    )
    wall = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall", name="W")
    ifcopenshell.api.run(
        "spatial.assign_container", f, products=[wall], relating_structure=storey
    )
    pending_op = PendingOpening(
        plane=Plane(Vec(1, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
        width=0.9, height=2.1, name="OP1"
    )
    opening = build_opening(f, pending_op, wall, storey, ctx)
    return f, storey, opening, ctx


def _door(**kwargs):
    defaults = dict(overall_width=0.9, overall_height=2.1, name="D1")
    defaults.update(kwargs)
    return PendingDoor(**defaults)


def _window(**kwargs):
    defaults = dict(overall_width=1.2, overall_height=1.4, name="W1")
    defaults.update(kwargs)
    return PendingWindow(**defaults)


# ===========================================================================
# IfcDoor
# ===========================================================================


class TestBuildDoor:
    def test_creates_ifc_door(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        door = build_door(f, _door(), opening, storey, ctx)
        assert door.is_a("IfcDoor")

    def test_creates_rel_fills_element(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        door = build_door(f, _door(), opening, storey, ctx)
        fills = f.by_type("IfcRelFillsElement")
        assert len(fills) == 1
        rel = fills[0]
        assert rel.RelatingOpeningElement == opening
        assert rel.RelatedBuildingElement == door

    def test_door_overall_dimensions(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        door = build_door(f, _door(overall_width=0.95, overall_height=2.2), opening, storey, ctx)
        assert door.OverallWidth == pytest.approx(0.95)
        assert door.OverallHeight == pytest.approx(2.2)

    def test_door_name_preserved(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        door = build_door(f, _door(name="MyDoor"), opening, storey, ctx)
        assert door.Name == "MyDoor"

    def test_door_contained_in_storey(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        door = build_door(f, _door(), opening, storey, ctx)
        containments = f.by_type("IfcRelContainedInSpatialStructure")
        contained = [p for rel in containments for p in rel.RelatedElements]
        assert door in contained

    def test_door_has_representation(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        door = build_door(f, _door(), opening, storey, ctx)
        assert door.Representation is not None

    def test_door_operation_type_set(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        door = build_door(f, _door(operation_type="SINGLE_SWING_LEFT"), opening, storey, ctx)
        assert door.OperationType == "SINGLE_SWING_LEFT"

    def test_door_psets_written(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        door = build_door(f, _door(), opening, storey, ctx)
        pset_names = {
            rel.RelatingPropertyDefinition.Name
            for rel in f.by_type("IfcRelDefinesByProperties")
            if rel.RelatedObjects and door in rel.RelatedObjects
        }
        assert "EPset_IfcKit_Geometry" in pset_names

    def test_door_with_type_creates_rel_defines_by_type(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        type_ent = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoorType", name="DT")
        door = build_door(f, _door(), opening, storey, ctx, type_entity=type_ent)
        rels = f.by_type("IfcRelDefinesByType")
        assert any(
            rel.RelatingType == type_ent and door in rel.RelatedObjects
            for rel in rels
        )

    def test_multiple_doors_same_type_one_relation(self, ifc4_setup):
        """Multiple doors sharing a type should use ONE IfcRelDefinesByType."""
        f, storey, opening, ctx = ifc4_setup
        type_ent = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoorType", name="DT")
        d1 = build_door(f, _door(name="D1"), opening, storey, ctx, type_entity=type_ent)
        # Need a second opening for the second door.
        wall2 = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall", name="W2")
        ifcopenshell.api.run("spatial.assign_container", f, products=[wall2], relating_structure=storey)
        op2 = build_opening(
            f,
            PendingOpening(plane=Plane(Vec(3,0,0), Vec(1,0,0), Vec(0,1,0)), width=0.9, height=2.1),
            wall2, storey, ctx
        )
        d2 = build_door(f, _door(name="D2"), op2, storey, ctx, type_entity=type_ent)
        rels = [r for r in f.by_type("IfcRelDefinesByType") if r.RelatingType == type_ent]
        assert len(rels) == 1
        assert d1 in rels[0].RelatedObjects
        assert d2 in rels[0].RelatedObjects


# ===========================================================================
# IfcWindow
# ===========================================================================


class TestBuildWindow:
    def test_creates_ifc_window(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        win = build_window(f, _window(), opening, storey, ctx)
        assert win.is_a("IfcWindow")

    def test_creates_rel_fills_element(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        win = build_window(f, _window(), opening, storey, ctx)
        fills = f.by_type("IfcRelFillsElement")
        assert any(rel.RelatedBuildingElement == win for rel in fills)

    def test_window_overall_dimensions(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        win = build_window(f, _window(overall_width=1.5, overall_height=1.2), opening, storey, ctx)
        assert win.OverallWidth == pytest.approx(1.5)
        assert win.OverallHeight == pytest.approx(1.2)

    def test_window_name_preserved(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        win = build_window(f, _window(name="MyWindow"), opening, storey, ctx)
        assert win.Name == "MyWindow"

    def test_window_contained_in_storey(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        win = build_window(f, _window(), opening, storey, ctx)
        contained = [p for rel in f.by_type("IfcRelContainedInSpatialStructure") for p in rel.RelatedElements]
        assert win in contained

    def test_window_with_type(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        type_ent = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWindowType", name="WT")
        win = build_window(f, _window(), opening, storey, ctx, type_entity=type_ent)
        rels = f.by_type("IfcRelDefinesByType")
        assert any(rel.RelatingType == type_ent and win in rel.RelatedObjects for rel in rels)


# ===========================================================================
# _assign_type helper
# ===========================================================================


class TestAssignType:
    def test_first_assignment_creates_relation(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        door = build_door(f, _door(), opening, storey, ctx)
        type_ent = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoorType", name="T")
        before = len(f.by_type("IfcRelDefinesByType"))
        _assign_type(f, door, type_ent)
        assert len(f.by_type("IfcRelDefinesByType")) == before + 1

    def test_second_assignment_reuses_relation(self, ifc4_setup):
        f, storey, opening, ctx = ifc4_setup
        d1 = build_door(f, _door(name="D1"), opening, storey, ctx)
        wall2 = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall", name="W2")
        ifcopenshell.api.run("spatial.assign_container", f, products=[wall2], relating_structure=storey)
        op2 = build_opening(
            f,
            PendingOpening(plane=Plane(Vec(3,0,0), Vec(1,0,0), Vec(0,1,0)), width=0.9, height=2.1),
            wall2, storey, ctx
        )
        d2 = build_door(f, _door(name="D2"), op2, storey, ctx)
        type_ent = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcDoorType", name="T")
        _assign_type(f, d1, type_ent)
        before = len(f.by_type("IfcRelDefinesByType"))
        _assign_type(f, d2, type_ent)
        assert len(f.by_type("IfcRelDefinesByType")) == before  # reused, not new
        rel = next(r for r in f.by_type("IfcRelDefinesByType") if r.RelatingType == type_ent)
        assert d1 in rel.RelatedObjects
        assert d2 in rel.RelatedObjects
