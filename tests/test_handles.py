"""
tests/test_handles.py
=====================

Tests for ifckit.handles — handle classes that wrap ifcopenshell entities.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, PropertyMock

from ifckit.handles import (
    Handle,
    SiteHandle,
    BuildingHandle,
    StoreyHandle,
    BridgeHandle,
    BridgePartHandle,
    AlignmentHandle,
    EntityHandle,
)


class _MockModel:
    """Minimal mock that records delegation calls."""

    def __init__(self):
        self.add_building = MagicMock(return_value="building")
        self.add_bridge = MagicMock(return_value="bridge")
        self.add_alignment = MagicMock(return_value="alignment")
        self.add_storey = MagicMock(return_value="storey")
        self.add = MagicMock(return_value="entity")
        self._clear_container = MagicMock(return_value=3)
        self.add_bridge_part = MagicMock(return_value="bridge_part")


# ---------------------------------------------------------------------------
# Handle (base class)
# ---------------------------------------------------------------------------


class TestHandle:
    def test_init_stores_entity_and_model(self):
        entity = MagicMock()
        model = _MockModel()
        h = Handle(entity, model)
        assert h.entity is entity
        assert h._model_ref is model

    def test_repr(self):
        entity = MagicMock()
        entity.is_a.return_value = "IfcSite"
        h = Handle(entity, _MockModel())
        assert repr(h) == "Handle(IfcSite)"

    def test_entity_property_returns_same(self):
        entity = MagicMock()
        h = Handle(entity, _MockModel())
        assert h.entity is entity

    def test_model_ref_property_returns_same(self):
        model = _MockModel()
        h = Handle(MagicMock(), model)
        assert h._model_ref is model


# ---------------------------------------------------------------------------
# SiteHandle
# ---------------------------------------------------------------------------


class TestSiteHandle:
    def test_add_building_delegates(self):
        model = _MockModel()
        entity = MagicMock()
        site = SiteHandle(entity, model)
        result = site.add_building("Tower", description="Main")
        model.add_building.assert_called_once_with(site, "Tower", description="Main")
        assert result == "building"

    def test_add_bridge_delegates(self):
        model = _MockModel()
        site = SiteHandle(MagicMock(), model)
        result = site.add_bridge("Bridge")
        model.add_bridge.assert_called_once_with(site, "Bridge", description=None)
        assert result == "bridge"

    def test_add_alignment_delegates(self):
        model = _MockModel()
        site = SiteHandle(MagicMock(), model)
        result = site.add_alignment("A1")
        model.add_alignment.assert_called_once_with(site, "A1")
        assert result == "alignment"

    def test_clear_delegates(self):
        model = _MockModel()
        entity = MagicMock()
        site = SiteHandle(entity, model)
        result = site.clear()
        model._clear_container.assert_called_once_with(entity)
        assert result == 3

    def test_repr(self):
        entity = MagicMock()
        entity.is_a.return_value = "IfcSite"
        site = SiteHandle(entity, _MockModel())
        assert repr(site) == "SiteHandle(IfcSite)"


# ---------------------------------------------------------------------------
# BuildingHandle
# ---------------------------------------------------------------------------


class TestBuildingHandle:
    def test_add_storey_delegates(self):
        model = _MockModel()
        building = BuildingHandle(MagicMock(), model)
        result = building.add_storey("Level 1", elevation=5.0)
        model.add_storey.assert_called_once_with(building, "Level 1", elevation=5.0)
        assert result == "storey"

    def test_add_storey_default_elevation(self):
        model = _MockModel()
        building = BuildingHandle(MagicMock(), model)
        building.add_storey("Ground")
        model.add_storey.assert_called_once_with(building, "Ground", elevation=0.0)

    def test_clear_delegates(self):
        model = _MockModel()
        entity = MagicMock()
        building = BuildingHandle(entity, model)
        building.clear()
        model._clear_container.assert_called_once_with(entity)

    def test_repr(self):
        entity = MagicMock()
        entity.is_a.return_value = "IfcBuilding"
        h = BuildingHandle(entity, _MockModel())
        assert repr(h) == "BuildingHandle(IfcBuilding)"


# ---------------------------------------------------------------------------
# StoreyHandle
# ---------------------------------------------------------------------------


class TestStoreyHandle:
    def test_add_delegates(self):
        model = _MockModel()
        storey = StoreyHandle(MagicMock(), model)
        pending = MagicMock()
        result = storey.add(pending)
        model.add.assert_called_once_with(pending, storey)
        assert result == "entity"

    def test_add_space_delegates(self):
        model = _MockModel()
        model.add = MagicMock(return_value="space_entity")
        storey = StoreyHandle(MagicMock(), model)
        result = storey.add_space(
            footprint=[(0, 0), (1, 0), (1, 1)],
            height=3.0,
            name="R-001",
            long_name="Office",
        )
        model.add.assert_called_once()
        args, _ = model.add.call_args
        pending = args[0]
        assert pending.name == "R-001"
        assert pending.height == 3.0
        assert result == "space_entity"

    def test_add_space_defaults(self):
        model = _MockModel()
        model.add = MagicMock(return_value="space_entity")
        storey = StoreyHandle(MagicMock(), model)
        storey.add_space(footprint=[(0, 0), (1, 0), (1, 1)], height=2.5)
        args, _ = model.add.call_args
        pending = args[0]
        assert pending.name == ""
        assert pending.long_name == ""

    def test_clear_delegates(self):
        model = _MockModel()
        entity = MagicMock()
        storey = StoreyHandle(entity, model)
        storey.clear()
        model._clear_container.assert_called_once_with(entity)

    def test_repr(self):
        entity = MagicMock()
        entity.is_a.return_value = "IfcBuildingStorey"
        h = StoreyHandle(entity, _MockModel())
        assert repr(h) == "StoreyHandle(IfcBuildingStorey)"


# ---------------------------------------------------------------------------
# BridgeHandle
# ---------------------------------------------------------------------------


class TestBridgeHandle:
    def test_add_bridge_part_delegates(self):
        model = _MockModel()
        bridge = BridgeHandle(MagicMock(), model)
        result = bridge.add_bridge_part("Segment", part_type="DECK")
        model.add_bridge_part.assert_called_once_with(bridge, "Segment", part_type="DECK")
        assert result == "bridge_part"

    def test_clear_delegates(self):
        model = _MockModel()
        entity = MagicMock()
        bridge = BridgeHandle(entity, model)
        bridge.clear()
        model._clear_container.assert_called_once_with(entity)

    def test_repr(self):
        entity = MagicMock()
        entity.is_a.return_value = "IfcBridge"
        h = BridgeHandle(entity, _MockModel())
        assert repr(h) == "BridgeHandle(IfcBridge)"


# ---------------------------------------------------------------------------
# BridgePartHandle
# ---------------------------------------------------------------------------


class TestBridgePartHandle:
    def test_add_delegates(self):
        model = _MockModel()
        bp = BridgePartHandle(MagicMock(), model)
        pending = MagicMock()
        result = bp.add(pending)
        model.add.assert_called_once_with(pending, bp)
        assert result == "entity"

    def test_clear_delegates(self):
        model = _MockModel()
        entity = MagicMock()
        bp = BridgePartHandle(entity, model)
        bp.clear()
        model._clear_container.assert_called_once_with(entity)

    def test_repr(self):
        entity = MagicMock()
        entity.is_a.return_value = "IfcBridgePart"
        h = BridgePartHandle(entity, _MockModel())
        assert repr(h) == "BridgePartHandle(IfcBridgePart)"


# ---------------------------------------------------------------------------
# AlignmentHandle
# ---------------------------------------------------------------------------


class TestAlignmentHandle:
    def test_repr(self):
        entity = MagicMock()
        entity.is_a.return_value = "IfcAlignment"
        h = AlignmentHandle(entity, _MockModel())
        assert repr(h) == "AlignmentHandle(IfcAlignment)"


# ---------------------------------------------------------------------------
# EntityHandle
# ---------------------------------------------------------------------------


class TestEntityHandle:
    def test_init_sets_footprint_curves_none(self):
        eh = EntityHandle(MagicMock(), _MockModel())
        assert eh.footprint_curves is None

    def test_footprint_curves_read_write(self):
        eh = EntityHandle(MagicMock(), _MockModel())
        curves = ["curve1", "curve2"]
        eh.footprint_curves = curves
        assert eh.footprint_curves is curves

    def test_add_delegates(self):
        model = _MockModel()
        entity = MagicMock()
        eh = EntityHandle(entity, model)
        pending = MagicMock()
        result = eh.add(pending)
        model.add.assert_called_once_with(pending, eh)
        assert result == "entity"

    def test_repr(self):
        entity = MagicMock()
        entity.is_a.return_value = "IfcWall"
        h = EntityHandle(entity, _MockModel())
        assert repr(h) == "EntityHandle(IfcWall)"
