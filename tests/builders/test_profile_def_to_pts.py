"""Tests for _profile_def_to_pts — focusing on Position (IfcAxis2Placement2D) application.

Each native parametric profile type carries an optional Position attribute.
These tests verify that translation and rotation encoded in Position are
correctly applied to the returned outline points.
"""
from __future__ import annotations

import math

import ifcopenshell
import pytest

from ifckit.builders._geom import _apply_axis2placement2d, _profile_def_to_pts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_file() -> ifcopenshell.file:
    return ifcopenshell.file(schema="IFC4")


def _make_placement(f: ifcopenshell.file, tx: float, ty: float, angle_deg: float = 0.0):
    """Create IfcAxis2Placement2D with given translation and rotation."""
    angle = math.radians(angle_deg)
    rx, ry = math.cos(angle), math.sin(angle)
    ref_dir = f.create_entity("IfcDirection", DirectionRatios=[rx, ry])
    loc = f.create_entity("IfcCartesianPoint", Coordinates=[tx, ty])
    return f.create_entity("IfcAxis2Placement2D", Location=loc, RefDirection=ref_dir)


def _centroid(pts):
    n = len(pts)
    return sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n


def _approx(a, b, tol=1e-9):
    return abs(a - b) < tol


# ---------------------------------------------------------------------------
# _apply_axis2placement2d unit tests
# ---------------------------------------------------------------------------

class TestApplyAxis2Placement2D:
    def test_none_position_is_identity(self):
        pts = [(1.0, 2.0), (3.0, 4.0)]
        assert _apply_axis2placement2d(pts, None) == pts

    def test_pure_translation(self):
        f = _make_file()
        pos = _make_placement(f, tx=10.0, ty=5.0)
        pts = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        result = _apply_axis2placement2d(pts, pos)
        assert _approx(result[0][0], 10.0) and _approx(result[0][1], 5.0)
        assert _approx(result[1][0], 11.0) and _approx(result[1][1], 5.0)

    def test_pure_rotation_90deg(self):
        f = _make_file()
        pos = _make_placement(f, tx=0.0, ty=0.0, angle_deg=90.0)
        pts = [(1.0, 0.0)]
        result = _apply_axis2placement2d(pts, pos)
        # (1,0) rotated 90° → (0,1)
        assert _approx(result[0][0], 0.0, tol=1e-9)
        assert _approx(result[0][1], 1.0, tol=1e-9)

    def test_translation_and_rotation(self):
        f = _make_file()
        pos = _make_placement(f, tx=2.0, ty=3.0, angle_deg=90.0)
        pts = [(1.0, 0.0)]
        result = _apply_axis2placement2d(pts, pos)
        # (1,0) rotated 90° → (0,1), then translated → (2,4)
        assert _approx(result[0][0], 2.0, tol=1e-9)
        assert _approx(result[0][1], 4.0, tol=1e-9)

    def test_no_ref_direction_defaults_to_identity(self):
        f = _make_file()
        loc = f.create_entity("IfcCartesianPoint", Coordinates=[5.0, 7.0])
        pos = f.create_entity("IfcAxis2Placement2D", Location=loc, RefDirection=None)
        pts = [(1.0, 2.0)]
        result = _apply_axis2placement2d(pts, pos)
        assert _approx(result[0][0], 6.0) and _approx(result[0][1], 9.0)


# ---------------------------------------------------------------------------
# Native profile type Position tests
# ---------------------------------------------------------------------------

class TestRectangleProfileDefPosition:
    def test_no_position(self):
        f = _make_file()
        prof = f.create_entity(
            "IfcRectangleProfileDef",
            ProfileType="AREA", XDim=4.0, YDim=2.0, Position=None
        )
        pts = _profile_def_to_pts(prof)
        assert len(pts) == 4
        cx, cy = _centroid(pts)
        assert _approx(cx, 0.0, tol=1e-9) and _approx(cy, 0.0, tol=1e-9)

    def test_translation_only(self):
        f = _make_file()
        pos = _make_placement(f, tx=10.0, ty=20.0)
        prof = f.create_entity(
            "IfcRectangleProfileDef",
            ProfileType="AREA", XDim=4.0, YDim=2.0, Position=pos
        )
        pts = _profile_def_to_pts(prof)
        cx, cy = _centroid(pts)
        assert _approx(cx, 10.0, tol=1e-9) and _approx(cy, 20.0, tol=1e-9)

    def test_rotation_90deg(self):
        f = _make_file()
        pos = _make_placement(f, tx=0.0, ty=0.0, angle_deg=90.0)
        prof = f.create_entity(
            "IfcRectangleProfileDef",
            ProfileType="AREA", XDim=4.0, YDim=2.0, Position=pos
        )
        pts = _profile_def_to_pts(prof)
        # After 90° rotation, X extent becomes Y extent and vice versa.
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x_span = max(xs) - min(xs)
        y_span = max(ys) - min(ys)
        # Original XDim=4 → after 90° rotation it is the Y span
        assert _approx(x_span, 2.0, tol=1e-9)
        assert _approx(y_span, 4.0, tol=1e-9)


class TestCircleProfileDefPosition:
    def test_translation(self):
        f = _make_file()
        pos = _make_placement(f, tx=5.0, ty=3.0)
        prof = f.create_entity(
            "IfcCircleProfileDef",
            ProfileType="AREA", Radius=1.0, Position=pos
        )
        pts = _profile_def_to_pts(prof, segments=16)
        cx, cy = _centroid(pts)
        assert _approx(cx, 5.0, tol=1e-6) and _approx(cy, 3.0, tol=1e-6)


class TestIShapeProfileDefPosition:
    def test_translation(self):
        f = _make_file()
        pos = _make_placement(f, tx=100.0, ty=50.0)
        prof = f.create_entity(
            "IfcIShapeProfileDef",
            ProfileType="AREA",
            OverallWidth=100.0,
            OverallDepth=200.0,
            WebThickness=10.0,
            FlangeThickness=15.0,
            Position=pos,
        )
        pts = _profile_def_to_pts(prof)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        # Centroid of an I-beam is at (0,0) before position → at (100, 50) after
        cx, cy = _centroid(pts)
        assert _approx(cx, 100.0, tol=1e-9) and _approx(cy, 50.0, tol=1e-9)


class TestLShapeProfileDefPosition:
    def test_translation(self):
        f = _make_file()
        pos = _make_placement(f, tx=3.0, ty=7.0)
        prof = f.create_entity(
            "IfcLShapeProfileDef",
            ProfileType="AREA",
            Depth=100.0, Width=80.0, Thickness=10.0,
            Position=pos,
        )
        pts = _profile_def_to_pts(prof)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        # Without position, X range starts at 0.  With tx=3 it starts at 3.
        assert _approx(min(xs), 3.0, tol=1e-9)
        assert _approx(min(ys), 7.0, tol=1e-9)


class TestTShapeProfileDefPosition:
    def test_translation(self):
        f = _make_file()
        pos = _make_placement(f, tx=1.0, ty=2.0)
        prof = f.create_entity(
            "IfcTShapeProfileDef",
            ProfileType="AREA",
            Depth=150.0, FlangeWidth=100.0, WebThickness=10.0, FlangeThickness=12.0,
            Position=pos,
        )
        pts = _profile_def_to_pts(prof)
        ys = [p[1] for p in pts]
        # Without position, Y starts at 0.  With ty=2 it starts at 2.
        assert _approx(min(ys), 2.0, tol=1e-9)


class TestZShapeProfileDefPosition:
    def test_translation(self):
        f = _make_file()
        pos = _make_placement(f, tx=5.0, ty=5.0)
        prof = f.create_entity(
            "IfcZShapeProfileDef",
            ProfileType="AREA",
            Depth=120.0, FlangeWidth=60.0, WebThickness=8.0, FlangeThickness=10.0,
            Position=pos,
        )
        pts = _profile_def_to_pts(prof)
        cx, cy = _centroid(pts)
        # Z-shape natural centroid is at (0,0) → after tx=5, ty=5 → (5,5)
        assert _approx(cx, 5.0, tol=1e-6) and _approx(cy, 5.0, tol=1e-6)


class TestCShapeProfileDefPosition:
    def test_translation(self):
        f = _make_file()
        pos = _make_placement(f, tx=10.0, ty=0.0)
        prof = f.create_entity(
            "IfcCShapeProfileDef",
            ProfileType="AREA",
            Depth=100.0, Width=60.0, WallThickness=8.0, Girth=0.0,
            Position=pos,
        )
        pts = _profile_def_to_pts(prof)
        xs = [p[0] for p in pts]
        # Without position, X starts at 0.  With tx=10 it starts at 10.
        assert _approx(min(xs), 10.0, tol=1e-9)


class TestTrapeziumProfileDefPosition:
    def test_translation(self):
        f = _make_file()
        pos = _make_placement(f, tx=0.0, ty=10.0)
        prof = f.create_entity(
            "IfcTrapeziumProfileDef",
            ProfileType="AREA",
            BottomXDim=100.0, TopXDim=60.0, YDim=80.0, TopXOffset=0.0,
            Position=pos,
        )
        pts = _profile_def_to_pts(prof)
        ys = [p[1] for p in pts]
        # Without position, Y starts at 0.  With ty=10 it starts at 10.
        assert _approx(min(ys), 10.0, tol=1e-9)
