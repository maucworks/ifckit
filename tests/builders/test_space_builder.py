"""Tests for SpaceBuilder."""
import pytest
import ifcopenshell

from ifckit.geometry import Vec
from ifckit.elements.space import PendingSpace
from ifckit.builders.space import SpaceBuilder


FOOTPRINT = [Vec(0, 0, 0), Vec(6, 0, 0), Vec(6, 4, 0), Vec(0, 4, 0)]


class TestSpaceBuilder:
    def test_produces_ifc_space(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingSpace(FOOTPRINT, 3.0, name="1.01")
        builder = SpaceBuilder()
        entity = builder.build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.is_a("IfcSpace")
        assert entity.Name == "1.01"

    def test_long_name(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingSpace(FOOTPRINT, 3.0, long_name="Meeting Room")
        builder = SpaceBuilder()
        entity = builder.build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.LongName == "Meeting Room"

    def test_predefined_type(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingSpace(FOOTPRINT, 3.0, predefined_type="PARKING")
        builder = SpaceBuilder()
        entity = builder.build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.PredefinedType == "PARKING"

    def test_has_body_representation(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingSpace(FOOTPRINT, 3.0)
        builder = SpaceBuilder()
        entity = builder.build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.Representation is not None
        identifiers = {
            r.RepresentationIdentifier
            for r in entity.Representation.Representations
        }
        assert "Body" in identifiers
        assert "FootPrint" in identifiers

    def test_has_extruded_solid(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingSpace(FOOTPRINT, 2.7)
        builder = SpaceBuilder()
        builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        solids = ifc4_model.ifc_file.by_type("IfcExtrudedAreaSolid")
        assert len(solids) == 1
        assert solids[0].Depth == pytest.approx(2.7)

    def test_has_footprint_polyline(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingSpace(FOOTPRINT, 3.0)
        builder = SpaceBuilder()
        builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        polylines = ifc4_model.ifc_file.by_type("IfcPolyline")
        assert len(polylines) >= 1

    def test_aggregated_under_storey(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingSpace(FOOTPRINT, 3.0)
        builder = SpaceBuilder()
        builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        rels = ifc4_model.ifc_file.by_type("IfcRelAggregates")
        storey_rels = [r for r in rels if r.RelatingObject == ifc4_storey.entity]
        assert len(storey_rels) >= 1
        products = [p for r in storey_rels for p in r.RelatedObjects]
        assert any(p.is_a("IfcSpace") for p in products)

    def test_wrong_type_raises(self, ifc4_model, ifc4_storey, body_context):
        from ifckit.elements.building import PendingWall
        from ifckit.geometry import Plane
        wrong = PendingWall(FOOTPRINT, Plane.world_xy(), 3.0)
        builder = SpaceBuilder()
        with pytest.raises(TypeError):
            builder.build(
                ifc4_model.ifc_file, wrong, ifc4_storey.entity, body_context
            )

    def test_registered_in_default_registry(self):
        from ifckit.builders import default_registry
        reg = default_registry()
        builder = reg.get("basic_space")
        assert isinstance(builder, SpaceBuilder)

    def test_via_storey_add(self, ifc4_model, ifc4_storey):
        pending = PendingSpace(FOOTPRINT, 3.0, name="R1")
        handle = ifc4_storey.add(pending)
        assert handle.entity.is_a("IfcSpace")

    def test_via_storey_add_space(self, ifc4_model, ifc4_storey):
        handle = ifc4_storey.add_space(FOOTPRINT, 3.0, name="R2",
                                        long_name="Boardroom")
        assert handle.entity.is_a("IfcSpace")
        assert handle.entity.Name == "R2"
        assert handle.entity.LongName == "Boardroom"
