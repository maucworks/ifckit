"""
Tests for ifckit.geometry.patterns — pure index operations (no OCC needed).
"""

from __future__ import annotations

import pytest

from ifckit.geometry import Vec
from ifckit.geometry.field import Field, FieldPoint
from ifckit.geometry.patterns import (
    anglebox_cells,
    brick_cells,
    diamond_cells,
    hankin_cells,
    hex_cells,
    quad_cells,
    triangle_cells,
    truchet_cells,
    wave_cells,
)


def _wide_field() -> Field:
    f = Field(nu=4, nv=[2])
    for j in range(3):
        for i in range(5):
            f.lattice[(i, j)] = len(f.points)
            f.points.append(FieldPoint(pos=Vec(i, j, 0), uv=(i / 4, j / 2), normal=Vec(0, 0, 1)))
    for i in range(4):
        for j in range(2):
            a = f.lattice[(i, j)]
            f.cells.append(
                (a, f.lattice[(i + 1, j)], f.lattice[(i + 1, j + 1)], f.lattice[(i, j + 1)])
            )
    return f


def _big_field() -> Field:
    f = Field(nu=4, nv=[4])
    for j in range(5):
        for i in range(5):
            f.lattice[(i, j)] = len(f.points)
            f.points.append(FieldPoint(pos=Vec(i, j, 0), uv=(i / 4, j / 4), normal=Vec(0, 0, 1)))
    for i in range(4):
        for j in range(4):
            a = f.lattice[(i, j)]
            f.cells.append(
                (a, f.lattice[(i + 1, j)], f.lattice[(i + 1, j + 1)], f.lattice[(i, j + 1)])
            )
    return f


def _node_set(f: Field) -> set:
    return {(round(p.x, 9), round(p.y, 9), round(p.z, 9)) for p in (q.pos for q in f.points)}


def _flat_field() -> Field:
    f = Field(nu=2, nv=[2])
    for j in range(3):
        for i in range(3):
            f.lattice[(i, j)] = len(f.points)
            f.points.append(FieldPoint(pos=Vec(i, j, 0), uv=(i / 2, j / 2), normal=Vec(0, 0, 1)))
    for i in range(2):
        for j in range(2):
            a = f.lattice[(i, j)]
            f.cells.append(
                (a, f.lattice[(i + 1, j)], f.lattice[(i + 1, j + 1)], f.lattice[(i, j + 1)])
            )
    return f


class TestQuadCells:
    def test_count_and_corners(self):
        quads = quad_cells(_flat_field())
        assert len(quads) == 4
        assert all(len(q) == 4 for q in quads)


class TestDiamondCells:
    def test_node_diamond(self):
        # Interior node (1,1) → [a1, b2, c1, b0] = node-based, on-surface.
        res = diamond_cells(_flat_field())
        assert len(res.diamonds) == 1
        got = sorted((round(p.x, 9), round(p.y, 9)) for p in res.diamonds[0])
        assert got == [(0.0, 1.0), (1.0, 0.0), (1.0, 2.0), (2.0, 1.0)]
        assert all(p.z == 0.0 for p in res.diamonds[0])

    def test_edge_infill(self):
        # 2×2 field: all 4 quads are boundary, one open half each.
        res = diamond_cells(_flat_field())
        assert len(res.edge) == 4
        assert all(len(t) == 3 for t in res.edge)
        got = sorted(sorted((round(p.x, 9), round(p.y, 9)) for p in t) for t in res.edge)
        assert got == [
            [(0.0, 0.0), (0.0, 1.0), (1.0, 0.0)],
            [(0.0, 2.0), (1.0, 1.0), (1.0, 2.0)],
            [(1.0, 1.0), (1.0, 2.0), (2.0, 1.0)],
            [(1.0, 1.0), (2.0, 0.0), (2.0, 1.0)],
        ]

    def test_partition(self):
        # Diamonds + infill cover the 2×2 field exactly once (area 4).
        def _area(poly):
            total = 0.0
            for k in range(1, len(poly) - 1):
                total += ((poly[k] - poly[0]) ** (poly[k + 1] - poly[0])).length() / 2
            return total

        res = diamond_cells(_flat_field())
        cover = sum(_area(c) for c in res.diamonds + res.edge)
        assert cover == pytest.approx(4.0)


class TestTriangleCells:
    def test_short_diagonal(self):
        tris = triangle_cells(_flat_field(), diagonal="short")
        assert len(tris) == 8
        assert all(len(t) == 3 for t in tris)

    def test_fixed_diagonal(self):
        tris = triangle_cells(_flat_field(), diagonal="a_c")
        a, b, c = tris[0]
        assert (a - Vec(0, 0, 0)).length() < 1e-12
        assert (b - Vec(1, 0, 0)).length() < 1e-12
        assert (c - Vec(1, 1, 0)).length() < 1e-12


def _all_nodes(cells, nodes: set) -> bool:
    return all((round(p.x, 9), round(p.y, 9), round(p.z, 9)) in nodes for c in cells for p in c)


class TestWaveCells:
    def test_zigzag(self):
        tris = wave_cells(_flat_field())
        assert len(tris) == 8
        assert _all_nodes(tris, _node_set(_flat_field()))


class TestAngleboxCells:
    def test_mixed(self):
        cells = anglebox_cells(_flat_field())
        assert len(cells) == 6  # 2 whole quads + 2 split pairs
        assert sorted(len(c) for c in cells) == [3, 3, 3, 3, 4, 4]


class TestBrickCells:
    def test_running_bond(self):
        f = _wide_field()
        bricks = brick_cells(f)
        assert len(bricks) == 5  # rows j=0: 3, j=1 (offset): 2
        assert all(len(b) == 4 for b in bricks)
        assert _all_nodes(bricks, _node_set(f))


class TestTruchetCells:
    def test_count_and_determinism(self):
        f = _flat_field()
        assert len(truchet_cells(f, seed=0)) == 8
        assert truchet_cells(f, seed=0) != truchet_cells(f, seed=1)
        again = truchet_cells(f, seed=7)
        assert [(p.x, p.y) for t in again for p in t] == [
            (p.x, p.y) for t in truchet_cells(f, seed=7) for p in t
        ]


class TestHexCells:
    def test_partition(self):
        f = _big_field()
        res = hex_cells(f)
        assert len(res.hexes) == 1
        assert all(len(h) == 6 for h in res.hexes)
        assert _all_nodes(res.hexes + res.fill, _node_set(f))

        def _area(poly):
            total = 0.0
            for k in range(1, len(poly) - 1):
                total += ((poly[k] - poly[0]) ** (poly[k + 1] - poly[0])).length() / 2
            return total

        assert sum(_area(c) for c in res.hexes + res.fill) == pytest.approx(16.0)


class TestHankinCells:
    def test_star_partition(self):
        pytest.importorskip("OCC")
        from ifckit.geometry import Surface

        face = Surface(
            control_points=[[Vec(0, 0, 0), Vec(0, 2, 0)], [Vec(2, 0, 0), Vec(2, 2, 0)]],
            uknots=[0.0, 1.0],
            vknots=[0.0, 1.0],
            umults=[2, 2],
            vmults=[2, 2],
            udegree=1,
            vdegree=1,
        )
        f = Field(nu=1, nv=[1])
        for j in range(2):
            for i in range(2):
                f.lattice[(i, j)] = len(f.points)
                f.points.append(
                    FieldPoint(pos=Vec(2 * i, 2 * j, 0), uv=(i, j), normal=Vec(0, 0, 1))
                )
        f.cells.append((0, 1, 3, 2))
        cells = hankin_cells(f, [face], theta_deg=60.0)
        assert len(cells) == 9  # star + 4 corner quads + 4 edge triangles
        assert all(abs(p.z) < 1e-9 for c in cells for p in c)

        def _area(poly):
            total = 0.0
            for k in range(1, len(poly) - 1):
                total += ((poly[k] - poly[0]) ** (poly[k + 1] - poly[0])).length() / 2
            return total

        assert sum(_area(c) for c in cells) == pytest.approx(4.0)


class TestGoldenRule:
    def test_all_outputs_are_nodes(self):
        f = _flat_field()
        nodes = _node_set(f)
        dia = diamond_cells(f)
        pops = (
            quad_cells(f)
            + dia.diamonds
            + dia.edge
            + triangle_cells(f)
            + wave_cells(f)
            + anglebox_cells(f)
            + truchet_cells(f)
        )
        assert _all_nodes(pops, nodes)
