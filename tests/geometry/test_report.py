"""Homogeneous .report() interface: values, None-cases, find()."""

import dataclasses
import json
import math
import sys

import pytest

from ifckit.geometry import (
    Arc,
    ArcReport,
    Curve,
    CurveReport,
    Line,
    LineReport,
    Path,
    PathReport,
    Plane,
    PlaneReport,
    Surface,
    SurfaceReport,
    Vec,
    VecReport,
)


def _rect_path(w=5.0, h=3.0):
    return (
        Path(plane=Plane.world_xy())
        .add_line(Vec(0, 0, 0), Vec(w, 0, 0))
        .add_line(Vec(w, 0, 0), Vec(w, h, 0))
        .add_line(Vec(w, h, 0), Vec(0, h, 0))
        .add_line(Vec(0, h, 0), Vec(0, 0, 0))
    )


class TestValues:
    def test_line(self):
        r = Line(Vec(0, 0, 0), Vec(5, 0, 0), id="l").report()
        assert isinstance(r, LineReport)
        assert r.length == pytest.approx(5.0)
        assert r.id == "l"
        assert r.type == "line"

    def test_arc(self):
        r = Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(5, 0, 0), math.pi / 2).report()
        assert isinstance(r, ArcReport)
        assert r.length == pytest.approx(5 * math.pi / 2)
        assert r.radius == pytest.approx(5.0)
        assert r.angle == pytest.approx(math.pi / 2)

    def test_vec_plane(self):
        v = Vec(3, 4, 0).report()
        assert isinstance(v, VecReport)
        assert v.length == pytest.approx(5.0)
        assert v.coords == (3.0, 4.0, 0.0)
        p = Plane.world_xy().report()
        assert isinstance(p, PlaneReport)
        assert p.normal == (0.0, 0.0, 1.0)

    def test_rect_path(self):
        r = _rect_path().report()
        assert isinstance(r, PathReport)
        assert r.length == pytest.approx(16.0)
        assert r.area == pytest.approx(15.0)
        assert r.count == 4
        assert len(r.parts) == 4
        assert all(isinstance(p, LineReport) for p in r.parts)
        assert [p.length for p in r.parts] == pytest.approx([5.0, 3.0, 5.0, 3.0])

    def test_triangle_path(self):
        path = (
            Path()
            .add_line(Vec(0, 0, 0), Vec(4, 0, 0))
            .add_line(Vec(4, 0, 0), Vec(0, 3, 0))
            .add_line(Vec(0, 3, 0), Vec(0, 0, 0))
        )
        assert path.report().area == pytest.approx(6.0)

    def test_diamond_curve(self):
        # Clamped spans through the corners (straight edges sample exactly;
        # corner samples may shave slivers → relative tolerance).
        curve = Curve(
            control_points=[Vec(1, 0, 0), Vec(0, 1, 0), Vec(-1, 0, 0), Vec(0, -1, 0)],
            knots=[0.0, 1 / 3, 2 / 3, 1.0],
            multiplicities=[2, 1, 1, 2],
            degree=1,
            closed=True,
        )
        r = curve.report()
        assert isinstance(r, CurveReport)
        assert r.area == pytest.approx(2.0, rel=0.01)

    def test_flat_surface(self):
        pytest.importorskip("OCC")
        surf = Surface(
            control_points=[[Vec(0, 0, 0), Vec(5, 0, 0)], [Vec(0, 3, 0), Vec(5, 3, 0)]],
            uknots=[0.0, 1.0],
            vknots=[0.0, 1.0],
            umults=[2, 2],
            vmults=[2, 2],
            udegree=1,
            vdegree=1,
        )
        r = surf.report()
        assert isinstance(r, SurfaceReport)
        assert r.area == pytest.approx(15.0)


class TestNoneCases:
    def test_open_path_area_none(self):
        path = Path().add_line(Vec(0, 0, 0), Vec(5, 0, 0))
        assert path.report().area is None

    def test_open_curve_area_none(self):
        curve = Curve(
            control_points=[Vec(0, 0, 0), Vec(10, 0, 0)],
            knots=[0.0, 1.0],
            multiplicities=[2, 2],
            degree=1,
        )
        assert curve.report().area is None

    def test_surface_area_none_without_occ(self, monkeypatch):
        # Simulate a missing pythonocc-core. Both steps matter: cached
        # OCC.* submodule entries bypass the parent check, so purge them
        # first, then block the parent lookup itself.
        for mod in [m for m in list(sys.modules) if m == "OCC" or m.startswith("OCC.")]:
            monkeypatch.delitem(sys.modules, mod)
        monkeypatch.setitem(sys.modules, "OCC", None)
        surf = Surface(
            control_points=[[Vec(0, 0, 0), Vec(5, 0, 0)], [Vec(0, 3, 0), Vec(5, 3, 0)]],
            uknots=[0.0, 1.0],
            vknots=[0.0, 1.0],
            umults=[2, 2],
            vmults=[2, 2],
            udegree=1,
            vdegree=1,
        )
        assert surf.report().area is None


class TestFind:
    def _tagged_path(self):
        return (
            Path()
            .add_line(Vec(0, 0, 0), Vec(5, 0, 0), id="facade-1", meta={"functie": "buitenfacade"})
            .add_line(Vec(5, 0, 0), Vec(5, 3, 0), id="wand-1", meta={"functie": "woningscheidend"})
            .add_line(Vec(5, 3, 0), Vec(0, 3, 0))
        )

    def test_find_by_meta(self):
        path = self._tagged_path()
        found = path.find(functie="buitenfacade")
        assert [s.id for s in found] == ["facade-1"]

    def test_find_by_id(self):
        path = self._tagged_path()
        assert path.find(id="wand-1")[0].meta == {"functie": "woningscheidend"}

    def test_find_no_match(self):
        assert self._tagged_path().find(functie="dak") == []
        assert self._tagged_path().find(id="bestaat-niet") == []

    def test_find_in_holes(self):
        outer = _rect_path()
        hole = Path().add_line(
            Vec(1, 1, 0), Vec(2, 1, 0), id="sparing", meta={"functie": "sparing"}
        )
        outer = outer.with_hole(hole)
        assert [s.id for s in outer.find(functie="sparing")] == ["sparing"]

    def test_find_subset_semantics(self):
        path = self._tagged_path()
        path.segments[0].meta["laag"] = "BG"
        assert path.find(functie="buitenfacade", laag="BG") != []
        assert path.find(functie="buitenfacade", laag="1e") == []


class TestReportShape:
    def test_immutable(self):
        r = _rect_path().report()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.length = 0.0

    def test_json_serializable(self):
        d = _rect_path().report().to_dict()
        assert json.loads(json.dumps(d))["area"] == pytest.approx(15.0)
        assert d["parts"][0]["type"] == "line"

    def test_str_human(self):
        s = str(_rect_path().report())
        assert s.startswith("PathReport(") and "15.000" in s

    def test_report_carries_meta(self):
        p = Path(meta={"project": "A"}).add_line(Vec(0, 0, 0), Vec(1, 0, 0))
        assert p.report().meta == {"project": "A"}
