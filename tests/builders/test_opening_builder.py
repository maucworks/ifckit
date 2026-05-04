"""
tests/builders/test_opening_builder.py
=======================================

Builder-level tests for build_opening (IfcRelVoidsElement).
These tests operate directly on ifcopenshell, bypassing IfcModel.
"""

import pytest
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.guid

from ifckit.builders._geom import get_body_context
from ifckit.builders.opening import build_opening
from ifckit.elements.opening import PendingOpening
from ifckit.geometry import Plane, Vec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ifc4_file():
    f = ifcopenshell.file(schema="IFC4")
    project = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="P")
    ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    f.create_entity(
        "IfcGeometricRepresentationSubContext",
        ContextIdentifier="Body",
        ContextType="Model",
        ParentContext=ctx,
        TargetView="MODEL_VIEW",
    )
    site = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcSite", name="S")
    bldg = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuilding", name="B")
    storey = ifcopenshell.api.run(
        "root.create_entity", f, ifc_class="IfcBuildingStorey", name="GF"
    )
    # Minimal placement for storey
    ax = f.create_entity(
        "IfcAxis2Placement3D",
        Location=f.create_entity("IfcCartesianPoint", Coordinates=[0.0, 0.0, 0.0]),
    )
    storey.ObjectPlacement = f.create_entity(
        "IfcLocalPlacement", RelativePlacement=ax
    )
    return f, storey


@pytest.fixture
def wall_entity(ifc4_file):
    f, storey = ifc4_file
    wall = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcWall", name="W")
    ifcopenshell.api.run(
        "spatial.assign_container", f, products=[wall], relating_structure=storey
    )
    return wall


def _opening(**kwargs):
    defaults = dict(
        plane=Plane(Vec(1, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
        width=0.9,
        height=2.1,
        name="OP1",
    )
    defaults.update(kwargs)
    return PendingOpening(**defaults)


# ===========================================================================
# Tests
# ===========================================================================


class TestBuildOpening:
    def test_creates_ifc_opening_element(self, ifc4_file, wall_entity):
        f, storey = ifc4_file
        ctx = get_body_context(f)
        op = build_opening(f, _opening(), wall_entity, storey, ctx)
        assert op.is_a("IfcOpeningElement")

    def test_creates_rel_voids_element(self, ifc4_file, wall_entity):
        f, storey = ifc4_file
        ctx = get_body_context(f)
        op = build_opening(f, _opening(), wall_entity, storey, ctx)
        voids = f.by_type("IfcRelVoidsElement")
        assert len(voids) == 1
        rel = voids[0]
        assert rel.RelatingBuildingElement == wall_entity
        assert rel.RelatedOpeningElement == op

    def test_opening_has_representation(self, ifc4_file, wall_entity):
        f, storey = ifc4_file
        ctx = get_body_context(f)
        op = build_opening(f, _opening(), wall_entity, storey, ctx)
        assert op.Representation is not None

    def test_opening_has_placement(self, ifc4_file, wall_entity):
        f, storey = ifc4_file
        ctx = get_body_context(f)
        op = build_opening(f, _opening(), wall_entity, storey, ctx)
        assert op.ObjectPlacement is not None

    # Removed test - IfcOpeningElement does not require spatial containment per IFC spec.
    # It is voided into the host element via IfcRelVoidsElement.

    def test_opening_name_preserved(self, ifc4_file, wall_entity):
        f, storey = ifc4_file
        ctx = get_body_context(f)
        op = build_opening(f, _opening(name="MyOpening"), wall_entity, storey, ctx)
        assert op.Name == "MyOpening"

    def test_two_openings_two_voids(self, ifc4_file, wall_entity):
        f, storey = ifc4_file
        ctx = get_body_context(f)
        build_opening(f, _opening(name="OP1"), wall_entity, storey, ctx)
        build_opening(f, _opening(name="OP2", width=1.2), wall_entity, storey, ctx)
        assert len(f.by_type("IfcRelVoidsElement")) == 2

    def test_opening_psets_written(self, ifc4_file, wall_entity):
        f, storey = ifc4_file
        ctx = get_body_context(f)
        op = build_opening(f, _opening(), wall_entity, storey, ctx)
        pset_names = {
            rel.RelatingPropertyDefinition.Name
            for rel in f.by_type("IfcRelDefinesByProperties")
            if rel.RelatedObjects and op in rel.RelatedObjects
        }
        assert "EPset_IfcKit_Geometry" in pset_names

    def test_opening_user_properties(self, ifc4_file, wall_entity):
        f, storey = ifc4_file
        ctx = get_body_context(f)
        op = build_opening(f, _opening(properties={"FireRating": "EI30"}), wall_entity, storey, ctx)
        pset_names = {
            rel.RelatingPropertyDefinition.Name
            for rel in f.by_type("IfcRelDefinesByProperties")
            if rel.RelatedObjects and op in rel.RelatedObjects
        }
        assert "EPset_IfcKit" in pset_names


class TestAnchor:
    """Tests for PendingOpening anchor field and anchor_offset integration."""

    def test_default_anchor_is_s(self):
        op = _opening()
        assert op.anchor == "s"

    def test_anchor_stored(self):
        op = _opening(anchor="sw")
        assert op.anchor == "sw"

    def test_anchor_roundtrip(self):
        op = _opening(anchor="c")
        assert PendingOpening.from_dict(op.to_dict()).anchor == "c"

    def test_default_anchor_not_in_dict(self):
        """Default anchor 's' should be omitted from the serialised dict."""
        d = _opening(anchor="s").to_dict()
        assert "anchor" not in d

    def test_non_default_anchor_in_dict(self):
        d = _opening(anchor="sw").to_dict()
        assert d["anchor"] == "sw"

    def test_invalid_anchor_raises(self):
        with pytest.raises(ValueError, match="anchor"):
            _opening(anchor="xx")

    def test_build_opening_with_anchor_sw(self, ifc4_file, wall_entity):
        """Opening with anchor='sw' still creates a valid IfcOpeningElement."""
        f, storey = ifc4_file
        ctx = get_body_context(f)
        op = build_opening(f, _opening(anchor="sw"), wall_entity, storey, ctx)
        assert op.is_a("IfcOpeningElement")

    def test_build_opening_with_anchor_c(self, ifc4_file, wall_entity):
        """Opening with anchor='c' (centred) still creates a valid IfcOpeningElement."""
        f, storey = ifc4_file
        ctx = get_body_context(f)
        op = build_opening(f, _opening(anchor="c"), wall_entity, storey, ctx)
        assert op.is_a("IfcOpeningElement")
