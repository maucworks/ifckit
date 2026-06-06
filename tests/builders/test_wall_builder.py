"""Tests for WallBuilder and SlabBuilder."""
import math
import pytest
import ifcopenshell

from ifckit.geometry import Vec, Plane
from ifckit.elements.building import PendingWall, PendingSlab
from ifckit.builders.wall import WallBuilder
from ifckit.builders.slab import SlabBuilder


FOOTPRINT = [Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 0.3, 0), Vec(0, 0.3, 0)]
PLANE = Plane.world_xy()


class TestWallBuilder:
    def test_produces_ifc_wall(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingWall(FOOTPRINT, PLANE, 3.0, name="W1")
        builder = WallBuilder()
        entity = builder.build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.is_a("IfcWall")
        assert entity.Name == "W1"

    def test_wall_has_representation(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingWall(FOOTPRINT, PLANE, 3.0)
        builder = WallBuilder()
        entity = builder.build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.Representation is not None

    def test_wall_has_extruded_solid(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingWall(FOOTPRINT, PLANE, 3.0)
        builder = WallBuilder()
        builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        solids = ifc4_model.ifc_file.by_type("IfcExtrudedAreaSolid")
        assert len(solids) == 1
        assert solids[0].Depth == pytest.approx(3.0)

    def test_wall_has_profile(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingWall(FOOTPRINT, PLANE, 3.0)
        builder = WallBuilder()
        builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        profiles = ifc4_model.ifc_file.by_type("IfcArbitraryClosedProfileDef")
        assert len(profiles) == 1

    def test_wall_contained_in_storey(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingWall(FOOTPRINT, PLANE, 3.0)
        builder = WallBuilder()
        builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        rels = ifc4_model.ifc_file.by_type("IfcRelContainedInSpatialStructure")
        assert len(rels) == 1
        assert rels[0].RelatingStructure == ifc4_storey.entity

    def test_wall_has_local_placement(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingWall(FOOTPRINT, PLANE, 3.0)
        builder = WallBuilder()
        entity = builder.build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.ObjectPlacement is not None

    def test_via_registry(self, ifc4_model, ifc4_storey, body_context):
        from ifckit.builders import default_registry
        registry = default_registry()
        pending = PendingWall(FOOTPRINT, PLANE, 3.0, name="RegistryWall")
        entity = registry.build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.is_a("IfcWall")

    def test_file_parses_after_save(self, ifc4_model, ifc4_storey, body_context, tmp_path):
        pending = PendingWall(FOOTPRINT, PLANE, 3.0)
        WallBuilder().build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        path = str(tmp_path / "wall.ifc")
        ifc4_model.save(path)
        reopened = ifcopenshell.open(path)
        assert len(reopened.by_type("IfcWall")) == 1
        assert len(reopened.by_type("IfcExtrudedAreaSolid")) == 1


class TestWallBuilderNonXYPlane:
    """Solid Position must be identity for any plane; orientation lives in ObjectPlacement only."""

    def test_xz_plane_solid_position_is_identity(self, ifc4_model, ifc4_storey, body_context):
        """Solid extrusion axis must be (0,0,1) — not world plane.z_axis — to avoid double rotation."""
        footprint = [Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 0, 0.3), Vec(0, 0, 0.3)]
        pending = PendingWall(footprint, Plane.world_xz(), 3.0)
        WallBuilder().build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        solid = ifc4_model.ifc_file.by_type("IfcExtrudedAreaSolid")[0]
        axis = solid.Position.Axis.DirectionRatios
        assert list(axis) == pytest.approx([0.0, 0.0, 1.0])

    def test_xz_plane_produces_wall(self, ifc4_model, ifc4_storey, body_context):
        footprint = [Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 0, 0.3), Vec(0, 0, 0.3)]
        pending = PendingWall(footprint, Plane.world_xz(), 3.0)
        entity = WallBuilder().build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.is_a("IfcWall")


class TestSlabBuilder:
    def test_produces_ifc_slab(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingSlab(FOOTPRINT, PLANE, 0.2, name="S1")
        builder = SlabBuilder()
        entity = builder.build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.is_a("IfcSlab")
        assert entity.Name == "S1"

    def test_slab_depth_matches_thickness(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingSlab(FOOTPRINT, PLANE, 0.25)
        SlabBuilder().build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        solids = ifc4_model.ifc_file.by_type("IfcExtrudedAreaSolid")
        assert solids[0].Depth == pytest.approx(0.25)

    def test_slab_has_representation(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingSlab(FOOTPRINT, PLANE, 0.2)
        entity = SlabBuilder().build(
            ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context
        )
        assert entity.Representation is not None

    def test_slab_contained_in_storey(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingSlab(FOOTPRINT, PLANE, 0.2)
        SlabBuilder().build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        rels = ifc4_model.ifc_file.by_type("IfcRelContainedInSpatialStructure")
        assert len(rels) == 1

    def test_file_parses_after_save(self, ifc4_model, ifc4_storey, body_context, tmp_path):
        pending = PendingSlab(FOOTPRINT, PLANE, 0.2)
        SlabBuilder().build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        path = str(tmp_path / "slab.ifc")
        ifc4_model.save(path)
        reopened = ifcopenshell.open(path)
        assert len(reopened.by_type("IfcSlab")) == 1


class TestSlabBuilderNonXYPlane:
    """Solid Position must be identity for any plane; orientation lives in ObjectPlacement only."""

    def test_xz_plane_solid_position_is_identity(self, ifc4_model, ifc4_storey, body_context):
        """Solid extrusion axis must be (0,0,1) — not world plane.z_axis — to avoid double rotation."""
        footprint = [Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 0, 0.3), Vec(0, 0, 0.3)]
        pending = PendingSlab(footprint, Plane.world_xz(), 0.2)
        SlabBuilder().build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)
        solid = ifc4_model.ifc_file.by_type("IfcExtrudedAreaSolid")[0]
        axis = solid.Position.Axis.DirectionRatios
        assert list(axis) == pytest.approx([0.0, 0.0, 1.0])
