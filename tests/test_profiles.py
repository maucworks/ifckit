"""
tests/test_profiles.py
======================

Tests for IBeamProfile and LBeamProfile.
"""

import math
import pytest

from ifckit.profiles import IBeamProfile, LBeamProfile


# ---------------------------------------------------------------------------
# IBeamProfile
# ---------------------------------------------------------------------------

class TestIBeamProfile:

    def test_default_construction(self):
        p = IBeamProfile()
        assert p.height == 0.5
        assert p.width == 0.3

    def test_area(self):
        # w=0.3, h=0.6, tw=0.01, tf=0.01
        # area = 2 * 0.3*0.01 + (0.6 - 0.02)*0.01 = 0.006 + 0.0058 = 0.0118
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
        """anchor='s': Z origin at bottom mid, so first point Z=0."""
        p = IBeamProfile(height=0.6, width=0.3, web_thickness=0.01, flange_thickness=0.01, anchor='s')
        pts = p.get_profile_points()
        zs = [z for _, z in pts]
        assert math.isclose(min(zs), 0.0, abs_tol=1e-9)
        assert math.isclose(max(zs), 0.6, rel_tol=1e-9)

    def test_anchor_c_centred(self):
        """anchor='c': profile is centred on Z=0."""
        p = IBeamProfile(height=0.6, width=0.3, web_thickness=0.01, flange_thickness=0.01, anchor='c')
        pts = p.get_profile_points()
        zs = [z for _, z in pts]
        assert math.isclose(min(zs), -0.3, abs_tol=1e-9)
        assert math.isclose(max(zs),  0.3, abs_tol=1e-9)

    def test_anchor_n_top_at_zero(self):
        """anchor='n': Z origin at top, so max Z=0."""
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


# ---------------------------------------------------------------------------
# LBeamProfile
# ---------------------------------------------------------------------------

class TestLBeamProfile:

    def test_default_construction(self):
        p = LBeamProfile()
        assert p.height == 0.3
        assert p.width == 0.3

    def test_area(self):
        # h=0.3, w=0.2, t=0.02
        # area = 0.2*0.02 + (0.3-0.02)*0.02 = 0.004 + 0.0056 = 0.0096
        p = LBeamProfile(height=0.3, width=0.2, thickness=0.02)
        assert math.isclose(p.area, 0.0096, rel_tol=1e-6)

    def test_profile_points_count(self):
        p = LBeamProfile()
        pts = p.get_profile_points()
        assert len(pts) == 6

    def test_anchor_sw_bottom_left_at_zero(self):
        """anchor='sw': origin at bottom-left, so min Y=0 and min Z=0."""
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
