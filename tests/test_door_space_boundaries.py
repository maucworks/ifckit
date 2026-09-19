# This file was generated with the assistance of an AI coding tool.
"""Tests for door space boundaries (M7b)."""

from ifckit import IfcModel
from ifckit.elements.building import PendingWall
from ifckit.elements.opening import PendingDoor, PendingOpening
from ifckit.geometry import Plane, Vec
from ifckit.spatial import ProgramEdge, ProgramSpace, RoomProgram, conform
from ifckit.spatial.derive import _door_pairs, space_adjacency


def _two_spaces(m):
    site = m.add_site("S")
    b = m.add_building(site, "B")
    st = m.add_storey(b, "00", elevation=0.0)
    st.add_space(
        [Vec(0, 0, 0), Vec(3, 0, 0), Vec(3, 4, 0), Vec(0, 4, 0)],
        height=3.0,
        name="1.01",
        long_name="Keuken",
    )
    st.add_space(
        [Vec(3, 0, 0), Vec(9, 0, 0), Vec(9, 4, 0), Vec(3, 4, 0)],
        height=3.0,
        name="1.02",
        long_name="Woonkamer",
    )
    return st


def _wall(st, x0=2.9, x1=3.1, name="W"):
    return st.add(
        PendingWall(
            [Vec(x0, 0, 0), Vec(x1, 0, 0), Vec(x1, 4, 0), Vec(x0, 4, 0)],
            plane=Plane.world_xy(),
            height=3.0,
            name=name,
        )
    )


def _door(m, st, wall_h, ox=2.9, oy=1.0):
    op = m.add_opening(
        PendingOpening(
            plane=Plane(Vec(ox, oy, 0.0), Vec(0, 1, 0), Vec(0, 0, 1)),
            width=0.9,
            height=2.1,
        ),
        host=wall_h,
        container=st,
    )
    return m.add_door(PendingDoor(overall_width=0.9, overall_height=2.1), opening=op, container=st)


def test_interior_door_creates_boundary_pair():
    m = IfcModel(name="T")
    st = _two_spaces(m)
    wall_h = _wall(st)
    door_h = _door(m, st, wall_h)

    sbs = m.ifc_file.by_type("IfcRelSpaceBoundary2ndLevel")
    assert len(sbs) == 2
    assert all(sb.PhysicalOrVirtualBoundary == "VIRTUAL" for sb in sbs)
    assert all(sb.InternalOrExternalBoundary == "INTERNAL" for sb in sbs)
    assert sbs[0].CorrespondingBoundary == sbs[1]
    assert sbs[1].CorrespondingBoundary == sbs[0]
    assert all(sb.RelatedBuildingElement == door_h.entity for sb in sbs)

    spaces = {s.Name: s.GlobalId for s in m.ifc_file.by_type("IfcSpace")}
    assert tuple(sorted([spaces["1.01"], spaces["1.02"]])) in _door_pairs(m.ifc_file)

    kinds = {attrs.get("kind") for attrs in space_adjacency(m).edges().values()}
    assert "door" in kinds


def test_conform_door_satisfied_on_built_model():
    m = IfcModel(name="T")
    st = _two_spaces(m)
    _door(m, st, _wall(st))
    program = RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=8),
            "w": ProgramSpace(name="1.02", area_min=20),
        },
        edges=[ProgramEdge("k", "w", kind="door")],
    )
    report = conform(m, program)
    assert "edge:k-w:door" in report.satisfied
    assert report.ok


def test_exterior_door_single_external_boundary():
    m = IfcModel(name="T")
    site = m.add_site("S")
    b = m.add_building(site, "B")
    st = m.add_storey(b, "00", elevation=0.0)
    st.add_space(
        [Vec(0, 0, 0), Vec(4, 0, 0), Vec(4, 3, 0), Vec(0, 3, 0)],
        height=3.0,
        name="1.01",
    )
    wall_h = st.add(
        PendingWall(
            [Vec(-0.1, 0, 0), Vec(0.1, 0, 0), Vec(0.1, 3, 0), Vec(-0.1, 3, 0)],
            plane=Plane.world_xy(),
            height=3.0,
            name="W",
        )
    )
    _door(m, st, wall_h, ox=-0.1, oy=1.0)

    sbs = m.ifc_file.by_type("IfcRelSpaceBoundary2ndLevel")
    assert len(sbs) == 1
    assert sbs[0].InternalOrExternalBoundary == "EXTERNAL"
    assert sbs[0].CorrespondingBoundary is None


def test_door_without_spaces_creates_nothing():
    m = IfcModel(name="T")
    site = m.add_site("S")
    b = m.add_building(site, "B")
    st = m.add_storey(b, "00", elevation=0.0)
    wall_h = _wall(st)
    _door(m, st, wall_h)
    assert m.ifc_file.by_type("IfcRelSpaceBoundary2ndLevel") == []
    assert len(m.ifc_file.by_type("IfcDoor")) == 1


def test_model_b_door_hook():
    m = IfcModel(name="T")
    site = m.add_site("S")
    b = m.add_building(site, "B")
    st = m.add_storey(b, "00", elevation=0.0)
    wall_h = _wall(st)
    door_h = m.add(
        PendingDoor(
            overall_width=0.9,
            overall_height=2.1,
            plane=Plane(Vec(2.9, 1.0, 0.0), Vec(0, 1, 0), Vec(0, 0, 1)),
            component_graph="door_flush",
        ),
        container=wall_h,
    )
    assert door_h.entity.is_a("IfcDoor")
    assert m.ifc_file.by_type("IfcRelSpaceBoundary2ndLevel") == []
