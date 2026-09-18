# This file was generated with the assistance of an AI coding tool.
"""Tests for conformance: comparing a model against a PvE graph."""

from ifckit.spatial import ProgramEdge, ProgramSpace, RoomProgram, check_program, conform


def test_conform_two_room_reports_door_violation(two_room_program, two_room_model):
    report = conform(two_room_model, two_room_program)
    # ruimten aanwezig, oppervlak binnen range, facade voldaan, wall-hint voldaan,
    # maar de deur ontbreekt in het model.
    assert "space:k" in report.satisfied
    assert "space:w" in report.satisfied
    assert "edge:k-buiten:facade" in report.satisfied
    assert "edge:k-w:wall" in report.satisfied
    assert "edge:k-w:door" in report.violated
    assert report.ok is False


def test_conform_satisfied_without_door(two_room_model):
    program = RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=8),
            "w": ProgramSpace(name="1.02", area_min=20),
            "buiten": ProgramSpace(name="buiten"),
        },
        edges=[
            ProgramEdge("k", "buiten", kind="facade"),
            ProgramEdge("k", "w", kind="wall", required=False),
        ],
    )
    report = conform(two_room_model, program)
    assert report.ok is True
    assert report.violated == []


def test_conform_area_out_of_range(two_room_model):
    program = RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=30),  # werkelijk 24 m²
        },
        edges=[],
    )
    report = conform(two_room_model, program)
    assert any(v.startswith("space:k:area<") for v in report.violated)
    assert report.ok is False


def test_conform_missing_space(two_room_model):
    program = RoomProgram(
        nodes={"x": ProgramSpace(name="9.99", required=True)},
        edges=[],
    )
    report = conform(two_room_model, program)
    assert "space:x" in report.missing


def test_conform_forbidden_adjacency_violated(two_room_model):
    program = RoomProgram(
        nodes={"k": ProgramSpace(name="1.01"), "w": ProgramSpace(name="1.02")},
        edges=[ProgramEdge("k", "w", kind="forbidden")],
    )
    report = conform(two_room_model, program)
    assert "edge:k-w:forbidden" in report.violated


def test_check_program_issues():
    program = RoomProgram(
        nodes={"a": ProgramSpace(name="A"), "b": ProgramSpace(name="B")},
        edges=[ProgramEdge("a", "zzz", kind="door")],
    )
    issues = check_program(program)
    assert any("onbekende knoop" in i for i in issues)
    assert any("geïsoleerde knoop" in i for i in issues)


def test_check_program_clean():
    program = RoomProgram(
        nodes={"a": ProgramSpace(name="A"), "b": ProgramSpace(name="B")},
        edges=[ProgramEdge("a", "b", kind="door")],
    )
    assert check_program(program) == []
