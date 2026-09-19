# This file was generated with the assistance of an AI coding tool.
"""Tests for space-syntax measures on small verifiable graphs."""

import pytest

from ifckit.spatial import (
    Graph,
    analyze,
    choice,
    connectivity,
    control,
    diamond_value,
    integration,
    mean_depth,
    relative_asymmetry,
    total_depth,
)


def _star() -> Graph:
    g = Graph()
    for leaf in ("a", "b", "d", "e"):
        g.add_edge("c", leaf)
    return g


def _path() -> Graph:
    g = Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    g.add_edge("c", "d")
    g.add_edge("d", "e")
    return g


def test_star_depth():
    g = _star()
    assert total_depth(g)["c"] == pytest.approx(4.0)
    assert total_depth(g)["a"] == pytest.approx(7.0)
    assert mean_depth(g)["c"] == pytest.approx(1.0)
    assert mean_depth(g)["a"] == pytest.approx(1.75)


def test_star_asymmetry():
    g = _star()
    ra = relative_asymmetry(g)
    assert ra["c"] == pytest.approx(0.0)
    assert ra["a"] == pytest.approx(0.5)


def test_star_integration_ordering():
    g = _star()
    iv = integration(g)
    assert iv["c"] > iv["a"]
    assert iv["a"] == pytest.approx(0.704, abs=0.01)


def test_path_middle_most_integrated():
    g = _path()
    md = mean_depth(g)
    assert md["c"] == pytest.approx(1.5)
    assert md["a"] == pytest.approx(2.5)
    iv = integration(g)
    assert iv["c"] > iv["b"] > iv["a"]
    assert iv["c"] == pytest.approx(1.056, abs=0.01)


def test_choice():
    star = _star()
    assert choice(star)["c"] == pytest.approx(6.0)
    assert choice(star)["a"] == pytest.approx(0.0)
    path = _path()
    assert choice(path)["c"] == pytest.approx(4.0)
    assert choice(path)["b"] == pytest.approx(3.0)
    assert choice(path)["a"] == pytest.approx(0.0)


def test_control():
    star = _star()
    assert control(star)["c"] == pytest.approx(4.0)
    assert control(star)["a"] == pytest.approx(0.25)
    assert control(_path())["b"] == pytest.approx(1.5)


def test_connectivity():
    assert connectivity(_star())["c"] == 4
    assert connectivity(_path())["a"] == 1


def test_disconnected_raises():
    g = Graph()
    g.add_edge("a", "b")
    g.add_node("c")
    with pytest.raises(ValueError):
        mean_depth(g)
    with pytest.raises(ValueError):
        integration(g)
    with pytest.raises(ValueError):
        choice(g)


def test_diamond_value():
    assert diamond_value(5) == pytest.approx(0.352)
    assert diamond_value(7) == pytest.approx(0.34)
    assert diamond_value(99) is None


def test_analyze_returns_all_measures():
    result = analyze(_star())
    assert set(result.depth) == {"a", "b", "c", "d", "e"}
    assert (
        set(result.integration)
        == set(result.connectivity)
        == set(result.control)
        == set(result.choice)
    )
