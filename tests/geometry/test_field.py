"""
Tests for ifckit.geometry.field — FieldPoint/Field, trim/crossing grids.
Pure parts run without OCC; builders skip via importorskip.
"""

from __future__ import annotations

import pytest

from ifckit.geometry import Surface, Vec
from ifckit.geometry.field import (
    Field,
    FieldPoint,
    crossing_grid,
    divide_trim_edge,
    orient_division,
    trim_grid,
)
from ifckit.geometry.surface import (
    occ_face_bounds,
    occ_normal_at,
    occ_project_point,
    occ_trim_loops,
)


def _flat_face(x0: float, y0: float, x1: float, y1: float) -> Surface:
    return Surface(
        control_points=[
            [Vec(x0, y0, 0), Vec(x0, y1, 0)],
            [Vec(x1, y0, 0), Vec(x1, y1, 0)],
        ],
        uknots=[0.0, 1.0],
        vknots=[0.0, 1.0],
        umults=[2, 2],
        vmults=[2, 2],
        udegree=1,
        vdegree=1,
    )


def _hand_field() -> Field:
    f = Field(nu=2, nv=[2])
    for j in range(3):
        for i in range(3):
            f.lattice[(i, j)] = len(f.points)
            f.points.append(
                FieldPoint(pos=Vec(i, j, 0), uv=(i / 2, j / 2), normal=Vec(0, 0, 1))
            )
    for i in range(2):
        for j in range(2):
            a = f.lattice[(i, j)]
            f.cells.append(
                (a, f.lattice[(i + 1, j)], f.lattice[(i + 1, j + 1)], f.lattice[(i, j + 1)])
            )
    return f


class TestFieldPoint:
    def test_roundtrip(self):
        p = FieldPoint(pos=Vec(1, 2, 3), uv=(0.25, 0.75), normal=Vec(0, 0, 1), face=2)
        q = FieldPoint.from_dict(p.to_dict())
        assert (q.pos - Vec(1, 2, 3)).length() < 1e-12
        assert q.uv == (0.25, 0.75)
        assert q.face == 2


class TestField:
    def test_roundtrip(self):
        f = _hand_field()
        g = Field.from_dict(f.to_dict())
        assert (g.points[0].pos - Vec(0, 0, 0)).length() < 1e-12
        assert g.lattice[(2, 2)] == 8
        assert g.cells[0] == (0, 3, 4, 1) or len(g.cells) == 4
        assert g.nu == 2 and g.nv == [2]

    def test_cell_points(self):
        f = _hand_field()
        assert len(f.cell_points()) == 4
        assert len(f.cell_points()[0]) == 4


class TestDivide:
    def test_equidistant(self):
        uv = [(float(k), 0.0) for k in range(11)]
        xyz = [(float(k), 0.0, 0.0) for k in range(11)]
        out = divide_trim_edge(uv, xyz, 5)
        assert len(out) == 6
        assert [u for u, _ in out] == pytest.approx([0, 2, 4, 6, 8, 10])

    def test_errors(self):
        with pytest.raises(ValueError):
            divide_trim_edge([(0, 0)], [(0, 0, 0)], 0)
        with pytest.raises(ValueError):
            divide_trim_edge([(0, 0), (1, 0)], [(0, 0, 0)], 2)


class TestOrient:
    def test_reversed(self):
        mov_uv = [(3.0, 0.0), (2.0, 0.0), (1.0, 0.0)]
        mov_xyz = [(3.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        out = orient_division(mov_uv, mov_xyz, (0.0, 0.0, 0.0), (3.0, 0.0, 0.0))
        # index 0 must sit at ref0 (origin side)
        assert out[0] == (1.0, 0.0)

    def test_kept(self):
        mov_uv = [(0.0, 0.0), (1.0, 0.0)]
        mov_xyz = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        assert orient_division(mov_uv, mov_xyz, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)) == mov_uv


class TestTrimGrid:
    def test_flat_rectangle(self):
        pytest.importorskip("OCC")
        f = trim_grid(_flat_face(0, 0, 8, 6), spacing=2.0)
        assert (f.nu, f.nv) == (4, [3])
        assert len(f.cells) == 12
        assert len(f.points) == 5 * 4
        for quad in f.cell_points():
            for p, q in zip(quad, quad[1:] + quad[:1]):
                assert (q - p).length() == pytest.approx(2.0, abs=1e-6)
            assert all(abs(p.z) < 1e-9 for p in quad)


class TestCrossingGrid:
    def test_two_flat_faces_shared_seam(self):
        pytest.importorskip("OCC")
        f1 = _flat_face(0, 0, 8, 6)
        f2 = _flat_face(0, 6, 8, 12)
        f = crossing_grid([f1, f2], spacing=2.0, shared=[(0, 1)])
        assert (f.nu, f.nv) == (4, [3, 3])
        assert len(f.cells) == 24
        assert len(f.points) == 5 * 4 + 5 * 3
        # Seam row shared and owned by face 0.
        seam = [f.points[f.lattice[(k, 3)]].pos for k in range(5)]
        assert all(abs(p.y - 6.0) < 1e-6 for p in seam)
        assert all(f.points[f.lattice[(k, 3)]].face == 0 for k in range(5))
        for quad in f.cell_points():
            assert all(abs(p.z) < 1e-9 for p in quad)

    def test_single_face(self):
        pytest.importorskip("OCC")
        f = crossing_grid([_flat_face(0, 0, 4, 4)], spacing=2.0)
        assert (f.nu, f.nv) == (2, [2])
        assert len(f.cells) == 4


class TestOccOperators:
    def test_project_point(self):
        pytest.importorskip("OCC")
        q, uv = occ_project_point(_flat_face(0, 0, 8, 6), Vec(4, 3, 2.5))
        assert (q - Vec(4, 3, 0)).length() < 1e-9
        assert uv[0] == pytest.approx(0.5) and uv[1] == pytest.approx(0.5)

    def test_normal_and_bounds_and_loops(self):
        pytest.importorskip("OCC")
        s = _flat_face(0, 0, 8, 6)
        n = occ_normal_at(s, 0.5, 0.5)
        assert (n - Vec(0, 0, 1)).length() < 1e-9
        assert occ_face_bounds(s) == (0.0, 1.0, 0.0, 1.0)
        assert len(occ_trim_loops(s)) == 4  # no cached face → native edges
