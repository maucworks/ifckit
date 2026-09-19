# This file was generated with the assistance of an AI coding tool.
"""Tests for ifckit.spatial.operators."""

import pytest

from ifckit.geometry import Vec
from ifckit.spatial import ProgramSpace, RoomProgram
from ifckit.spatial.operators import (
    add_room,
    layout_row,
    mirror_footprint,
    place_space,
    remove_room,
    split_footprint,
)


def _area(pts) -> float:
    s = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i].x, pts[i].y
        x1, y1 = pts[(i + 1) % n].x, pts[(i + 1) % n].y
        s += x0 * y1 - x1 * y0
    return s / 2.0


def _program() -> RoomProgram:
    return RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", area_min=8, area_max=15),
            "w": ProgramSpace(name="1.02", area_min=20),
        },
        edges=[],
    )


def test_place_space_exact_dims():
    pts = place_space(_program(), "k", 1.0, 2.0, w=3.0, d=4.0)
    assert [(p.x, p.y) for p in pts] == [(1.0, 2.0), (4.0, 2.0), (4.0, 6.0), (1.0, 6.0)]
    assert _area(pts) == pytest.approx(12.0)


def test_place_space_derives_missing_dim():
    assert _area(place_space(_program(), "k", 0, 0, w=4.0)) == pytest.approx(8.0)
    assert _area(place_space(_program(), "w", 0, 0, d=5.0)) == pytest.approx(20.0)
    assert _area(place_space(_program(), "k", 0, 0)) == pytest.approx(8.0)


def test_place_space_rejects_area_violation():
    with pytest.raises(ValueError):
        place_space(_program(), "k", 0, 0, w=1.0, d=1.0)  # 1 m² < 8
    with pytest.raises(ValueError):
        place_space(_program(), "k", 0, 0, w=10.0, d=10.0)  # 100 m² > 15


def test_place_space_rejects_bad_input():
    with pytest.raises(KeyError):
        place_space(_program(), "zzz", 0, 0)
    with pytest.raises(ValueError):
        place_space(_program(), "k", 0, 0, w=-1.0)
    prog = RoomProgram(nodes={"x": ProgramSpace(name="X")}, edges=[])
    with pytest.raises(ValueError):
        place_space(prog, "x", 0, 0)


def test_split_footprint_x():
    a, b = split_footprint([Vec(0, 0, 0), Vec(6, 0, 0), Vec(6, 4, 0), Vec(0, 4, 0)], "x", 2.0)
    assert _area(a) == pytest.approx(8.0)
    assert _area(b) == pytest.approx(16.0)


def test_split_footprint_y():
    a, b = split_footprint([Vec(0, 0, 0), Vec(6, 0, 0), Vec(6, 4, 0), Vec(0, 4, 0)], "y", 1.0)
    assert _area(a) == pytest.approx(6.0)
    assert _area(b) == pytest.approx(18.0)


def test_split_footprint_rejects():
    rect = [Vec(0, 0, 0), Vec(6, 0, 0), Vec(6, 4, 0), Vec(0, 4, 0)]
    with pytest.raises(ValueError):
        split_footprint(rect, "x", 99.0)
    with pytest.raises(ValueError):
        split_footprint(rect, "z", 1.0)
    with pytest.raises(ValueError):
        split_footprint([Vec(0, 0, 0), Vec(1, 1, 0), Vec(2, 0, 0)], "x", 1.0)


def test_mirror_footprint():
    rect = [Vec(0, 0, 0), Vec(6, 0, 0), Vec(6, 4, 0), Vec(0, 4, 0)]
    m = mirror_footprint(rect, "x", 10.0)
    assert [(p.x, p.y) for p in m] == [(20.0, 4.0), (14.0, 4.0), (14.0, 0.0), (20.0, 0.0)]
    assert _area(m) == pytest.approx(_area(rect))  # winding behouden
    m2 = mirror_footprint(rect, "y", 5.0)
    assert [(p.x, p.y) for p in m2] == [(0.0, 6.0), (6.0, 6.0), (6.0, 10.0), (0.0, 10.0)]
    with pytest.raises(ValueError):
        mirror_footprint(rect, "z", 0.0)


def test_add_remove_room():
    prog = _program()
    add_room(prog, "b", ProgramSpace(name="1.03", area_min=5))
    assert "b" in prog.nodes
    with pytest.raises(KeyError):
        add_room(prog, "b", ProgramSpace(name="dup"))
    from ifckit.spatial import ProgramEdge

    prog.edges.append(ProgramEdge("k", "b", kind="wall", required=False))
    remove_room(prog, "b")
    assert "b" not in prog.nodes
    assert all(e.a != "b" and e.b != "b" for e in prog.edges)
    with pytest.raises(KeyError):
        remove_room(prog, "b")


def test_layout_row():
    prog = _program()
    out = layout_row(prog, ["k", "w"], x0=1.0, y0=2.0, depth=4.0, gap=0.5)
    assert _area(out["k"]) == pytest.approx(8.0)
    assert _area(out["w"]) == pytest.approx(20.0)
    # aaneengesloten met gap: k[1,3], w[3.5,8.5]
    assert out["k"][0].x == pytest.approx(1.0)
    assert out["w"][0].x == pytest.approx(3.5)
    assert out["k"][0].y == out["w"][0].y == pytest.approx(2.0)
    with pytest.raises(KeyError):
        layout_row(prog, ["zzz"], 0, 0, 4.0)
    with pytest.raises(ValueError):
        layout_row(prog, ["k"], 0, 0, 0.0)
