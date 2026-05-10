"""
tests/test_profile_transform.py
================================

Tests for rotation, offset_x, offset_y on all Profile subclasses.
Covers:
  - _apply_transform(): rotate, translate, combined
  - get_profile_points() reflects transform
  - to_ifc() emits correct IfcAxis2Placement2D Location and RefDirection
  - to_dict() / from_dict() round-trips transform parameters
  - IBeamProfile: anchor offset + rotation/offset combined correctly
  - LBeamProfile: same
  - SteelProfile.from_name() passes rotation/offset through
"""

from __future__ import annotations

import math
import pytest
import ifcopenshell

from ifckit.profiles.base import Profile
from ifckit.profiles.shapes import (
    PolygonProfile,
    RoundedPolygonProfile,
    RectangleProfile,
    CircleProfile,
    HollowCircleProfile,
)
from ifckit.profiles.i_beam import IBeamProfile
from ifckit.profiles.l_beam import LBeamProfile
from ifckit.profiles.steel import SteelProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ifc():
    return ifcopenshell.file(schema="IFC4")


def _placement_coords(ifc_file, entity):
    """Return (loc_x, loc_y) from IfcAxis2Placement2D.Location."""
    pos = entity.Position
    return tuple(pos.Location.Coordinates)


def _placement_ref(ifc_file, entity):
    """Return (ref_x, ref_y) from IfcAxis2Placement2D.RefDirection, or None."""
    pos = entity.Position
    if pos.RefDirection is None:
        return None
    return tuple(pos.RefDirection.DirectionRatios)


# ---------------------------------------------------------------------------
# _apply_transform: unit tests on the base helper
# ---------------------------------------------------------------------------


class _ConcreteProfile(RectangleProfile):
    """Subclass to expose _apply_transform for testing."""


def test_apply_transform_identity():
    p = _ConcreteProfile(x_dim=0.1, y_dim=0.2)
    pts = [(1.0, 0.0), (0.0, 1.0)]
    assert p._apply_transform(pts) == pts


def test_apply_transform_rotation_90():
    p = _ConcreteProfile(x_dim=0.1, y_dim=0.2, rotation=math.pi / 2)
    result = p._apply_transform([(1.0, 0.0)])
    x, y = result[0]
    assert abs(x - 0.0) < 1e-9
    assert abs(y - 1.0) < 1e-9


def test_apply_transform_offset():
    p = _ConcreteProfile(x_dim=0.1, y_dim=0.2, offset_x=0.05, offset_y=0.10)
    result = p._apply_transform([(0.0, 0.0)])
    assert abs(result[0][0] - 0.05) < 1e-9
    assert abs(result[0][1] - 0.10) < 1e-9


def test_apply_transform_combined():
    """Rotate 90° then translate by (1, 2)."""
    p = _ConcreteProfile(x_dim=0.1, y_dim=0.2, rotation=math.pi / 2, offset_x=1.0, offset_y=2.0)
    result = p._apply_transform([(1.0, 0.0)])
    x, y = result[0]
    # (1,0) rotated 90° → (0, 1); then + (1, 2) → (1, 3)
    assert abs(x - 1.0) < 1e-9
    assert abs(y - 3.0) < 1e-9


# ---------------------------------------------------------------------------
# RectangleProfile
# ---------------------------------------------------------------------------


def test_rectangle_get_profile_points_offset():
    p = RectangleProfile(x_dim=0.2, y_dim=0.1, offset_x=1.0, offset_y=2.0)
    pts = p.get_profile_points()
    xs = [pt[0] for pt in pts]
    ys = [pt[1] for pt in pts]
    # centred at (1, 2) with half-widths 0.1 and 0.05
    assert abs(min(xs) - (1.0 - 0.1)) < 1e-9
    assert abs(max(xs) - (1.0 + 0.1)) < 1e-9
    assert abs(min(ys) - (2.0 - 0.05)) < 1e-9
    assert abs(max(ys) - (2.0 + 0.05)) < 1e-9


def test_rectangle_to_ifc_location():
    f = _ifc()
    p = RectangleProfile(x_dim=0.2, y_dim=0.1, offset_x=0.3, offset_y=0.4)
    ent = p.to_ifc(f)
    loc = _placement_coords(f, ent)
    assert abs(loc[0] - 0.3) < 1e-9
    assert abs(loc[1] - 0.4) < 1e-9
    assert _placement_ref(f, ent) is None  # no rotation → no RefDirection


def test_rectangle_to_ifc_rotation():
    f = _ifc()
    angle = math.pi / 4
    p = RectangleProfile(x_dim=0.2, y_dim=0.1, rotation=angle)
    ent = p.to_ifc(f)
    ref = _placement_ref(f, ent)
    assert ref is not None
    assert abs(ref[0] - math.cos(angle)) < 1e-9
    assert abs(ref[1] - math.sin(angle)) < 1e-9


def test_rectangle_roundtrip():
    p = RectangleProfile(x_dim=0.2, y_dim=0.1, rotation=0.5, offset_x=0.1, offset_y=-0.2)
    d = p.to_dict()
    p2 = Profile.dispatch_from_dict(d)
    assert abs(p2.rotation - 0.5) < 1e-12
    assert abs(p2.offset_x - 0.1) < 1e-12
    assert abs(p2.offset_y - (-0.2)) < 1e-12


# ---------------------------------------------------------------------------
# CircleProfile — offset only (rotation has no visible effect on circle)
# ---------------------------------------------------------------------------


def test_circle_to_ifc_offset():
    f = _ifc()
    p = CircleProfile(radius=0.05, offset_x=0.1, offset_y=0.2)
    ent = p.to_ifc(f)
    loc = _placement_coords(f, ent)
    assert abs(loc[0] - 0.1) < 1e-9
    assert abs(loc[1] - 0.2) < 1e-9


def test_circle_roundtrip():
    p = CircleProfile(radius=0.05, rotation=1.0, offset_x=0.1, offset_y=0.2)
    d = p.to_dict()
    p2 = Profile.dispatch_from_dict(d)
    assert abs(p2.rotation - 1.0) < 1e-12
    assert abs(p2.offset_x - 0.1) < 1e-12


# ---------------------------------------------------------------------------
# HollowCircleProfile
# ---------------------------------------------------------------------------


def test_hollow_circle_to_ifc_offset():
    f = _ifc()
    p = HollowCircleProfile(radius=0.1, wall_thickness=0.01, offset_x=0.5, offset_y=-0.3)
    ent = p.to_ifc(f)
    loc = _placement_coords(f, ent)
    assert abs(loc[0] - 0.5) < 1e-9
    assert abs(loc[1] - (-0.3)) < 1e-9


def test_hollow_circle_roundtrip():
    p = HollowCircleProfile(radius=0.1, wall_thickness=0.01, offset_x=0.5, offset_y=-0.3)
    d = p.to_dict()
    p2 = Profile.dispatch_from_dict(d)
    assert abs(p2.offset_x - 0.5) < 1e-12
    assert abs(p2.offset_y - (-0.3)) < 1e-12


# ---------------------------------------------------------------------------
# PolygonProfile
# ---------------------------------------------------------------------------


def test_polygon_get_profile_points_rotation():
    angle = math.pi / 2
    p = PolygonProfile(points=[(1, 0), (0, 1), (-1, 0)], rotation=angle)
    pts = p.get_profile_points()
    # Default anchor "c" on bbox (w=2, h=1, sw=(-1,0)):
    #   dx = -1-(-1)=0, dy = -0.5-0=-0.5
    #   (1,0) → (1, -0.5) → rotated 90° → (0.5, 1)
    x, y = pts[0]
    assert abs(x - 0.5) < 1e-9
    assert abs(y - 1.0) < 1e-9


def test_polygon_roundtrip():
    p = PolygonProfile(points=[(1, 0), (0, 1), (-1, 0)], rotation=0.3, offset_x=1.0, offset_y=2.0)
    d = p.to_dict()
    p2 = Profile.dispatch_from_dict(d)
    assert abs(p2.rotation - 0.3) < 1e-12
    assert abs(p2.offset_x - 1.0) < 1e-12


# ---------------------------------------------------------------------------
# IBeamProfile — anchor + rotation + offset
# ---------------------------------------------------------------------------


def test_ibeam_to_ifc_anchor_only():
    """anchor='s' (mid-bottom): centroid of IFC I-shape should be at (0, h/2)."""
    f = _ifc()
    h = 0.2
    p = IBeamProfile(height=h, width=0.1, web_thickness=0.006, flange_thickness=0.01, anchor="s")
    ent = p.to_ifc(f)
    loc = _placement_coords(f, ent)
    assert abs(loc[0] - 0.0) < 1e-9
    assert abs(loc[1] - h / 2) < 1e-9


def test_ibeam_to_ifc_anchor_with_offset():
    f = _ifc()
    h = 0.2
    p = IBeamProfile(
        height=h,
        width=0.1,
        web_thickness=0.006,
        flange_thickness=0.01,
        anchor="s",
        offset_x=0.05,
        offset_y=0.1,
    )
    ent = p.to_ifc(f)
    loc = _placement_coords(f, ent)
    assert abs(loc[0] - 0.05) < 1e-9
    assert abs(loc[1] - (h / 2 + 0.1)) < 1e-9


def test_ibeam_to_ifc_rotation():
    f = _ifc()
    angle = math.pi / 6
    p = IBeamProfile(
        height=0.2, width=0.1, web_thickness=0.006, flange_thickness=0.01, rotation=angle
    )
    ent = p.to_ifc(f)
    ref = _placement_ref(f, ent)
    assert ref is not None
    assert abs(ref[0] - math.cos(angle)) < 1e-9
    assert abs(ref[1] - math.sin(angle)) < 1e-9


def test_ibeam_get_profile_points_rotation():
    """With 90° rotation the original X-extent becomes Y-extent."""
    p_base = IBeamProfile(height=0.2, width=0.1, web_thickness=0.006, flange_thickness=0.01)
    p_rot = IBeamProfile(
        height=0.2, width=0.1, web_thickness=0.006, flange_thickness=0.01, rotation=math.pi / 2
    )
    base_pts = p_base.get_profile_points()
    rot_pts = p_rot.get_profile_points()
    base_x_span = max(x for x, _ in base_pts) - min(x for x, _ in base_pts)
    rot_y_span = max(y for _, y in rot_pts) - min(y for _, y in rot_pts)
    assert abs(base_x_span - rot_y_span) < 1e-9


def test_ibeam_roundtrip():
    p = IBeamProfile(
        height=0.2,
        width=0.1,
        web_thickness=0.006,
        flange_thickness=0.01,
        rotation=0.4,
        offset_x=0.02,
        offset_y=-0.01,
    )
    d = p.to_dict()
    p2 = IBeamProfile.from_dict(d)
    assert abs(p2.rotation - 0.4) < 1e-12
    assert abs(p2.offset_x - 0.02) < 1e-12
    assert abs(p2.offset_y - (-0.01)) < 1e-12


# ---------------------------------------------------------------------------
# LBeamProfile
# ---------------------------------------------------------------------------


def test_lbeam_to_ifc_offset():
    f = _ifc()
    p = LBeamProfile(
        height=0.15, width=0.1, thickness=0.01, anchor="sw", offset_x=0.1, offset_y=0.2
    )
    ent = p.to_ifc(f)
    loc = _placement_coords(f, ent)
    # anchor='sw' → anchor offset (0,0); user offset adds (0.1, 0.2)
    assert abs(loc[0] - 0.1) < 1e-9
    assert abs(loc[1] - 0.2) < 1e-9


def test_lbeam_roundtrip():
    p = LBeamProfile(
        height=0.15, width=0.1, thickness=0.01, rotation=1.2, offset_x=0.1, offset_y=0.2
    )
    d = p.to_dict()
    p2 = LBeamProfile.from_dict(d)
    assert abs(p2.rotation - 1.2) < 1e-12
    assert abs(p2.offset_x - 0.1) < 1e-12


# ---------------------------------------------------------------------------
# SteelProfile.from_name passes through rotation / offset
# ---------------------------------------------------------------------------


def test_steel_from_name_rotation():
    p = SteelProfile.from_name("IPE200", rotation=math.pi / 2, offset_x=0.05)
    assert isinstance(p, IBeamProfile)
    assert abs(p.rotation - math.pi / 2) < 1e-12
    assert abs(p.offset_x - 0.05) < 1e-12


def test_steel_chs_offset():
    p = SteelProfile.from_name("CHS168.3X10", offset_x=0.1, offset_y=-0.1)
    assert isinstance(p, HollowCircleProfile)
    assert abs(p.offset_x - 0.1) < 1e-12
    assert abs(p.offset_y - (-0.1)) < 1e-12
