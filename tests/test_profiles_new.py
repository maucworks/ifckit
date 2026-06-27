"""
tests/test_profiles_new.py
==========================

Tests for the ifckit.profiles system:
  - IBeamProfile and LBeamProfile (basic + extended + to_ifc + from_dict)
  - Profile ABC + registry
  - PolygonProfile, RoundedPolygonProfile, RectangleProfile,
    CircleProfile, HollowCircleProfile
  - SteelProfile lookup table
  - profile_to_ifc() builder helper
  - PendingBeam round-trip with Profile object
"""

from __future__ import annotations

import math

import ifcopenshell
import pytest

from ifckit.profiles import (
    CircleProfile,
    HollowCircleProfile,
    IBeamProfile,
    LBeamProfile,
    PolygonProfile,
    Profile,
    RectangleProfile,
    RoundedPolygonProfile,
    SteelProfile,
)
from ifckit.profiles.base import RegisterProfileType

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ifc4_file():
    f = ifcopenshell.file(schema="IFC4")
    return f


# ---------------------------------------------------------------------------
# Profile ABC + registry
# ---------------------------------------------------------------------------


class TestProfileRegistry:
    @pytest.mark.parametrize(
        "profile_type",
        ["polygon", "rounded_polygon", "rectangle", "circle", "hollow_circle", "i_beam", "l_beam"],
    )
    def test_registered(self, profile_type):
        assert profile_type in RegisterProfileType._registry

    def test_dispatch_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown profile_type"):
            Profile.dispatch_from_dict({"profile_type": "__nonexistent__"})

    def test_dispatch_missing_key_raises(self):
        with pytest.raises(KeyError):
            Profile.dispatch_from_dict({})


# ---------------------------------------------------------------------------
# PolygonProfile
# ---------------------------------------------------------------------------


class TestPolygonProfile:
    def test_construction(self):
        p = PolygonProfile([(0, 0), (1, 0), (1, 1), (0, 1)])
        assert len(p.points) == 4

    def test_construction_from_tuples_3d(self):
        p = PolygonProfile([(0, 0, 5), (1, 0, 5), (1, 1, 5)])
        assert p.points[0].x == 0.0 and p.points[0].y == 0.0

    def test_too_few_points_raises(self):
        with pytest.raises(ValueError):
            PolygonProfile([(0, 0), (1, 0)])

    def test_to_dict_round_trip(self):
        p = PolygonProfile([(0, 0), (1, 0), (1, 1), (0, 1)], name="test")
        d = p.to_dict()
        assert d["profile_type"] == "polygon"
        p2 = Profile.dispatch_from_dict(d)
        assert isinstance(p2, PolygonProfile)
        assert p2.points == p.points
        assert p2.name == "test"

    def test_to_ifc_creates_arbitrary_closed(self, ifc4_file):
        p = PolygonProfile([(0, 0), (1, 0), (1, 1), (0, 1)])
        ent = p.to_ifc(ifc4_file)
        assert ent.is_a("IfcArbitraryClosedProfileDef")
        assert ent.OuterCurve.is_a("IfcPolyline")

    def test_to_ifc_ccw(self, ifc4_file):
        p = PolygonProfile([(0, 0), (0, 1), (1, 1), (1, 0)])
        ent = p.to_ifc(ifc4_file)
        coords = [(pt.Coordinates[0], pt.Coordinates[1]) for pt in ent.OuterCurve.Points[:-1]]
        n = len(coords)
        area = (
            sum(
                coords[i][0] * coords[(i + 1) % n][1] - coords[(i + 1) % n][0] * coords[i][1]
                for i in range(n)
            )
            / 2
        )
        assert area > 0

    def test_get_profile_points(self):
        pts = [(0, 0), (2, 0), (2, 1), (0, 1)]
        p = PolygonProfile(pts)
        assert p.get_profile_points() == pts


# ---------------------------------------------------------------------------
# RoundedPolygonProfile
# ---------------------------------------------------------------------------


class TestRoundedPolygonProfile:
    def test_construction(self):
        pts = [(0, 0), (4, 0), (4, 3), (0, 3)]
        p = RoundedPolygonProfile(pts, radius=0.1)
        assert len(p._raw_points) == 4
        assert p.radii == [0.1, 0.1, 0.1, 0.1]

    def test_per_corner_radius(self):
        pts = [(0, 0), (4, 0), (4, 3), (0, 3)]
        p = RoundedPolygonProfile(pts, radius=[0.1, 0.2, 0.0, 0.15])
        assert p.radii[2] == 0.0

    def test_radius_list_wrong_length_raises(self):
        with pytest.raises(ValueError, match="radius list"):
            RoundedPolygonProfile([(0, 0), (1, 0), (1, 1)], radius=[0.1, 0.2])

    def test_zero_radius_same_as_polygon(self):
        pts = [(0, 0), (4, 0), (4, 3), (0, 3)]
        p = RoundedPolygonProfile(pts, radius=0.0)
        outline = p.get_profile_points()
        assert len(outline) == 4

    def test_nonzero_radius_adds_arc_points(self):
        pts = [(0, 0), (4, 0), (4, 3), (0, 3)]
        p = RoundedPolygonProfile(pts, radius=0.2, arc_segments=4)
        outline = p.get_profile_points()
        assert len(outline) == 4 * 5

    def test_to_dict_round_trip(self):
        pts = [(0, 0), (4, 0), (4, 3), (0, 3)]
        p = RoundedPolygonProfile(pts, radius=0.15, name="rounded")
        d = p.to_dict()
        p2 = Profile.dispatch_from_dict(d)
        assert isinstance(p2, RoundedPolygonProfile)
        assert p2.radii == p.radii
        assert p2.name == "rounded"

    def test_to_ifc_creates_arbitrary_closed(self, ifc4_file):
        pts = [(0, 0), (4, 0), (4, 3), (0, 3)]
        p = RoundedPolygonProfile(pts, radius=0.1)
        ent = p.to_ifc(ifc4_file)
        assert ent.is_a("IfcArbitraryClosedProfileDef")


# ---------------------------------------------------------------------------
# RectangleProfile
# ---------------------------------------------------------------------------


class TestRectangleProfile:
    def test_construction(self):
        p = RectangleProfile(0.3, 0.5)
        assert p.x_dim == 0.3
        assert p.y_dim == 0.5

    def test_area(self):
        p = RectangleProfile(0.4, 0.6)
        assert math.isclose(p.area, 0.24, rel_tol=1e-9)

    def test_invalid_dims(self):
        with pytest.raises(ValueError):
            RectangleProfile(-1, 0.5)
        with pytest.raises(ValueError):
            RectangleProfile(0.3, 0)

    def test_to_ifc_is_rectangle_profile_def(self, ifc4_file):
        p = RectangleProfile(0.3, 0.5, name="REC300x500")
        ent = p.to_ifc(ifc4_file)
        assert ent.is_a("IfcRectangleProfileDef")
        assert ent.XDim == pytest.approx(0.3)
        assert ent.YDim == pytest.approx(0.5)
        assert ent.ProfileName == "REC300x500"

    def test_to_dict_round_trip(self):
        p = RectangleProfile(0.2, 0.4, name="myRect")
        d = p.to_dict()
        assert d["profile_type"] == "rectangle"
        p2 = Profile.dispatch_from_dict(d)
        assert isinstance(p2, RectangleProfile)
        assert p2.x_dim == 0.2
        assert p2.y_dim == 0.4
        assert p2.name == "myRect"

    def test_get_profile_points(self):
        p = RectangleProfile(0.2, 0.4)
        pts = p.get_profile_points()
        assert len(pts) == 4
        xs = [x for x, _ in pts]
        ys = [y for _, y in pts]
        assert math.isclose(max(xs) - min(xs), 0.2, rel_tol=1e-9)
        assert math.isclose(max(ys) - min(ys), 0.4, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# CircleProfile
# ---------------------------------------------------------------------------


class TestCircleProfile:
    def test_construction(self):
        p = CircleProfile(0.15)
        assert p.radius == 0.15

    def test_area(self):
        p = CircleProfile(1.0)
        assert math.isclose(p.area, math.pi, rel_tol=1e-9)

    def test_invalid_radius(self):
        with pytest.raises(ValueError):
            CircleProfile(0)

    def test_to_ifc_is_circle_profile_def(self, ifc4_file):
        p = CircleProfile(0.15, name="CIRC150")
        ent = p.to_ifc(ifc4_file)
        assert ent.is_a("IfcCircleProfileDef")
        assert ent.Radius == pytest.approx(0.15)

    def test_to_dict_round_trip(self):
        p = CircleProfile(0.1, name="col")
        d = p.to_dict()
        p2 = Profile.dispatch_from_dict(d)
        assert isinstance(p2, CircleProfile)
        assert p2.radius == 0.1

    def test_get_profile_points_32_points(self):
        p = CircleProfile(0.1)
        pts = p.get_profile_points()
        assert len(pts) == 32


# ---------------------------------------------------------------------------
# HollowCircleProfile
# ---------------------------------------------------------------------------


class TestHollowCircleProfile:
    def test_construction(self):
        p = HollowCircleProfile(radius=0.1, wall_thickness=0.005)
        assert math.isclose(p.inner_radius, 0.095, rel_tol=1e-9)

    def test_area(self):
        p = HollowCircleProfile(radius=0.1, wall_thickness=0.005)
        expected = math.pi * (0.1**2 - 0.095**2)
        assert math.isclose(p.area, expected, rel_tol=1e-9)

    def test_invalid_wall_thickness(self):
        with pytest.raises(ValueError):
            HollowCircleProfile(radius=0.1, wall_thickness=0.1)
        with pytest.raises(ValueError):
            HollowCircleProfile(radius=0.1, wall_thickness=0)

    def test_to_ifc_is_circle_hollow_profile_def(self, ifc4_file):
        p = HollowCircleProfile(radius=0.1, wall_thickness=0.005, name="CHS200x5")
        ent = p.to_ifc(ifc4_file)
        assert ent.is_a("IfcCircleHollowProfileDef")
        assert ent.Radius == pytest.approx(0.1)
        assert ent.WallThickness == pytest.approx(0.005)

    def test_to_dict_round_trip(self):
        p = HollowCircleProfile(radius=0.15, wall_thickness=0.008)
        d = p.to_dict()
        p2 = Profile.dispatch_from_dict(d)
        assert isinstance(p2, HollowCircleProfile)
        assert p2.radius == 0.15
        assert p2.wall_thickness == 0.008


# ---------------------------------------------------------------------------
# IBeamProfile
# ---------------------------------------------------------------------------


class TestIBeamProfile:
    def test_default_construction(self):
        p = IBeamProfile()
        assert p.height == 0.5
        assert p.width == 0.3

    def test_area(self):
        p = IBeamProfile(height=0.6, width=0.3, web_thickness=0.01, flange_thickness=0.01)
        assert math.isclose(p.area, 0.0118, rel_tol=1e-6)

    def test_web_height(self):
        p = IBeamProfile(height=0.6, width=0.3, web_thickness=0.01, flange_thickness=0.01)
        assert math.isclose(p.web_height, 0.58, rel_tol=1e-9)

    def test_centroid_symmetric(self):
        p = IBeamProfile(height=0.6, width=0.3, web_thickness=0.01, flange_thickness=0.01)
        assert math.isclose(p.centroid_z, 0.3, rel_tol=1e-9)

    def test_profile_points_count(self):
        p = IBeamProfile()
        pts = p.get_profile_points()
        assert len(pts) == 12

    def test_anchor_s_bottom_at_zero(self):
        p = IBeamProfile(height=0.6, width=0.3, web_thickness=0.01, flange_thickness=0.01, anchor='s')
        pts = p.get_profile_points()
        zs = [z for _, z in pts]
        assert math.isclose(min(zs), 0.0, abs_tol=1e-9)
        assert math.isclose(max(zs), 0.6, rel_tol=1e-9)

    def test_anchor_c_centred(self):
        p = IBeamProfile(height=0.6, width=0.3, web_thickness=0.01, flange_thickness=0.01, anchor='c')
        pts = p.get_profile_points()
        zs = [z for _, z in pts]
        assert math.isclose(min(zs), -0.3, abs_tol=1e-9)
        assert math.isclose(max(zs),  0.3, abs_tol=1e-9)

    def test_anchor_n_top_at_zero(self):
        p = IBeamProfile(height=0.6, width=0.3, web_thickness=0.01, flange_thickness=0.01, anchor='n')
        pts = p.get_profile_points()
        zs = [z for _, z in pts]
        assert math.isclose(max(zs), 0.0, abs_tol=1e-9)
        assert math.isclose(min(zs), -0.6, abs_tol=1e-9)

    def test_invalid_anchor(self):
        with pytest.raises(ValueError, match="anchor"):
            IBeamProfile(anchor='x')

    def test_invalid_web_thickness(self):
        with pytest.raises(ValueError):
            IBeamProfile(width=0.3, web_thickness=0.4)

    def test_invalid_flange_thickness(self):
        with pytest.raises(ValueError):
            IBeamProfile(height=0.6, flange_thickness=0.35)

    def test_to_dict(self):
        p = IBeamProfile(name="HEA200")
        d = p.to_dict()
        assert d["name"] == "HEA200"
        assert "area" in d
        assert "centroid_z" in d

    def test_all_anchors_smoke(self):
        for anchor in ('sw', 's', 'se', 'w', 'c', 'e', 'nw', 'n', 'ne'):
            p = IBeamProfile(anchor=anchor)
            pts = p.get_profile_points()
            assert len(pts) == 12

    def test_to_ifc_is_i_shape_profile_def(self, ifc4_file):
        p = IBeamProfile(
            height=0.3, width=0.15, web_thickness=0.007, flange_thickness=0.011, name="IPE300"
        )
        ent = p.to_ifc(ifc4_file)
        assert ent.is_a("IfcIShapeProfileDef")
        assert ent.OverallDepth == pytest.approx(0.3)
        assert ent.OverallWidth == pytest.approx(0.15)
        assert ent.WebThickness == pytest.approx(0.007)
        assert ent.FlangeThickness == pytest.approx(0.011)
        assert ent.ProfileName == "IPE300"

    def test_from_dict_round_trip(self):
        p = IBeamProfile(
            height=0.3, width=0.15, web_thickness=0.007, flange_thickness=0.011,
            anchor="c", name="IPE300",
        )
        d = p.to_dict()
        assert d["profile_type"] == "i_beam"
        p2 = Profile.dispatch_from_dict(d)
        assert isinstance(p2, IBeamProfile)
        assert p2.height == p.height
        assert p2.anchor == "c"

    def test_profile_type_attribute(self):
        assert IBeamProfile.profile_type == "i_beam"


# ---------------------------------------------------------------------------
# LBeamProfile
# ---------------------------------------------------------------------------


class TestLBeamProfile:
    def test_default_construction(self):
        p = LBeamProfile()
        assert p.height == 0.3
        assert p.width == 0.3

    def test_area(self):
        p = LBeamProfile(height=0.3, width=0.2, thickness=0.02)
        assert math.isclose(p.area, 0.0096, rel_tol=1e-6)

    def test_profile_points_count(self):
        p = LBeamProfile()
        pts = p.get_profile_points()
        assert len(pts) == 6

    def test_anchor_sw_bottom_left_at_zero(self):
        p = LBeamProfile(height=0.3, width=0.2, thickness=0.02, anchor='sw')
        pts = p.get_profile_points()
        ys = [y for y, _ in pts]
        zs = [z for _, z in pts]
        assert math.isclose(min(ys), 0.0, abs_tol=1e-9)
        assert math.isclose(min(zs), 0.0, abs_tol=1e-9)

    def test_anchor_sw_extents(self):
        p = LBeamProfile(height=0.3, width=0.2, thickness=0.02, anchor='sw')
        pts = p.get_profile_points()
        ys = [y for y, _ in pts]
        zs = [z for _, z in pts]
        assert math.isclose(max(ys), 0.2, rel_tol=1e-9)
        assert math.isclose(max(zs), 0.3, rel_tol=1e-9)

    def test_invalid_anchor(self):
        with pytest.raises(ValueError, match="anchor"):
            LBeamProfile(anchor='x')

    def test_invalid_thickness(self):
        with pytest.raises(ValueError):
            LBeamProfile(height=0.3, width=0.3, thickness=0.4)

    def test_centroid_y_positive(self):
        p = LBeamProfile(height=0.3, width=0.2, thickness=0.02)
        assert 0 < p.centroid_y < p.width

    def test_centroid_z_positive(self):
        p = LBeamProfile(height=0.3, width=0.2, thickness=0.02)
        assert 0 < p.centroid_z < p.height

    def test_to_dict(self):
        p = LBeamProfile(name="L100x100x10")
        d = p.to_dict()
        assert d["name"] == "L100x100x10"
        assert "area" in d

    def test_all_anchors_smoke(self):
        for anchor in ('sw', 's', 'se', 'w', 'c', 'e', 'nw', 'n', 'ne'):
            p = LBeamProfile(anchor=anchor)
            pts = p.get_profile_points()
            assert len(pts) == 6

    def test_to_ifc_is_l_shape_profile_def(self, ifc4_file):
        p = LBeamProfile(height=0.1, width=0.1, thickness=0.01, name="L100x100x10")
        ent = p.to_ifc(ifc4_file)
        assert ent.is_a("IfcLShapeProfileDef")
        assert ent.Depth == pytest.approx(0.1)
        assert ent.Width == pytest.approx(0.1)
        assert ent.Thickness == pytest.approx(0.01)

    def test_from_dict_round_trip(self):
        p = LBeamProfile(height=0.1, width=0.1, thickness=0.01, anchor="sw", name="L100x100x10")
        d = p.to_dict()
        assert d["profile_type"] == "l_beam"
        p2 = Profile.dispatch_from_dict(d)
        assert isinstance(p2, LBeamProfile)
        assert p2.thickness == p.thickness

    def test_profile_type_attribute(self):
        assert LBeamProfile.profile_type == "l_beam"


# ---------------------------------------------------------------------------
# SteelProfile lookup
# ---------------------------------------------------------------------------


class TestSteelProfile:
    def test_hea200(self):
        p = SteelProfile.from_name("HEA200")
        assert isinstance(p, IBeamProfile)
        assert p.name == "HEA200"
        assert math.isclose(p.height, 0.190, rel_tol=1e-6)
        assert math.isclose(p.width, 0.200, rel_tol=1e-6)

    def test_ipe300(self):
        p = SteelProfile.from_name("IPE300")
        assert isinstance(p, IBeamProfile)
        assert math.isclose(p.height, 0.300, rel_tol=1e-6)

    def test_heb300(self):
        p = SteelProfile.from_name("HEB300")
        assert isinstance(p, IBeamProfile)
        assert math.isclose(p.height, 0.300, rel_tol=1e-6)

    def test_hem200(self):
        p = SteelProfile.from_name("HEM200")
        assert isinstance(p, IBeamProfile)
        assert math.isclose(p.height, 0.220, rel_tol=1e-6)

    def test_chs_table(self):
        p = SteelProfile.from_name("CHS168.3x10")
        assert isinstance(p, HollowCircleProfile)
        assert math.isclose(p.radius, 0.168_3 / 2, rel_tol=1e-4)
        assert math.isclose(p.wall_thickness, 0.010, rel_tol=1e-6)

    def test_chs_on_the_fly(self):
        p = SteelProfile.from_name("CHS300x12")
        assert isinstance(p, HollowCircleProfile)
        assert math.isclose(p.radius, 0.150, rel_tol=1e-6)

    def test_unp200(self):
        p = SteelProfile.from_name("UNP200")
        assert isinstance(p, IBeamProfile)
        assert p.name == "UNP200"

    def test_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown steel section"):
            SteelProfile.from_name("XYZNOTREAL")

    def test_case_insensitive(self):
        p = SteelProfile.from_name("hea200")
        assert isinstance(p, IBeamProfile)

    def test_available_returns_families(self):
        avail = SteelProfile.available()
        assert "HEA" in avail
        assert "IPE" in avail
        assert "CHS" in avail
        assert "HEA200" in avail["HEA"]

    def test_custom_anchor(self):
        p = SteelProfile.from_name("IPE300", anchor="s")
        assert p.anchor == "s"

    def test_to_ifc(self, ifc4_file):
        p = SteelProfile.from_name("HEA200")
        ent = p.to_ifc(ifc4_file)
        assert ent.is_a("IfcIShapeProfileDef")

    def test_unit_millimetre_ibeam(self):
        from ifckit.schema import LengthUnit

        p = SteelProfile.from_name("HEA200", unit=LengthUnit.MILLIMETRE)
        assert isinstance(p, IBeamProfile)
        assert math.isclose(p.height, 190.0, rel_tol=1e-6)
        assert math.isclose(p.width, 200.0, rel_tol=1e-6)

    def test_unit_millimetre_chs(self):
        from ifckit.schema import LengthUnit

        p = SteelProfile.from_name("CHS168.3x10", unit=LengthUnit.MILLIMETRE)
        assert isinstance(p, HollowCircleProfile)
        assert math.isclose(p.radius, 168.3 / 2, rel_tol=1e-4)
        assert math.isclose(p.wall_thickness, 10.0, rel_tol=1e-6)

    def test_unit_metre_default_unchanged(self):
        from ifckit.schema import LengthUnit

        p_default = SteelProfile.from_name("IPE300")
        p_explicit = SteelProfile.from_name("IPE300", unit=LengthUnit.METRE)
        assert math.isclose(p_default.height, p_explicit.height, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# profile_to_ifc() helper in _geom
# ---------------------------------------------------------------------------


class TestProfileToIfc:
    def test_from_profile_object(self, ifc4_file):
        from ifckit.builders._geom import profile_to_ifc

        p = RectangleProfile(0.3, 0.5)
        ent = profile_to_ifc(ifc4_file, p)
        assert ent.is_a("IfcRectangleProfileDef")

    def test_from_point_list(self, ifc4_file):
        from ifckit.builders._geom import profile_to_ifc

        pts = [(0, 0), (1, 0), (1, 1), (0, 1)]
        ent = profile_to_ifc(ifc4_file, pts)
        assert ent.is_a("IfcArbitraryClosedProfileDef")

    def test_from_duck_typed_object(self, ifc4_file):
        from ifckit.builders._geom import profile_to_ifc

        class _Duck:
            def get_profile_points(self):
                return [(0, 0), (1, 0), (1, 1)]

        ent = profile_to_ifc(ifc4_file, _Duck())
        assert ent.is_a("IfcArbitraryClosedProfileDef")


# ---------------------------------------------------------------------------
# PendingBeam + Profile round-trip
# ---------------------------------------------------------------------------


class TestPendingBeamProfileRoundTrip:
    def test_ibeam_preserved_in_to_dict(self):
        from ifckit.elements import PendingBeam
        from ifckit.geometry import Line, Vec

        beam = PendingBeam(
            axis=Line(Vec(0, 0, 0), Vec(5, 0, 0)),
            profile=IBeamProfile(
                height=0.3, width=0.15, web_thickness=0.007, flange_thickness=0.011, name="IPE300"
            ),
        )
        d = beam.to_dict()
        assert isinstance(d["profile"], dict)
        assert d["profile"]["profile_type"] == "i_beam"

    def test_ibeam_reconstructed_from_dict(self):
        from ifckit.elements import PendingBeam
        from ifckit.geometry import Line, Vec

        beam = PendingBeam(
            axis=Line(Vec(0, 0, 0), Vec(5, 0, 0)),
            profile=IBeamProfile(
                height=0.3, width=0.15, web_thickness=0.007, flange_thickness=0.011, name="IPE300"
            ),
        )
        d = beam.to_dict()
        beam2 = PendingBeam.from_dict(d)
        assert isinstance(beam2._profile_source, IBeamProfile)
        assert beam2._profile_source.name == "IPE300"

    def test_point_list_profile_unchanged(self):
        from ifckit.elements import PendingBeam
        from ifckit.geometry import Line, Vec

        pts = [Vec(0, -0.05, 0), Vec(0.05, 0, 0), Vec(0, 0.05, 0), Vec(-0.05, 0, 0)]
        beam = PendingBeam(axis=Line(Vec(0, 0, 0), Vec(3, 0, 0)), profile=pts)
        d = beam.to_dict()
        assert isinstance(d["profile"], list)
        beam2 = PendingBeam.from_dict(d)
        assert len(beam2.profile) == 4
