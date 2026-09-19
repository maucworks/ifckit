# This file was generated with the assistance of an AI coding tool.
"""Tests for the PvE program dataclasses."""

import pytest

from ifckit.spatial import ProgramEdge, ProgramSpace, RoomProgram


def test_program_edge_rejects_unknown_kind():
    with pytest.raises(ValueError):
        ProgramEdge("a", "b", kind="nonsense")


def test_program_edge_soft_wall_defaults_required_true():
    edge = ProgramEdge("a", "b", kind="wall")
    assert edge.required is True


def test_room_program_to_from_dict_roundtrip():
    program = RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", long_name="Keuken", area_min=8),
            "buiten": ProgramSpace(name="buiten", exterior=True),
        },
        edges=[ProgramEdge("k", "buiten", kind="facade")],
    )
    data = program.to_dict()
    restored = RoomProgram.from_dict(data)
    assert restored.nodes["k"].name == "1.01"
    assert restored.nodes["k"].area_min == 8
    assert restored.edges[0].kind == "facade"


def test_room_program_defaults_empty():
    program = RoomProgram()
    assert program.nodes == {}
    assert program.edges == []


def test_program_space_rejects_unknown_role():
    with pytest.raises(ValueError):
        ProgramSpace(name="X", role="nonsense")


def test_program_space_role_roundtrip():
    program = RoomProgram(nodes={"g": ProgramSpace(name="Gang", role="verkeer")}, edges=[])
    restored = RoomProgram.from_dict(program.to_dict())
    assert restored.nodes["g"].role == "verkeer"


def test_access_graph_only_door_edges():
    program = RoomProgram(
        nodes={
            "a": ProgramSpace(name="A"),
            "b": ProgramSpace(name="B"),
            "c": ProgramSpace(name="C"),
        },
        edges=[
            ProgramEdge("a", "b", kind="door"),
            ProgramEdge("b", "c", kind="wall", required=False),
        ],
    )
    g = program.access_graph()
    assert g.has_edge("a", "b")
    assert not g.has_edge("b", "c")
    assert g.edge_attrs("a", "b")["kind"] == "door"
