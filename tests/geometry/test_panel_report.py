"""
Tests for ifckit.geometry.panel_report — cell metrics (no OCC needed).
"""

from __future__ import annotations

import pytest

from ifckit.geometry import Vec
from ifckit.geometry.field import Field, FieldPoint
from ifckit.geometry.panel_report import FieldReport, cells_report, field_report


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


class TestCellsReport:
    def test_unit_square(self):
        rep = cells_report([[Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0), Vec(0, 1, 0)]])
        assert rep.n_cells == 1
        assert rep.edge_min == pytest.approx(1.0)
        assert rep.edge_mean == pytest.approx(1.0)
        assert rep.edge_max == pytest.approx(1.0)
        assert rep.angle_max_dev == pytest.approx(0.0, abs=1e-9)
        assert rep.planarity_max == pytest.approx(0.0, abs=1e-12)

    def test_lifted_corner(self):
        # Plane through first three corners; d drops 0.5/sqrt(1.25) below it.
        rep = cells_report([[Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0.5), Vec(0, 1, 0)]])
        assert rep.planarity_max == pytest.approx(0.44721359)

    def test_empty(self):
        assert cells_report([]).n_cells == 0

    def test_degenerate(self):
        with pytest.raises(ValueError):
            cells_report([[Vec(0, 0, 0), Vec(1, 0, 0)]])

    def test_equilateral_triangle(self):
        import math as _math

        tri = [[Vec(0, 0, 0), Vec(1, 0, 0), Vec(0.5, _math.sqrt(3) / 2, 0)]]
        rep = cells_report(tri)
        assert rep.n_cells == 1
        assert rep.edge_max == pytest.approx(1.0)
        assert rep.angle_max_dev == pytest.approx(0.0, abs=1e-9)
        assert rep.planarity_max == pytest.approx(0.0, abs=1e-12)


class TestFieldReport:
    def test_flat_field(self):
        rep = field_report(_flat_field())
        assert rep.n_cells == 4
        assert rep.edge_max == pytest.approx(1.0)
        assert rep.planarity_max == pytest.approx(0.0, abs=1e-12)
        assert rep.meta["field_id"] is not None
        d = rep.to_dict()
        assert d["type"] == "field_report" and d["n_cells"] == 4

    def test_str(self):
        assert isinstance(str(FieldReport(n_cells=2)), str)


class TestFacadeParity:
    """The facade resolves to the promoted implementation."""

    def test_names_are_the_promoted_objects(self):
        import geometrykit.geometry.panel as promoted

        from ifckit.geometry import panel_report as facade

        assert facade.FieldReport is promoted.FieldReport
        assert facade.cells_report is promoted.cells_report
        assert facade.field_report is promoted.field_report

    def test_reports_agree_on_metrics(self):
        import geometrykit.geometry.panel as promoted

        cells = [
            [Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0), Vec(0, 1, 0)],
            [Vec(2, 0, 0), Vec(3, 0, 0), Vec(3, 1, 0.5), Vec(2, 1, 0)],
        ]
        from geometrykit.geometry import Vec as GVec

        g_cells = [[GVec(p.x, p.y, p.z) for p in cell] for cell in cells]
        mine = cells_report(cells)
        theirs = promoted.cells_report(g_cells)
        for key in (
            "n_cells",
            "edge_min",
            "edge_mean",
            "edge_max",
            "angle_max_dev",
            "planarity_max",
        ):
            assert getattr(mine, key) == pytest.approx(getattr(theirs, key))
