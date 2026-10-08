"""Identity (id/meta) on geometry: minting, roundtrip, propagation."""

import copy
import re

from ifckit.geometry import Arc, Curve, Line, Path, Plane, Surface, Vec

HEX32 = re.compile(r"[0-9a-f]{32}")


def _line(**kw):
    return Line(Vec(0, 0, 0), Vec(5, 0, 0), **kw)


def _arc(**kw):
    return Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(5, 0, 0), 1.5708, **kw)


def _curve(**kw):
    return Curve(
        control_points=[Vec(0, 0, 0), Vec(10, 0, 0)],
        knots=[0.0, 1.0],
        multiplicities=[2, 2],
        degree=1,
        **kw,
    )


def _surface(**kw):
    return Surface(
        control_points=[[Vec(0, 0, 0), Vec(5, 0, 0)], [Vec(0, 5, 0), Vec(5, 5, 0)]],
        uknots=[0.0, 1.0],
        vknots=[0.0, 1.0],
        umults=[2, 2],
        vmults=[2, 2],
        udegree=1,
        vdegree=1,
        **kw,
    )


def _rect_path():
    return (
        Path(plane=Plane.world_xy())
        .add_line(Vec(0, 0, 0), Vec(5, 0, 0))
        .add_line(Vec(5, 0, 0), Vec(5, 3, 0))
        .add_line(Vec(5, 3, 0), Vec(0, 3, 0))
        .add_line(Vec(0, 3, 0), Vec(0, 0, 0))
    )


class TestMinting:
    def test_auto_uuid_unique(self):
        ids = {
            _line().id,
            _line().id,
            _arc().id,
            _curve().id,
            _surface().id,
            Path().id,
            Plane.world_xy().id,
        }
        assert len(ids) == 7
        assert all(HEX32.fullmatch(i) for i in ids)

    def test_vec_no_auto_id(self):
        v = Vec(1, 2, 3)
        assert v.id is None
        assert v.meta == {}
        assert Vec(1, 2, 3, id="p1", meta={"a": 1}).id == "p1"

    def test_explicit_id_meta(self):
        line = _line(id="seg-1", meta={"functie": "buitenfacade"})
        assert line.id == "seg-1"
        assert line.meta == {"functie": "buitenfacade"}

    def test_meta_dict_copied(self):
        meta = {"a": 1}
        line = _line(meta=meta)
        meta["a"] = 2
        assert line.meta == {"a": 1}


class TestRoundtrip:
    def test_line_arc(self):
        for obj in (_line(id="l", meta={"k": "v"}), _arc(id="a", meta={"k": "v"})):
            d = obj.to_dict()
            assert d["id"] == obj.id and d["meta"] == {"k": "v"}
            back = type(obj).from_dict(d)
            assert back.id == obj.id and back.meta == {"k": "v"}

    def test_old_dicts_mint_id(self):
        line = Line.from_dict(
            {"type": "line", "start": {"x": 0, "y": 0, "z": 0}, "end": {"x": 1, "y": 0, "z": 0}}
        )
        assert HEX32.fullmatch(line.id)
        vec = Vec.from_dict({"x": 0, "y": 0, "z": 0})
        assert vec.id is None

    def test_curve_surface_path(self):
        path = _rect_path()
        path.meta["gebouw"] = "A"
        for obj in (_curve(id="c"), _surface(id="s"), path, Plane.world_xy()):
            d = obj.to_dict()
            back = type(obj).from_dict(d)
            assert back.id == obj.id
            assert back.meta == obj.meta
        # Nested Vec/Plane dicts carry identity keys.
        assert "id" in path.to_dict()["segments"][0]["start"]
        assert "id" in path.to_dict()["plane"]


class TestCopy:
    def test_copy_shares_id_fresh_meta(self):
        line = _line(meta={"a": 1})
        c = copy.copy(line)
        assert c.id == line.id
        c.meta["a"] = 2
        assert line.meta == {"a": 1}

    def test_deepcopy_independent(self):
        path = _rect_path()
        d = copy.deepcopy(path)
        assert d.id == path.id
        assert [s.id for s in d.segments] == [s.id for s in path.segments]
        d.segments[0].meta["x"] = 1
        assert "x" not in path.segments[0].meta

    def test_duplicate_preserves(self):
        path = _rect_path()
        first = path.segments[0].id
        dup = path.duplicate()
        assert dup.id == path.id
        assert dup.segments[0].id == first


class TestPropagation:
    def test_transformed_preserves(self):
        line = _line(id="t", meta={"a": 1})
        moved = line.translated(Vec(1, 0, 0))
        assert moved.id == "t" and moved.meta == {"a": 1}
        # Identity preserved segment-wise against the source path:
        src = _rect_path()
        moved2 = src.translated(Vec(1, 0, 0))
        assert [s.id for s in moved2.segments] == [s.id for s in src.segments]
        assert moved2.id == src.id

    def test_subpath_trim_derives(self):
        path = _rect_path()
        src_id = path.segments[0].id
        sub = path.subpath(0.0, 0.1)
        assert sub.id != path.id
        assert sub.meta["derived_from"] == path.id
        assert sub.segments[0].id != src_id
        assert sub.segments[0].meta["derived_from"] == src_id

    def test_subpath_middle_preserved(self):
        path = _rect_path()
        mids = [s.id for s in path.segments[1:3]]
        sub = path.subpath(0.0, 0.99)
        kept = [s.id for s in sub.segments if s.id in mids]
        assert kept == mids

    def test_tessellate_derives(self):
        path = Path().add_arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(5, 0, 0), 1.5708)
        arc_id = path.segments[0].id
        tess = path.tessellate(30)
        assert tess.id != path.id
        assert all(s.meta.get("derived_from") == arc_id for s in tess.segments)
        assert all(isinstance(s, Line) for s in tess.segments)

    def test_fillet_derives(self):
        path = Path().add_line(Vec(0, 0, 0), Vec(5, 0, 0)).add_line(Vec(5, 0, 0), Vec(5, 5, 0))
        in_id, out_id = (s.id for s in path.segments)
        path.fillet(1, 1.0)
        assert len(path.segments) == 3
        assert path.segments[0].meta["derived_from"] == in_id
        assert path.segments[1].meta["derived_from"] == [in_id, out_id]
        assert path.segments[2].meta["derived_from"] == out_id

    def test_extend_preserves_middle(self):
        path = _rect_path()
        ids = [s.id for s in path.segments]
        ext = path.extend(end_dist=1.0)
        assert ext.id != path.id
        assert [s.id for s in ext.segments[:4]] == ids

    def test_assemble_preserves(self):
        from ifckit.geometry import assemble_path

        a = _line(id="a")
        b = Line(Vec(5, 0, 0), Vec(9, 0, 0), id="b")
        paths = assemble_path([a, b])
        assert [s.id for s in paths[0].segments] == ["a", "b"]

    def test_add_line_tagging(self):
        path = Path().add_line(
            Vec(0, 0, 0), Vec(1, 0, 0), id="facade-1", meta={"functie": "buitenfacade"}
        )
        assert path.segments[0].id == "facade-1"
        assert path.segments[0].meta == {"functie": "buitenfacade"}

    def test_reverse_move_keep_identity(self):
        path = _rect_path()
        ids = [s.id for s in path.segments]
        path.reverse()
        assert sorted(s.id for s in path.segments) == sorted(ids)
        path.move(Vec(1, 1, 0))
        assert sorted(s.id for s in path.segments) == sorted(ids)
