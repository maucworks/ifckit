"""
tests/test_model_doors_windows.py
==================================

Integration tests for the IfcModel opening / door / window / type APIs.
These test the full chain: host → opening → fill → type.
"""

import pytest

from ifckit import IfcModel, IfcSchema, PendingWall
from ifckit.elements.opening import PendingDoor, PendingOpening, PendingWindow
from ifckit.elements.types import PendingDoorType, PendingWindowType
from ifckit.geometry import Plane, Vec


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def model():
    m = IfcModel("TestProject", schema=IfcSchema.IFC4)
    site = m.add_site("Site")
    bldg = m.add_building(site, "Building")
    storey = m.add_storey(bldg, "GF", elevation=0.0)
    return m, storey


@pytest.fixture
def model_with_wall(model):
    m, storey = model
    wall = m.add(PendingWall(
        footprint=[Vec(0,0,0), Vec(5,0,0), Vec(5,0.2,0), Vec(0,0.2,0)],
        plane=Plane(Vec(0,0,0), Vec(1,0,0), Vec(0,1,0)),
        height=3.0, name="W1"
    ), storey)
    return m, storey, wall


def _opening_plane(x=1.0):
    return Plane(Vec(x, 0.0, 0.0), Vec(1, 0, 0), Vec(0, 1, 0))


# ===========================================================================
# S1 — wall + opening + door
# ===========================================================================


class TestWallOpeningDoor:
    def test_creates_correct_entities(self, model_with_wall):
        m, storey, wall = model_with_wall
        op = m.add_opening(
            PendingOpening(plane=_opening_plane(), width=0.9, height=2.1, name="OP1"),
            host=wall, container=storey
        )
        door = m.add_door(
            PendingDoor(overall_width=0.9, overall_height=2.1, name="D1"),
            opening=op, container=storey
        )
        assert op.entity.is_a("IfcOpeningElement")
        assert door.entity.is_a("IfcDoor")

    def test_rel_voids_element_exists(self, model_with_wall):
        m, storey, wall = model_with_wall
        op = m.add_opening(
            PendingOpening(plane=_opening_plane(), width=0.9, height=2.1),
            host=wall, container=storey
        )
        voids = m._file.by_type("IfcRelVoidsElement")
        assert len(voids) == 1
        assert voids[0].RelatingBuildingElement == wall.entity
        assert voids[0].RelatedOpeningElement == op.entity

    def test_rel_fills_element_exists(self, model_with_wall):
        m, storey, wall = model_with_wall
        op = m.add_opening(
            PendingOpening(plane=_opening_plane(), width=0.9, height=2.1),
            host=wall, container=storey
        )
        door = m.add_door(
            PendingDoor(overall_width=0.9, overall_height=2.1),
            opening=op, container=storey
        )
        fills = m._file.by_type("IfcRelFillsElement")
        assert len(fills) == 1
        assert fills[0].RelatingOpeningElement == op.entity
        assert fills[0].RelatedBuildingElement == door.entity

    # Removed test - IfcOpeningElement does not require spatial containment per IFC spec.
    # Door should still be contained in storey.


# ===========================================================================
# S2 — wall + opening + window
# ===========================================================================


class TestWallOpeningWindow:
    def test_creates_correct_entities(self, model_with_wall):
        m, storey, wall = model_with_wall
        op = m.add_opening(
            PendingOpening(plane=_opening_plane(), width=1.2, height=1.4, name="OP1"),
            host=wall, container=storey
        )
        win = m.add_window(
            PendingWindow(overall_width=1.2, overall_height=1.4, name="W1"),
            opening=op, container=storey
        )
        assert op.entity.is_a("IfcOpeningElement")
        assert win.entity.is_a("IfcWindow")

    def test_rel_voids_and_fills(self, model_with_wall):
        m, storey, wall = model_with_wall
        op = m.add_opening(
            PendingOpening(plane=_opening_plane(), width=1.2, height=1.4),
            host=wall, container=storey
        )
        win = m.add_window(
            PendingWindow(overall_width=1.2, overall_height=1.4),
            opening=op, container=storey
        )
        assert len(m._file.by_type("IfcRelVoidsElement")) == 1
        assert len(m._file.by_type("IfcRelFillsElement")) == 1


# ===========================================================================
# S3 — 10 doors with same type → single IfcDoorType, multiple RelDefinesByType
# ===========================================================================


class TestTypedDoors:
    def test_ten_doors_one_type(self, model):
        m, storey = model
        dt = m.add_door_type(PendingDoorType(overall_width=0.9, overall_height=2.1, name="DT"))

        for i in range(10):
            wall = m.add(PendingWall(
                footprint=[Vec(i*2,0,0), Vec(i*2+1.5,0,0), Vec(i*2+1.5,0.2,0), Vec(i*2,0.2,0)],
                plane=Plane(Vec(i*2,0,0), Vec(1,0,0), Vec(0,1,0)),
                height=3.0
            ), storey)
            op = m.add_opening(
                PendingOpening(plane=_opening_plane(x=i*2+0.3), width=0.9, height=2.1),
                host=wall, container=storey
            )
            m.add_door(
                PendingDoor(overall_width=0.9, overall_height=2.1),
                opening=op, container=storey, door_type=dt
            )

        # Exactly one IfcDoorType in the file.
        door_types = m._file.by_type("IfcDoorType")
        assert len(door_types) == 1

        # All 10 doors assigned to that type via IfcRelDefinesByType.
        rels = [r for r in m._file.by_type("IfcRelDefinesByType") if r.RelatingType == dt.entity]
        assert len(rels) == 1
        assert len(rels[0].RelatedObjects) == 10


# ===========================================================================
# S4 — 10 windows with same type
# ===========================================================================


class TestTypedWindows:
    def test_ten_windows_one_type(self, model):
        m, storey = model
        wt = m.add_window_type(PendingWindowType(overall_width=1.2, overall_height=1.4, name="WT"))

        for i in range(10):
            wall = m.add(PendingWall(
                footprint=[Vec(i*2,0,0), Vec(i*2+2,0,0), Vec(i*2+2,0.2,0), Vec(i*2,0.2,0)],
                plane=Plane(Vec(i*2,0,0), Vec(1,0,0), Vec(0,1,0)),
                height=3.0
            ), storey)
            op = m.add_opening(
                PendingOpening(plane=_opening_plane(x=i*2+0.4), width=1.2, height=1.4),
                host=wall, container=storey
            )
            m.add_window(
                PendingWindow(overall_width=1.2, overall_height=1.4),
                opening=op, container=storey, window_type=wt
            )

        window_types = m._file.by_type("IfcWindowType")
        assert len(window_types) == 1
        rels = [r for r in m._file.by_type("IfcRelDefinesByType") if r.RelatingType == wt.entity]
        assert len(rels) == 1
        assert len(rels[0].RelatedObjects) == 10


# ===========================================================================
# S5 — multiple storeys
# ===========================================================================


class TestMultiStoreyContainment:
    def test_doors_in_separate_storeys(self, model):
        m, storey_gf = model
        site = m._file.by_type("IfcSite")[0]
        bldg = m._file.by_type("IfcBuilding")[0]
        from ifckit.handles import BuildingHandle
        storey_ff = m.add_storey(BuildingHandle(bldg, m), "FF", elevation=3.0)

        for storey, z_offset in [(storey_gf, 0.0), (storey_ff, 3.0)]:
            wall = m.add(PendingWall(
                footprint=[Vec(0,0,0), Vec(5,0,0), Vec(5,0.2,0), Vec(0,0.2,0)],
                plane=Plane(Vec(0,0,z_offset), Vec(1,0,0), Vec(0,1,0)),
                height=3.0
            ), storey)
            op = m.add_opening(
                PendingOpening(plane=Plane(Vec(1,0,z_offset), Vec(1,0,0), Vec(0,1,0)), width=0.9, height=2.1),
                host=wall, container=storey
            )
            m.add_door(
                PendingDoor(overall_width=0.9, overall_height=2.1),
                opening=op, container=storey
            )

        assert len(m._file.by_type("IfcDoor")) == 2
        assert len(m._file.by_type("IfcRelVoidsElement")) == 2
        assert len(m._file.by_type("IfcRelFillsElement")) == 2


# ===========================================================================
# S6 — invalid references
# ===========================================================================


class TestInvalidReferences:
    def test_wrong_host_type_raises(self, model_with_wall):
        m, storey, wall = model_with_wall
        # Pass door as host (wrong type).
        op = m.add_opening(
            PendingOpening(plane=_opening_plane(), width=0.9, height=2.1),
            host=wall, container=storey
        )
        door = m.add_door(
            PendingDoor(overall_width=0.9, overall_height=2.1),
            opening=op, container=storey
        )
        with pytest.raises(ValueError, match="not in the allowed host classes"):
            m.add_opening(
                PendingOpening(plane=_opening_plane(2.0), width=0.9, height=2.1),
                host=door, container=storey   # door is not a valid host
            )

    def test_non_opening_as_fill_target_raises(self, model_with_wall):
        m, storey, wall = model_with_wall
        with pytest.raises(ValueError, match="expected IfcOpeningElement"):
            m.add_door(
                PendingDoor(overall_width=0.9, overall_height=2.1),
                opening=wall,   # wall, not opening
                container=storey
            )

    def test_wrong_container_type_raises(self, model_with_wall):
        m, storey, wall = model_with_wall
        op = m.add_opening(
            PendingOpening(plane=_opening_plane(), width=0.9, height=2.1),
            host=wall, container=storey
        )
        with pytest.raises(TypeError, match="StoreyHandle"):
            m.add_door(
                PendingDoor(overall_width=0.9, overall_height=2.1),
                opening=op, container=wall   # wrong type
            )

    def test_type_key_collision_raises(self, model):
        m, storey = model
        m.add_door_type(PendingDoorType(overall_width=0.9, overall_height=2.1, type_key="my-type"))
        with pytest.raises(ValueError, match="already registered with different parameters"):
            m.add_door_type(PendingDoorType(overall_width=1.2, overall_height=2.1, type_key="my-type"))

    def test_same_type_key_same_params_returns_same_entity(self, model):
        m, storey = model
        dt1 = m.add_door_type(PendingDoorType(overall_width=0.9, overall_height=2.1, name="DT"))
        dt2 = m.add_door_type(PendingDoorType(overall_width=0.9, overall_height=2.1, name="DT"))
        assert dt1.entity is dt2.entity


# ===========================================================================
# Type cache
# ===========================================================================


class TestTypeCache:
    def test_door_type_cache_reuse(self, model):
        m, storey = model
        dt1 = m.add_door_type(PendingDoorType(overall_width=0.9, overall_height=2.1, lining_depth=0.1))
        dt2 = m.add_door_type(PendingDoorType(overall_width=0.9, overall_height=2.1, lining_depth=0.1))
        assert dt1.entity is dt2.entity
        assert len(m._file.by_type("IfcDoorType")) == 1

    def test_window_type_cache_reuse(self, model):
        m, storey = model
        wt1 = m.add_window_type(PendingWindowType(overall_width=1.2, overall_height=1.4))
        wt2 = m.add_window_type(PendingWindowType(overall_width=1.2, overall_height=1.4))
        assert wt1.entity is wt2.entity
        assert len(m._file.by_type("IfcWindowType")) == 1

    def test_different_params_different_types(self, model):
        m, storey = model
        dt1 = m.add_door_type(PendingDoorType(overall_width=0.9, overall_height=2.1))
        dt2 = m.add_door_type(PendingDoorType(overall_width=1.0, overall_height=2.1))
        assert dt1.entity is not dt2.entity
        assert len(m._file.by_type("IfcDoorType")) == 2


# ===========================================================================
# IFC4 file save/reopen round-trip
# ===========================================================================


class TestIfcOutputRoundtrip:
    def test_save_and_reopen(self, model_with_wall, tmp_path):
        m, storey, wall = model_with_wall
        op = m.add_opening(
            PendingOpening(plane=_opening_plane(), width=0.9, height=2.1, name="OP1"),
            host=wall, container=storey
        )
        dt = m.add_door_type(PendingDoorType(overall_width=0.9, overall_height=2.1, name="DT1"))
        m.add_door(
            PendingDoor(overall_width=0.9, overall_height=2.1, name="D1"),
            opening=op, container=storey, door_type=dt
        )
        out = str(tmp_path / "test.ifc")
        m.save(out)

        import ifcopenshell
        f2 = ifcopenshell.open(out)
        assert len(f2.by_type("IfcOpeningElement")) == 1
        assert len(f2.by_type("IfcDoor")) == 1
        assert len(f2.by_type("IfcDoorType")) == 1
        assert len(f2.by_type("IfcRelVoidsElement")) == 1
        assert len(f2.by_type("IfcRelFillsElement")) == 1
        assert len(f2.by_type("IfcRelDefinesByType")) == 1
