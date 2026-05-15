"""Tests for PendingWallGraph to_dict/from_dict roundtrip."""

import math
import pytest
from ifckit.geometry import Vec, Plane, Path
from ifckit.elements.wall_graph import PendingWallGraph


class TestPathMode:
    def test_roundtrip_rect(self):
        outer = Path.from_pts(
            [Vec(0, 0, 0), Vec(4000, 0, 0), Vec(4000, 3000, 0), Vec(0, 3000, 0)],
            plane=Plane.world_xy(),
            closed=True,
        )
        outer.fillet([0, 1, 2, 3], 800)

        inner = outer.offset(200)
        path = outer.with_hole(inner)

        w1 = PendingWallGraph(path=path, thickness=200, height=3000)
        d = w1.to_dict()
        w2 = PendingWallGraph.from_dict(d)

        assert w2.thickness == 200
        assert w2.height == 3000
        assert w2.from_path is True
        assert w2.path is not None
        assert w2.path.is_closed is True
        assert len(w2.path.holes) == 1

    def test_roundtrip_open_path(self):
        p = (
            Path()
            .add_line(Vec(0, 0, 0), Vec(5, 0, 0))
            .add_arc(Vec(5, 1, 0), Vec(0, 0, 1), Vec(5, 0, 0), math.pi / 2)
        )
        w1 = PendingWallGraph(path=p, thickness=150, height=2500, name="CurvedWall")
        d = w1.to_dict()
        w2 = PendingWallGraph.from_dict(d)

        assert w2.thickness == 150
        assert w2.height == 2500
        assert w2.from_path is True
        assert w2.path is not None
        assert not w2.path.is_closed
        assert w2.path.length == pytest.approx(p.length)
        assert w2.path.start_point().equals(p.start_point())
        assert w2.path.end_point().equals(p.end_point())

    def test_roundtrip_preserves_fillets(self):
        pts = [Vec(0, 0, 0), Vec(1000, 0, 0), Vec(1000, 1000, 0), Vec(0, 1000, 0)]
        p = Path.from_pts(pts, closed=True)
        p.fillet([0, 1, 2, 3], 200)

        w1 = PendingWallGraph(path=p, thickness=100, height=2000)
        d = w1.to_dict()
        w2 = PendingWallGraph.from_dict(d)

        assert w2.from_path is True
        segs2 = w2.path.segments
        assert len(segs2) == 8  # 4 lines + 4 fillet arcs


class TestEdgeMode:
    def test_roundtrip_simple_wall(self):
        w1 = PendingWallGraph(
            vertices=[Vec(0, 0, 0), Vec(5000, 0, 0)],
            edges=[(0, 1)],
            plane=Plane.world_xy(),
            thickness=200,
            height=3000,
            name="Straight",
        )
        d = w1.to_dict()
        w2 = PendingWallGraph.from_dict(d)

        assert w2.thickness == 200
        assert w2.height == 3000
        assert not w2.from_path
        assert len(w2.vertices) == 2
        assert len(w2.edges) == 1

    def test_backward_compat_no_mode_field(self):
        d = {
            "vertices": [(0, 0, 0), (5000, 0, 0)],
            "edges": [(0, 1)],
            "plane": {
                "origin": {"x": 0, "y": 0, "z": 0},
                "x_axis": {"x": 1, "y": 0, "z": 0},
                "y_axis": {"x": 0, "y": 1, "z": 0},
            },
            "thickness": 200,
            "height": 3000,
            "name": "Legacy",
        }
        w = PendingWallGraph.from_dict(d)
        assert not w.from_path
        assert w.thickness == 200
        assert w.name == "Legacy"
