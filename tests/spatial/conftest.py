# This file was generated with the assistance of an AI coding tool.
"""Shared fixtures for ifckit.spatial tests."""

import pytest

from ifckit import IfcModel
from ifckit.geometry import Vec
from ifckit.spatial import ProgramEdge, ProgramSpace, RoomProgram


def _space(pts, height, name, long_name=""):
    return pts, height, name, long_name


@pytest.fixture
def two_room_program() -> RoomProgram:
    """Keuken + woonkamer, buiten-knoop, facade (hard), deur (hard), wall-hint (zacht)."""
    return RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", long_name="Keuken", area_min=8, area_max=15),
            "w": ProgramSpace(name="1.02", long_name="Woonkamer", area_min=20),
            "buiten": ProgramSpace(name="buiten", exterior=True),
        },
        edges=[
            ProgramEdge("k", "buiten", kind="facade"),
            ProgramEdge("k", "w", kind="door"),
            ProgramEdge("k", "w", kind="wall", required=False),
        ],
    )


@pytest.fixture
def two_room_model() -> IfcModel:
    """Twee aangrenzende IfcSpace's (1.01 Keuken 12 m², 1.02 Woonkamer 24 m²)."""
    m = IfcModel(name="TwoRoom")
    site = m.add_site("S")
    building = m.add_building(site, "B")
    storey = m.add_storey(building, "00", elevation=0.0)
    storey.add_space(
        [Vec(0, 0, 0), Vec(3, 0, 0), Vec(3, 4, 0), Vec(0, 4, 0)],
        height=3.0,
        name="1.01",
        long_name="Keuken",
    )
    storey.add_space(
        [Vec(3, 0, 0), Vec(9, 0, 0), Vec(9, 4, 0), Vec(3, 4, 0)],
        height=3.0,
        name="1.02",
        long_name="Woonkamer",
    )
    return m
