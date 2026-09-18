# This file was generated with the assistance of an AI coding tool.
"""Tests for ifckit.spatial.graph.Graph."""

import pytest

from ifckit.spatial import Graph


def test_add_node_and_edge():
    g = Graph()
    g.add_node("a", name="Keuken")
    g.add_edge("a", "b", kind="wall")
    assert "a" in g
    assert "b" in g
    assert g.has_edge("a", "b")
    assert g.has_edge("b", "a")
    assert g.degree("a") == 1
    assert g.neighbors("a")["b"]["kind"] == "wall"


def test_edges_keyed_sorted():
    g = Graph()
    g.add_edge("b", "a", kind="door")
    assert ("a", "b") in g.edges()
    assert g.edges()[("a", "b")]["kind"] == "door"


def test_edge_attrs_merges():
    g = Graph()
    g.add_edge("a", "b", kind="wall")
    g.add_edge("a", "b", required=False)
    attrs = g.edge_attrs("a", "b")
    assert attrs == {"kind": "wall", "required": False}


def test_edge_attrs_missing_returns_none():
    g = Graph()
    assert g.edge_attrs("a", "b") is None


def test_shortest_path():
    g = Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "c")
    assert g.shortest_path("a", "c") == ["a", "b", "c"]
    assert g.shortest_path("a", "x") is None


def test_connected_components_and_isolated():
    g = Graph()
    g.add_edge("a", "b")
    g.add_node("c")
    comps = g.connected_components()
    assert {frozenset(c) for c in comps} == {frozenset({"a", "b"}), frozenset({"c"})}
    assert not g.is_connected()


def test_to_networkx():
    pytest.importorskip("networkx")
    g = Graph()
    g.add_edge("a", "b", kind="wall")
    ng = g.to_networkx()
    assert ng.has_edge("a", "b")
    assert ng.edges["a", "b"]["kind"] == "wall"
