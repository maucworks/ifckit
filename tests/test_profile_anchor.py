"""
tests/test_profile_anchor.py
============================

Tests for the 9-point compass anchor system on all profile types.

The anchor controls where (0, 0) sits relative to the profile bounding box:

    nw ── n ── ne
    │           │
    w ─── c ─── e
    │           │
    sw ── s ── se

For each profile the tests verify:
  1. Default anchor produces the expected natural origin (backward-compat).
  2. Switching anchor moves the origin correctly.
  3. Anchor is serialized and round-tripped through to_dict/from_dict.
"""

from __future__ import annotations

import math

import pytest

from ifckit.profiles.shapes import CircleProfile, HollowCircleProfile, RectangleProfile
from ifckit.profiles.i_beam import IBeamProfile
from ifckit.profiles.l_beam import LBeamProfile
from ifckit.profiles.sections import (
    CShapeProfile,
    TrapeziumProfile,
    TShapeProfile,
    ZShapeProfile,
)
from ifckit.profiles.base import Profile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bbox(pts):
    """Return (x_min, y_min, x_max, y_max) of a point list."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _centroid(pts):
    """Return bounding-box centre."""
    x0, y0, x1, y1 = _bbox(pts)
    return (x0 + x1) / 2, (y0 + y1) / 2


# ---------------------------------------------------------------------------
# RectangleProfile
# ---------------------------------------------------------------------------


class TestRectangleAnchor:
    W, H = 0.2, 0.1

    def _pts(self, anchor, **kw):
        return RectangleProfile(self.W, self.H, anchor=anchor, **kw).get_profile_points()

    def test_default_anchor_is_c(self):
        p = RectangleProfile(self.W, self.H)
        assert p.anchor == "c"

    def test_c_centred_at_origin(self):
        pts = self._pts("c")
        cx, cy = _centroid(pts)
        assert abs(cx) < 1e-9
        assert abs(cy) < 1e-9

    def test_sw_bottom_left_at_origin(self):
        pts = self._pts("sw")
        x0, y0, _, _ = _bbox(pts)
        assert abs(x0) < 1e-9
        assert abs(y0) < 1e-9

    def test_ne_top_right_at_origin(self):
        pts = self._pts("ne")
        _, _, x1, y1 = _bbox(pts)
        assert abs(x1) < 1e-9
        assert abs(y1) < 1e-9

    def test_s_bottom_centre_at_origin(self):
        pts = self._pts("s")
        x0, y0, x1, _ = _bbox(pts)
        assert abs(y0) < 1e-9
        assert abs((x0 + x1) / 2) < 1e-9

    def test_n_top_centre_at_origin(self):
        pts = self._pts("n")
        x0, _, x1, y1 = _bbox(pts)
        assert abs(y1) < 1e-9
        assert abs((x0 + x1) / 2) < 1e-9

    def test_w_left_mid_at_origin(self):
        pts = self._pts("w")
        x0, y0, _, y1 = _bbox(pts)
        assert abs(x0) < 1e-9
        assert abs((y0 + y1) / 2) < 1e-9

    def test_offset_on_top_of_anchor(self):
        pts = self._pts("sw", offset_x=1.0, offset_y=2.0)
        x0, y0, _, _ = _bbox(pts)
        assert abs(x0 - 1.0) < 1e-9
        assert abs(y0 - 2.0) < 1e-9

    def test_roundtrip_anchor(self):
        p = RectangleProfile(self.W, self.H, anchor="sw", offset_x=0.5)
        d = p.to_dict()
        p2 = Profile.dispatch_from_dict(d)
        assert p2.anchor == "sw"
        assert abs(p2.offset_x - 0.5) < 1e-12

    def test_invalid_anchor_raises(self):
        with pytest.raises(ValueError):
            RectangleProfile(self.W, self.H, anchor="xx")

    def test_rotation_around_anchor(self):
        """After 90° rotation with anchor='sw', the bottom-left of the bounding
        box prior to rotation (the sw corner) stays at origin, but the rotated
        bbox is different.  Just check that the anchor-shifted centroid is at
        the expected rotated position (approx bounding-box centre of rectangle).
        """
        # With anchor='sw' and no rotation: sw at (0,0), centroid at (W/2, H/2).
        # After 90° CCW: centroid at (-H/2, W/2) — rotation around the sw point.
        pts = self._pts("sw", rotation=math.pi / 2)
        cx, cy = _centroid(pts)
        assert abs(cx - (-self.H / 2)) < 1e-9
        assert abs(cy - (self.W / 2)) < 1e-9


# ---------------------------------------------------------------------------
# CircleProfile
# ---------------------------------------------------------------------------


class TestCircleAnchor:
    R = 0.05

    def _pts(self, anchor, **kw):
        return CircleProfile(self.R, anchor=anchor, **kw).get_profile_points()

    def test_default_anchor_is_c(self):
        assert CircleProfile(self.R).anchor == "c"

    def test_c_centred_at_origin(self):
        cx, cy = _centroid(self._pts("c"))
        assert abs(cx) < 1e-6
        assert abs(cy) < 1e-6

    def test_sw_bbox_origin(self):
        # Circle approximated by 32 segments, so bbox edges are slightly inside r.
        pts = self._pts("sw")
        x0, y0, x1, y1 = _bbox(pts)
        # The leftmost/bottommost point should be near -R from centre.
        # After sw anchor, bbox sw should be near (0, 0).
        # Tolerance: 1 - cos(pi/32) ≈ 0.005 relative to R.
        tol = self.R * (1 - math.cos(math.pi / 32)) + 1e-9
        assert x0 > -tol
        assert y0 > -tol

    def test_roundtrip(self):
        p = CircleProfile(self.R, anchor="s")
        p2 = Profile.dispatch_from_dict(p.to_dict())
        assert p2.anchor == "s"


# ---------------------------------------------------------------------------
# HollowCircleProfile
# ---------------------------------------------------------------------------


class TestHollowCircleAnchor:
    R = 0.1

    def test_default_anchor_is_c(self):
        assert HollowCircleProfile(self.R, 0.01).anchor == "c"

    def test_c_centred_at_origin(self):
        pts = HollowCircleProfile(self.R, 0.01, anchor="c").get_profile_points()
        cx, cy = _centroid(pts)
        assert abs(cx) < 1e-6
        assert abs(cy) < 1e-6

    def test_roundtrip(self):
        p = HollowCircleProfile(self.R, 0.01, anchor="n")
        p2 = Profile.dispatch_from_dict(p.to_dict())
        assert p2.anchor == "n"


# ---------------------------------------------------------------------------
# TShapeProfile
# ---------------------------------------------------------------------------


class TestTShapeAnchor:
    def _p(self, anchor="s", **kw):
        return TShapeProfile(depth=0.2, flange_width=0.15, web_thickness=0.01,
                             flange_thickness=0.015, anchor=anchor, **kw)

    def test_default_anchor_is_s(self):
        assert self._p().anchor == "s"

    def test_s_bottom_centre_at_origin(self):
        pts = self._p("s").get_profile_points()
        x0, y0, x1, _ = _bbox(pts)
        assert abs(y0) < 1e-9
        assert abs((x0 + x1) / 2) < 1e-9

    def test_n_top_centre_at_origin(self):
        pts = self._p("n").get_profile_points()
        x0, _, x1, y1 = _bbox(pts)
        assert abs(y1) < 1e-9
        assert abs((x0 + x1) / 2) < 1e-9

    def test_c_centred_at_origin(self):
        pts = self._p("c").get_profile_points()
        cx, cy = _centroid(pts)
        assert abs(cx) < 1e-9
        assert abs(cy) < 1e-9

    def test_roundtrip(self):
        p = self._p("c", offset_x=0.01)
        p2 = Profile.dispatch_from_dict(p.to_dict())
        assert p2.anchor == "c"
        assert abs(p2.offset_x - 0.01) < 1e-12


# ---------------------------------------------------------------------------
# ZShapeProfile
# ---------------------------------------------------------------------------


class TestZShapeAnchor:
    def _p(self, anchor="c", **kw):
        return ZShapeProfile(depth=0.2, flange_width=0.08, web_thickness=0.008,
                             flange_thickness=0.012, anchor=anchor, **kw)

    def test_default_anchor_is_c(self):
        assert self._p().anchor == "c"

    def test_c_centred_at_origin(self):
        pts = self._p("c").get_profile_points()
        cx, cy = _centroid(pts)
        assert abs(cx) < 1e-9
        assert abs(cy) < 1e-9

    def test_s_bottom_at_origin(self):
        pts = self._p("s").get_profile_points()
        _, y0, _, _ = _bbox(pts)
        assert abs(y0) < 1e-9

    def test_roundtrip(self):
        p = self._p("sw")
        p2 = Profile.dispatch_from_dict(p.to_dict())
        assert p2.anchor == "sw"


# ---------------------------------------------------------------------------
# CShapeProfile
# ---------------------------------------------------------------------------


class TestCShapeAnchor:
    def _p(self, anchor="w", **kw):
        return CShapeProfile(depth=0.2, width=0.08, wall_thickness=0.003,
                             anchor=anchor, **kw)

    def test_default_anchor_is_w(self):
        assert self._p().anchor == "w"

    def test_w_left_mid_at_origin(self):
        pts = self._p("w").get_profile_points()
        x0, y0, _, y1 = _bbox(pts)
        assert abs(x0) < 1e-9
        assert abs((y0 + y1) / 2) < 1e-9

    def test_c_centred(self):
        pts = self._p("c").get_profile_points()
        cx, cy = _centroid(pts)
        assert abs(cx) < 1e-9
        assert abs(cy) < 1e-9

    def test_roundtrip(self):
        p = self._p("e")
        p2 = Profile.dispatch_from_dict(p.to_dict())
        assert p2.anchor == "e"


# ---------------------------------------------------------------------------
# TrapeziumProfile
# ---------------------------------------------------------------------------


class TestTrapeziumAnchor:
    def _p(self, anchor="s", **kw):
        return TrapeziumProfile(bottom_x_dim=0.3, top_x_dim=0.15, y_dim=0.2,
                                anchor=anchor, **kw)

    def test_default_anchor_is_s(self):
        assert self._p().anchor == "s"

    def test_s_bottom_centre_at_origin(self):
        pts = self._p("s").get_profile_points()
        x0, y0, x1, _ = _bbox(pts)
        assert abs(y0) < 1e-9
        assert abs((x0 + x1) / 2) < 1e-9

    def test_n_top_at_origin(self):
        pts = self._p("n").get_profile_points()
        _, _, _, y1 = _bbox(pts)
        assert abs(y1) < 1e-9

    def test_c_centred(self):
        pts = self._p("c").get_profile_points()
        cx, cy = _centroid(pts)
        assert abs(cx) < 1e-9
        assert abs(cy) < 1e-9

    def test_roundtrip(self):
        p = self._p("sw", offset_y=-0.1)
        p2 = Profile.dispatch_from_dict(p.to_dict())
        assert p2.anchor == "sw"
        assert abs(p2.offset_y - (-0.1)) < 1e-12


# ---------------------------------------------------------------------------
# IBeamProfile — already had anchor; verify serialization round-trip
# ---------------------------------------------------------------------------


class TestIBeamAnchorRoundtrip:
    def test_default_anchor_serialized(self):
        p = IBeamProfile(height=0.3, width=0.15, web_thickness=0.01,
                         flange_thickness=0.012, anchor="c")
        p2 = Profile.dispatch_from_dict(p.to_dict())
        assert p2.anchor == "c"

    def test_anchor_in_transform_dict(self):
        p = IBeamProfile(height=0.3, width=0.15, web_thickness=0.01,
                         flange_thickness=0.012, anchor="n")
        d = p.to_dict()
        assert d["anchor"] == "n"


# ---------------------------------------------------------------------------
# LBeamProfile — already had anchor; verify serialization round-trip
# ---------------------------------------------------------------------------


class TestLBeamAnchorRoundtrip:
    def test_default_anchor_serialized(self):
        p = LBeamProfile(height=0.2, width=0.15, thickness=0.01)
        p2 = Profile.dispatch_from_dict(p.to_dict())
        assert p2.anchor == "sw"

    def test_anchor_in_transform_dict(self):
        p = LBeamProfile(height=0.2, width=0.15, thickness=0.01, anchor="c")
        d = p.to_dict()
        assert d["anchor"] == "c"
