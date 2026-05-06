"""
tests/builders/test_window_graph_ifc.py
=======================================

Integration tests: PendingWindow/PendingDoor with component_graph set →
geometry produced by the component-graph evaluator instead of built-in lining.

These tests build a full IFC file via IfcModel to verify the end-to-end path:
  PendingWindow.component_graph → build_window → _build_fill_from_graph
  → evaluate_component_graph → IfcExtrudedAreaSolid × N components
"""

from __future__ import annotations

import pytest

from ifckit import IfcModel, IfcSchema, PendingWall
from ifckit.elements.opening import PendingDoor, PendingOpening, PendingWindow
from ifckit.geometry import Plane, Vec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def model_with_wall():
    m = IfcModel("TestProject", schema=IfcSchema.IFC4)
    site = m.add_site("Site")
    bldg = m.add_building(site, "Building")
    storey = m.add_storey(bldg, "GF", elevation=0.0)
    wall = m.add(
        PendingWall(
            footprint=[Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 0.25, 0), Vec(0, 0.25, 0)],
            plane=Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
            height=3.0,
            name="W1",
        ),
        storey,
    )
    return m, storey, wall


def _opening_plane(x=1.0):
    return Plane(Vec(x, 0.0, 0.0), Vec(1, 0, 0), Vec(0, 1, 0))


# ---------------------------------------------------------------------------
# Window with component_graph="fixed_casement" — Model A path
# ---------------------------------------------------------------------------


class TestWindowWithFixedCasementGraph:
    def test_window_builds_without_error(self, model_with_wall):
        m, storey, wall = model_with_wall
        opening = m.add_opening(
            PendingOpening(width=1.0, height=1.2, plane=_opening_plane(1.0)),
            wall,
            storey,
        )
        window = m.add_window(
            PendingWindow(
                overall_width=1.0,
                overall_height=1.2,
                name="W-graph",
                component_graph="fixed_casement",
            ),
            opening,
            storey,
        )
        assert window is not None

    def test_window_is_ifc_window(self, model_with_wall):
        m, storey, wall = model_with_wall
        opening = m.add_opening(
            PendingOpening(width=1.0, height=1.2, plane=_opening_plane(1.0)),
            wall,
            storey,
        )
        window = m.add_window(
            PendingWindow(
                overall_width=1.0,
                overall_height=1.2,
                component_graph="fixed_casement",
            ),
            opening,
            storey,
        )
        assert window.entity.is_a("IfcWindow")

    def test_window_shape_has_two_solids(self, model_with_wall):
        """fixed_casement produces Lining + Glazing → 2 items in IfcShapeRepresentation."""
        m, storey, wall = model_with_wall
        opening = m.add_opening(
            PendingOpening(width=1.0, height=1.2, plane=_opening_plane(1.0)),
            wall,
            storey,
        )
        window = m.add_window(
            PendingWindow(
                overall_width=1.0,
                overall_height=1.2,
                component_graph="fixed_casement",
            ),
            opening,
            storey,
        )
        # Navigate via .entity to get IFC attributes
        reps = window.entity.Representation.Representations
        body_rep = next(r for r in reps if r.RepresentationIdentifier == "Body")
        assert len(body_rep.Items) == 2

    def test_lining_is_extruded_with_voids(self, model_with_wall):
        m, storey, wall = model_with_wall
        opening = m.add_opening(
            PendingOpening(width=1.0, height=1.2, plane=_opening_plane(1.0)),
            wall,
            storey,
        )
        window = m.add_window(
            PendingWindow(
                overall_width=1.0,
                overall_height=1.2,
                component_graph="fixed_casement",
            ),
            opening,
            storey,
        )
        reps = window.entity.Representation.Representations
        body_rep = next(r for r in reps if r.RepresentationIdentifier == "Body")
        profiles = []
        for item in body_rep.Items:
            # Unwrap IfcStyledItem to access the actual solid
            solid = item.Item if item.is_a("IfcStyledItem") else item
            profiles.append(solid.SweptArea.is_a())
        assert "IfcArbitraryProfileDefWithVoids" in profiles

    def test_window_fills_opening(self, model_with_wall):
        m, storey, wall = model_with_wall
        opening = m.add_opening(
            PendingOpening(width=1.0, height=1.2, plane=_opening_plane(1.0)),
            wall,
            storey,
        )
        window = m.add_window(
            PendingWindow(
                overall_width=1.0,
                overall_height=1.2,
                component_graph="fixed_casement",
            ),
            opening,
            storey,
        )
        ifc_file = m._file
        fills = ifc_file.by_type("IfcRelFillsElement")
        assert any(f.RelatedBuildingElement == window.entity for f in fills)


# ---------------------------------------------------------------------------
# Door with component_graph="door_flush" — Model A path
# ---------------------------------------------------------------------------


class TestDoorWithDoorFlushGraph:
    def test_door_builds_without_error(self, model_with_wall):
        m, storey, wall = model_with_wall
        opening = m.add_opening(
            PendingOpening(width=0.9, height=2.1, plane=_opening_plane(2.0)),
            wall,
            storey,
        )
        door = m.add_door(
            PendingDoor(
                overall_width=0.9,
                overall_height=2.1,
                name="D-graph",
                component_graph="door_flush",
            ),
            opening,
            storey,
        )
        assert door is not None

    def test_door_is_ifc_door(self, model_with_wall):
        m, storey, wall = model_with_wall
        opening = m.add_opening(
            PendingOpening(width=0.9, height=2.1, plane=_opening_plane(2.0)),
            wall,
            storey,
        )
        door = m.add_door(
            PendingDoor(
                overall_width=0.9,
                overall_height=2.1,
                component_graph="door_flush",
            ),
            opening,
            storey,
        )
        assert door.entity.is_a("IfcDoor")

    def test_door_shape_has_one_solid(self, model_with_wall):
        """door_flush produces a single Door component."""
        m, storey, wall = model_with_wall
        opening = m.add_opening(
            PendingOpening(width=0.9, height=2.1, plane=_opening_plane(2.0)),
            wall,
            storey,
        )
        door = m.add_door(
            PendingDoor(
                overall_width=0.9,
                overall_height=2.1,
                component_graph="door_flush",
            ),
            opening,
            storey,
        )
        reps = door.entity.Representation.Representations
        body_rep = next(r for r in reps if r.RepresentationIdentifier == "Body")
        assert len(body_rep.Items) == 1


# ---------------------------------------------------------------------------
# Fallback: no component_graph → existing lining logic untouched
# ---------------------------------------------------------------------------


class TestWindowWithoutGraph:
    def test_window_without_graph_still_builds(self, model_with_wall):
        """Ensure existing code path is not broken by the new graph_name parameter."""
        m, storey, wall = model_with_wall
        opening = m.add_opening(
            PendingOpening(width=1.0, height=1.2, plane=_opening_plane(3.0)),
            wall,
            storey,
        )
        window = m.add_window(
            PendingWindow(overall_width=1.0, overall_height=1.2),
            opening,
            storey,
        )
        assert window.entity.is_a("IfcWindow")
