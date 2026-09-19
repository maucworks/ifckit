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
