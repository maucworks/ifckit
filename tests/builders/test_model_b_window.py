"""
tests/builders/test_model_b_window.py
======================================

Integration tests for Model B: m.add(PendingWindow(plane=..., component_graph=...), wall)

Model B generates the IfcOpeningElement automatically from the JSON preset's
opening_component section. No explicit add_opening() call needed.
"""

from __future__ import annotations

import pytest

from ifckit import IfcModel, IfcSchema, PendingWall
from ifckit.elements.opening import PendingDoor, PendingWindow
from ifckit.geometry import Plane, Vec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def model_with_wall():
    """IFC4 model with a single wall (5 m × 0.25 m × 3 m)."""
    m = IfcModel("TestProject", schema=IfcSchema.IFC4)
    site = m.add_site("Site")
    bldg = m.add_building(site, "Building")
    storey = m.add_storey(bldg, "GF", elevation=0.0)
    wall = m.add(
        PendingWall(
            footprint=[Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 0.25, 0), Vec(0, 0.25, 0)],
            plane=Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
            height=3.0,
            name="TestWall",
        ),
        storey,
    )
    return m, storey, wall


def _window_plane(x=1.0):
    """Insert plane centred at (x, 0, 0) — bottom-centre of window opening."""
    return Plane(Vec(x, 0.0, 0.0), Vec(1, 0, 0), Vec(0, 1, 0))


# ---------------------------------------------------------------------------
# Model B — window
# ---------------------------------------------------------------------------


class TestModelBWindow:
    def test_window_builds_without_error(self, model_with_wall):
        m, storey, wall = model_with_wall
        result = m.add(
            PendingWindow(
                overall_width=1.0,
                overall_height=1.2,
                plane=_window_plane(1.0),
                component_graph="fixed_casement",
                name="W-ModelB",
            ),
            wall,
        )
        assert result is not None

    def test_returns_entity_handle(self, model_with_wall):
        from ifckit.handles import EntityHandle

        m, storey, wall = model_with_wall
        result = m.add(
            PendingWindow(
                overall_width=1.0,
                overall_height=1.2,
                plane=_window_plane(1.0),
                component_graph="fixed_casement",
            ),
            wall,
        )
        assert isinstance(result, EntityHandle)

    def test_result_is_ifc_window(self, model_with_wall):
        m, storey, wall = model_with_wall
        result = m.add(
            PendingWindow(
                overall_width=1.0,
                overall_height=1.2,
                plane=_window_plane(1.0),
                component_graph="fixed_casement",
            ),
            wall,
        )
        assert result.entity.is_a("IfcWindow")

    def test_opening_element_is_created(self, model_with_wall):
        m, storey, wall = model_with_wall
        before = len(m._file.by_type("IfcOpeningElement"))
        m.add(
            PendingWindow(
                overall_width=1.0,
                overall_height=1.2,
                plane=_window_plane(1.0),
                component_graph="fixed_casement",
            ),
            wall,
        )
        after = len(m._file.by_type("IfcOpeningElement"))
        assert after == before + 1

    def test_opening_voids_wall(self, model_with_wall):
        m, storey, wall = model_with_wall
        m.add(
            PendingWindow(
                overall_width=1.0,
                overall_height=1.2,
                plane=_window_plane(1.0),
                component_graph="fixed_casement",
            ),
            wall,
        )
        voids = m._file.by_type("IfcRelVoidsElement")
        assert any(v.RelatingBuildingElement == wall.entity for v in voids)

    def test_window_fills_opening(self, model_with_wall):
        m, storey, wall = model_with_wall
        window = m.add(
            PendingWindow(
                overall_width=1.0,
                overall_height=1.2,
                plane=_window_plane(1.0),
                component_graph="fixed_casement",
            ),
            wall,
        )
        fills = m._file.by_type("IfcRelFillsElement")
        assert any(f.RelatedBuildingElement == window.entity for f in fills)

    def test_window_shape_has_two_solids(self, model_with_wall):
        """fixed_casement → Lining + Glazing = 2 solids."""
        m, storey, wall = model_with_wall
        window = m.add(
            PendingWindow(
                overall_width=1.0,
                overall_height=1.2,
                plane=_window_plane(1.0),
                component_graph="fixed_casement",
            ),
            wall,
        )
        reps = window.entity.Representation.Representations
        body_rep = next(r for r in reps if r.RepresentationIdentifier == "Body")
        assert len(body_rep.Items) == 2

    def test_lining_profile_has_voids(self, model_with_wall):
        m, storey, wall = model_with_wall
        window = m.add(
            PendingWindow(
                overall_width=1.0,
                overall_height=1.2,
                plane=_window_plane(1.0),
                component_graph="fixed_casement",
            ),
            wall,
        )
        reps = window.entity.Representation.Representations
        body_rep = next(r for r in reps if r.RepresentationIdentifier == "Body")
        profiles = []
        for item in body_rep.Items:
            # Unwrap IfcStyledItem to access the actual solid
            solid = item.Item if item.is_a("IfcStyledItem") else item
            profiles.append(solid.SweptArea.is_a())
        assert "IfcArbitraryProfileDefWithVoids" in profiles

    def test_missing_plane_raises(self, model_with_wall):
        m, storey, wall = model_with_wall
        with pytest.raises(ValueError, match="plane must be set"):
            m.add(
                PendingWindow(
                    overall_width=1.0,
                    overall_height=1.2,
                    component_graph="fixed_casement",
                    # plane=None  (default)
                ),
                wall,
            )

    def test_two_windows_same_wall(self, model_with_wall):
        """Two windows can be added to the same wall."""
        m, storey, wall = model_with_wall
        w1 = m.add(
            PendingWindow(
                overall_width=0.8,
                overall_height=1.2,
                plane=_window_plane(0.5),
                component_graph="fixed_casement",
            ),
            wall,
        )
        w2 = m.add(
            PendingWindow(
                overall_width=0.8,
                overall_height=1.2,
                plane=_window_plane(3.0),
                component_graph="fixed_casement",
            ),
            wall,
        )
        assert w1.entity != w2.entity
        assert len(m._file.by_type("IfcOpeningElement")) == 2


# ---------------------------------------------------------------------------
# Model B — door
# ---------------------------------------------------------------------------


class TestModelBDoor:
    def test_door_builds_without_error(self, model_with_wall):
        m, storey, wall = model_with_wall
        result = m.add(
            PendingDoor(
                overall_width=0.9,
                overall_height=2.1,
                plane=_window_plane(2.0),
                component_graph="door_flush",
                name="D-ModelB",
            ),
            wall,
        )
        assert result is not None

    def test_result_is_ifc_door(self, model_with_wall):
        m, storey, wall = model_with_wall
        result = m.add(
            PendingDoor(
                overall_width=0.9,
                overall_height=2.1,
                plane=_window_plane(2.0),
                component_graph="door_flush",
            ),
            wall,
        )
        assert result.entity.is_a("IfcDoor")

    def test_opening_element_is_created(self, model_with_wall):
        m, storey, wall = model_with_wall
        before = len(m._file.by_type("IfcOpeningElement"))
        m.add(
            PendingDoor(
                overall_width=0.9,
                overall_height=2.1,
                plane=_window_plane(2.0),
                component_graph="door_flush",
            ),
            wall,
        )
        after = len(m._file.by_type("IfcOpeningElement"))
        assert after == before + 1

    def test_door_shape_has_two_solids(self, model_with_wall):
        """door_flush produces lining + panel solids."""
        m, storey, wall = model_with_wall
        door = m.add(
            PendingDoor(
                overall_width=0.9,
                overall_height=2.1,
                plane=_window_plane(2.0),
                component_graph="door_flush",
            ),
            wall,
        )
        reps = door.entity.Representation.Representations
        body_rep = next(r for r in reps if r.RepresentationIdentifier == "Body")
        assert len(body_rep.Items) == 4

    def test_door_fills_opening(self, model_with_wall):
        m, storey, wall = model_with_wall
        door = m.add(
            PendingDoor(
                overall_width=0.9,
                overall_height=2.1,
                plane=_window_plane(2.0),
                component_graph="door_flush",
            ),
            wall,
        )
        fills = m._file.by_type("IfcRelFillsElement")
        assert any(f.RelatedBuildingElement == door.entity for f in fills)

    def test_missing_plane_raises(self, model_with_wall):
        m, storey, wall = model_with_wall
        with pytest.raises(ValueError, match="plane must be set"):
            m.add(
                PendingDoor(
                    overall_width=0.9,
                    overall_height=2.1,
                    component_graph="door_flush",
                    # plane=None  (default)
                ),
                wall,
            )
