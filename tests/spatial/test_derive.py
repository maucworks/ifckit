# This file was generated with the assistance of an AI coding tool.
"""Tests for graph derivation from IFC models."""

import ifcopenshell
import pytest

from ifckit import IfcModel
from ifckit.geometry import Vec
from ifckit.spatial import perimeter_spaces, space_adjacency, space_footprints, wall_graph


def _grid_model(n: int) -> IfcModel:
    """Een n x n rooster van 3x3m ruimten, voor envelop-analyse."""
    m = IfcModel(name="Grid")
    site = m.add_site("S")
    building = m.add_building(site, "B")
    storey = m.add_storey(building, "00", elevation=0.0)
    for i in range(n):
        for j in range(n):
            x, y = i * 3, j * 3
            storey.add_space(
                [Vec(x, y, 0), Vec(x + 3, y, 0), Vec(x + 3, y + 3, 0), Vec(x, y + 3, 0)],
                height=3.0,
                name=f"r{i}{j}",
            )
    return m


def test_space_adjacency_two_rooms(two_room_model):
    graph = space_adjacency(two_room_model)
    assert len(graph) == 2
    # de enige grens is een gedeelde wand (geen space boundaries in het model)
    edges = graph.edges()
    assert len(edges) == 1
    assert next(iter(edges.values()))["kind"] == "wall"


def test_space_adjacency_node_attrs(two_room_model):
    graph = space_adjacency(two_room_model)
    names = {attrs["name"] for attrs in graph.nodes().values()}
    assert names == {"1.01", "1.02"}


def test_space_footprints_area_in_metres(two_room_model):
    footprints = space_footprints(two_room_model)
    assert len(footprints) == 2
    areas = sorted(poly.area for poly in footprints.values())
    assert areas == pytest.approx([12.0, 24.0])  # 3x4 en 6x4 m


def test_perimeter_two_rooms_both_facade(two_room_model):
    footprints = space_footprints(two_room_model)
    perimeter = perimeter_spaces(footprints)
    assert len(perimeter) == 2


def test_perimeter_center_interior():
    m = _grid_model(3)
    footprints = space_footprints(m)
    perimeter = perimeter_spaces(footprints)
    # 8 randruimten hebben een buitengevel, de centrale ruimte (r11) niet
    assert len(perimeter) == 8
    graph = space_adjacency(m)
    center = next(gid for gid, attrs in graph.nodes().items() if attrs["name"] == "r11")
    assert center not in perimeter


def test_wall_graph_connects_adjacent_walls():
    m = IfcModel(name="Walls")
    site = m.add_site("S")
    building = m.add_building(site, "B")
    storey = m.add_storey(building, "00", elevation=0.0)
    from ifckit import PendingWall
    from ifckit.geometry import Plane

    plane = Plane.world_xy()
    # twee dunne wanden die een hoek delen
    storey.add(
        PendingWall(
            [Vec(0, 0, 0), Vec(0.2, 0, 0), Vec(0.2, 4, 0), Vec(0, 4, 0)],
            plane=plane,
            height=3.0,
            name="W1",
        )
    )
    storey.add(
        PendingWall(
            [Vec(0, 4, 0), Vec(4, 4, 0), Vec(4, 4.2, 0), Vec(0, 4.2, 0)],
            plane=plane,
            height=3.0,
            name="W2",
        )
    )
    graph = wall_graph(m)
    assert len(graph) == 2
    assert len(graph.edges()) == 1


def test_door_pairs_virtual_boundary():
    from ifckit.spatial.derive import _door_pairs

    f = ifcopenshell.file(schema="IFC4")
    a = f.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name="A")
    b = f.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name="B")
    sb1 = f.create_entity(
        "IfcRelSpaceBoundary2ndLevel",
        GlobalId=ifcopenshell.guid.new(),
        RelatingSpace=a,
        PhysicalOrVirtualBoundary="VIRTUAL",
    )
    sb2 = f.create_entity(
        "IfcRelSpaceBoundary2ndLevel",
        GlobalId=ifcopenshell.guid.new(),
        RelatingSpace=b,
        PhysicalOrVirtualBoundary="VIRTUAL",
    )
    sb1.CorrespondingBoundary = sb2
    sb2.CorrespondingBoundary = sb1
    assert tuple(sorted([a.GlobalId, b.GlobalId])) in _door_pairs(f)
