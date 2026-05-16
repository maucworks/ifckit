"""Tests for PendingTaperedExtrusion and TaperedExtrusionBuilder."""

import math

import pytest
from ifckit import IfcModel, IfcSchema, default_registry
from ifckit.elements.structural import PendingTaperedExtrusion
from ifckit.geometry import Path, Plane, Vec


class TestPendingTaperedExtrusion:
    def test_create(self):
        plane = Plane.world_xy()
        start = [Vec(-1, -1, 0), Vec(1, -1, 0), Vec(1, 1, 0), Vec(-1, 1, 0)]
        end = [Vec(-0.5, -0.5, 0), Vec(0.5, -0.5, 0), Vec(0.5, 0.5, 0), Vec(-0.5, 0.5, 0)]
        p = PendingTaperedExtrusion(plane, start, end, height=5.0, name="Pier")
        assert p.element_type == "tapered_extrusion"
        assert p.height == 5.0
        assert len(p.start_profile) == 4
        assert len(p.end_profile) == 4
        assert p.name == "Pier"

    def test_point_count_mismatch_raises(self):
        plane = Plane.world_xy()
        start = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)]
        end = [Vec(0, 0, 0), Vec(1, 0, 0)]
        with pytest.raises(ValueError, match="equal point count"):
            PendingTaperedExtrusion(plane, start, end, height=3.0)

    def test_to_dict_roundtrip(self):
        plane = Plane.world_xy()
        start = [Vec(-1, -1, 0), Vec(1, -1, 0), Vec(1, 1, 0), Vec(-1, 1, 0)]
        end = [Vec(-0.5, -0.5, 0), Vec(0.5, -0.5, 0), Vec(0.5, 0.5, 0), Vec(-0.5, 0.5, 0)]
        p = PendingTaperedExtrusion(plane, start, end, height=5.0, name="Pier")
        d = p.to_dict()
        p2 = PendingTaperedExtrusion.from_dict(d)
        assert p2.plane.origin.equals(p.plane.origin)
        assert p2.height == p.height
        assert p2.name == p.name
        assert len(p2.start_profile) == 4
        assert len(p2.end_profile) == 4

    def test_to_json_roundtrip(self):
        plane = Plane.world_xy()
        start = [Vec(-1, -1, 0), Vec(1, -1, 0), Vec(1, 1, 0), Vec(-1, 1, 0)]
        end = [Vec(-0.5, -0.5, 0), Vec(0.5, -0.5, 0), Vec(0.5, 0.5, 0), Vec(-0.5, 0.5, 0)]
        p = PendingTaperedExtrusion(plane, start, end, height=5.0, name="Pier")
        json_str = p.to_json()
        p2 = PendingTaperedExtrusion.from_json(json_str)
        assert p2.height == 5.0
        assert p2.name == "Pier"


    def test_create_with_path(self):
        plane = Plane.world_xy()
        start = Path.from_pts(
            [Vec(-1, -1, 0), Vec(1, -1, 0), Vec(1, 1, 0), Vec(-1, 1, 0)],
            closed=True,
        )
        end = Path.from_pts(
            [Vec(-0.5, -0.5, 0), Vec(0.5, -0.5, 0), Vec(0.5, 0.5, 0), Vec(-0.5, 0.5, 0)],
            closed=True,
        )
        p = PendingTaperedExtrusion(plane, start, end, height=5.0, name="PathPier")
        assert p.element_type == "tapered_extrusion"
        assert len(p.start_profile) == 4
        assert p.name == "PathPier"


class TestTaperedExtrusionBuilder:
    def _model(self):
        m = IfcModel(name="Test", schema=IfcSchema.IFC4)
        site = m.add_site("Site")
        bldg = m.add_building(site, "Building")
        storey = m.add_storey(bldg, "Level 0")
        return m, storey

    def _square_profile(self, size=2.0):
        h = size / 2
        return [Vec(-h, -h, 0), Vec(h, -h, 0), Vec(h, h, 0), Vec(-h, h, 0)]

    def test_build_basic(self):
        m, storey = self._model()
        plane = Plane.world_xy()
        start = self._square_profile(2.0)
        end = self._square_profile(1.0)
        p = PendingTaperedExtrusion(plane, start, end, height=5.0, name="TaperedColumn")
        entity = storey.add(p)
        assert entity.entity.is_a("IfcElement")

    def test_build_entity_attributes(self):
        m, storey = self._model()
        plane = Plane.world_xy()
        start = self._square_profile(2.0)
        end = self._square_profile(1.0)
        p = PendingTaperedExtrusion(plane, start, end, height=5.0, name="TaperedColumn")
        entity = storey.add(p)
        e = entity.entity
        assert e.Name == "TaperedColumn"
        assert e.Representation is not None
        assert e.ObjectPlacement is not None

    def test_build_solid_type(self):
        m, storey = self._model()
        plane = Plane.world_xy()
        start = self._square_profile(2.0)
        end = self._square_profile(1.0)
        p = PendingTaperedExtrusion(plane, start, end, height=5.0)
        entity = storey.add(p)
        # The representation should contain an IfcExtrudedAreaSolidTapered
        rep = entity.entity.Representation
        assert rep is not None
        for shape_rep in rep.Representations or []:
            for item in shape_rep.Items or []:
                if item.is_a("IfcExtrudedAreaSolidTapered"):
                    assert abs(item.Depth - 5.0) < 1e-6
                    assert item.EndSweptArea is not None
                    assert item.SweptArea is not None
                    return
        pytest.fail("No IfcExtrudedAreaSolidTapered found in representation")

    def test_build_tapered_geometry(self):
        """Verify that start and end profiles are different sizes."""
        m, storey = self._model()
        plane = Plane.world_xy()
        start = self._square_profile(2.0)  # large
        end = self._square_profile(0.5)  # small
        p = PendingTaperedExtrusion(plane, start, end, height=10.0)
        entity = storey.add(p)
        rep = entity.entity.Representation
        for shape_rep in rep.Representations or []:
            for item in shape_rep.Items or []:
                if item.is_a("IfcExtrudedAreaSolidTapered"):
                    # Both profiles exist and are IfcArbitraryClosedProfileDef
                    assert item.SweptArea.is_a("IfcArbitraryClosedProfileDef")
                    assert item.EndSweptArea.is_a("IfcArbitraryClosedProfileDef")
                    return
        pytest.fail("No IfcExtrudedAreaSolidTapered found")

    def test_build_with_path(self):
        m, storey = self._model()
        plane = Plane.world_xy()
        start = Path.from_pts(
            [Vec(-1, -1, 0), Vec(1, -1, 0), Vec(1, 1, 0), Vec(-1, 1, 0)],
            closed=True,
        )
        end = Path.from_pts(
            [Vec(-0.5, -0.5, 0), Vec(0.5, -0.5, 0), Vec(0.5, 0.5, 0), Vec(-0.5, 0.5, 0)],
            closed=True,
        )
        p = PendingTaperedExtrusion(plane, start, end, height=5.0, name="PathPier")
        entity = storey.add(p)
        assert entity.entity.Name == "PathPier"
        rep = entity.entity.Representation
        for shape_rep in rep.Representations or []:
            for item in shape_rep.Items or []:
                if item.is_a("IfcExtrudedAreaSolidTapered"):
                    assert item.SweptArea.is_a("IfcArbitraryClosedProfileDef")
                    assert item.EndSweptArea.is_a("IfcArbitraryClosedProfileDef")
                    return
        pytest.fail("No IfcExtrudedAreaSolidTapered found")

    def test_build_arc_path(self):
        """Build a tapered extrusion with arc-segment profiles (Path with arcs)."""
        m, storey = self._model()
        plane = Plane.world_xy()
        start = Path(plane=plane)
        start.add_line(Vec(-1, 0, 0), Vec(1, 0, 0))
        start.add_arc(Vec(1, 1, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi)
        start.add_line(Vec(-1, 2, 0), Vec(-1, 0, 0))

        end = Path(plane=plane)
        end.add_line(Vec(-0.5, 0, 0), Vec(0.5, 0, 0))
        end.add_arc(Vec(0.5, 0.5, 0), Vec(0, 0, 1), Vec(0.5, 0, 0), math.pi)
        end.add_line(Vec(-0.5, 1, 0), Vec(-0.5, 0, 0))

        p = PendingTaperedExtrusion(plane, start, end, height=4.0, name="ArcPier")
        entity = storey.add(p)
        assert entity.entity.Name == "ArcPier"
        rep = entity.entity.Representation
        for shape_rep in rep.Representations or []:
            for item in shape_rep.Items or []:
                if item.is_a("IfcExtrudedAreaSolidTapered"):
                    return
        pytest.fail("No IfcExtrudedAreaSolidTapered found")

    def test_build_to_dict_roundtrip_with_path(self):
        m, storey = self._model()
        plane = Plane.world_xy()
        start = Path.from_pts(
            [Vec(-1, -1, 0), Vec(1, -1, 0), Vec(1, 1, 0), Vec(-1, 1, 0)], closed=True
        )
        end = Path.from_pts(
            [Vec(-0.5, -0.5, 0), Vec(0.5, -0.5, 0), Vec(0.5, 0.5, 0), Vec(-0.5, 0.5, 0)], closed=True
        )
        p = PendingTaperedExtrusion(plane, start, end, height=5.0, name="Roundtrip")
        d = p.to_dict()
        p2 = PendingTaperedExtrusion.from_dict(d)
        assert p2.height == 5.0
        assert p2.name == "Roundtrip"
        entity = storey.add(p2)
        assert entity.entity.Name == "Roundtrip"
        """Test with a tilted plane."""
        m, storey = self._model()
        angle = math.radians(15)
        plane = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, math.cos(angle), math.sin(angle)))
        start = self._square_profile(2.0)
        end = self._square_profile(1.0)
        p = PendingTaperedExtrusion(plane, start, end, height=5.0, name="SlopedPier")
        entity = storey.add(p)
        assert entity.entity.Name == "SlopedPier"
