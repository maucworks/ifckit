"""
Tests for affine transform system: Transform + mirror/copy/rotate/scale
on all geometry primitives.
"""

import math

import pytest

from ifckit.geometry import (
    Arc,
    Curve,
    Intersection,
    Line,
    Path,
    Plane,
    Surface,
    Transform,
    Vec,
)

# ===========================================================================
# Transform class
# ===========================================================================


class TestTransform:
    def test_identity(self):
        t = Transform.identity()
        v = Vec(1, 2, 3)
        assert t.apply(v) == v
        assert t.apply_vector(v) == v

    def test_translation(self):
        t = Transform.translation(Vec(10, 0, 5))
        assert t.apply(Vec(0, 0, 0)) == Vec(10, 0, 5)
        # direction (no translation)
        assert t.apply_vector(Vec(1, 0, 0)) == Vec(1, 0, 0)

    def test_rotation(self):
        r = Transform.rotation(Vec(0, 0, 1), math.pi / 2)
        v = r.apply(Vec(1, 0, 0))
        assert v.equals(Vec(0, 1, 0), 1e-9)

    def test_rotation_around_arbitrary_axis(self):
        r = Transform.rotation(Vec(1, 1, 0), math.pi)
        v = r.apply(Vec(0, 1, 0))
        assert v.equals(Vec(1, 0, 0), 1e-9)

    def test_uniform_scale(self):
        s = Transform.scaling(2, 2, 2)
        assert s.apply(Vec(1, 2, 3)) == Vec(2, 4, 6)

    def test_non_uniform_scale(self):
        s = Transform.scaling(2, 3, 4)
        assert s.apply(Vec(1, 1, 1)) == Vec(2, 3, 4)

    def test_reflection_over_xy_plane(self):
        plane = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        ref = Transform.reflection(plane)
        assert ref.apply(Vec(1, 2, 3)) == Vec(1, 2, -3)

    def test_reflection_over_offset_plane(self):
        plane = Plane(Vec(0, 0, 5), Vec(1, 0, 0), Vec(0, 1, 0))
        ref = Transform.reflection(plane)
        assert ref.apply(Vec(1, 2, 3)) == Vec(1, 2, 7)

    def test_reflection_over_yz_plane(self):
        p_yz = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        ref = Transform.reflection(p_yz)
        assert ref.apply(Vec(1, 2, 3)) == Vec(-1, 2, 3)

    def test_composition(self):
        t = Transform.translation(Vec(10, 0, 0)) @ Transform.rotation(
            Vec(0, 0, 1), math.pi / 2
        )
        v = t.apply(Vec(1, 0, 0))
        assert v.equals(Vec(10, 1, 0), 1e-9)

    def test_inverse(self):
        t = Transform.translation(Vec(10, 20, 30)) @ Transform.scaling(2, 3, 4)
        ti = t.inverse()
        v = Vec(1, 2, 3)
        assert (t @ ti).apply(v).equals(v, tol=1e-9)

    def test_inverse_reflection(self):
        plane = Plane(Vec(0, 0, 5), Vec(1, 0, 0), Vec(0, 1, 0))
        ref = Transform.reflection(plane)
        ri = ref.inverse()
        v = Vec(1, 2, 3)
        assert (ref @ ri).apply(v).equals(v, tol=1e-9)

    def test_is_uniform_scale(self):
        assert Transform.identity().is_uniform_scale()
        assert Transform.scaling(2, 2, 2).is_uniform_scale()
        assert not Transform.scaling(2, 3, 2).is_uniform_scale()
        r = Transform.rotation(Vec(0, 0, 1), 0.5)
        assert r.is_uniform_scale()

    def test_apply_vector_no_translation(self):
        plane = Plane(Vec(0, 0, 5), Vec(1, 0, 0), Vec(0, 1, 0))
        ref = Transform.reflection(plane)
        assert ref.apply_vector(Vec(0, 0, 1)) == Vec(0, 0, -1)


# ===========================================================================
# Vec
# ===========================================================================


class TestVecTransform:
    def test_mirrored(self):
        p_xy = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        v = Vec(1, 2, 3).mirrored(p_xy)
        assert v == Vec(1, 2, -3)

    def test_translated(self):
        v = Vec(1, 2, 3).translated(Vec(10, 0, 5))
        assert v == Vec(11, 2, 8)

    def test_rotated(self):
        v = Vec(1, 0, 0).rotated(Vec(0, 0, 1), math.pi / 2)
        assert v.equals(Vec(0, 1, 0), 1e-9)

    def test_scaled_uniform(self):
        v = Vec(1, 2, 3).scaled(2)
        assert v == Vec(2, 4, 6)

    def test_scaled_non_uniform(self):
        v = Vec(1, 2, 3).scaled(2, 3, 4)
        assert v == Vec(2, 6, 12)

    def test_copy(self):
        v = Vec(1, 2, 3)
        c = v.copy()
        assert c == v
        assert c is not v

    def test_transformed(self):
        t = Transform.translation(Vec(5, 0, 0))
        v = Vec(1, 2, 3).transformed(t)
        assert v == Vec(6, 2, 3)


# ===========================================================================
# Line
# ===========================================================================


class TestLineTransform:
    def test_mirrored(self):
        p_yz = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        line = Line(Vec(1, 2, 3), Vec(4, 5, 6)).mirrored(p_yz)
        assert line.start == Vec(-1, 2, 3)
        assert line.end == Vec(-4, 5, 6)

    def test_translated(self):
        line = Line(Vec(0, 0, 0), Vec(1, 0, 0)).translated(Vec(0, 10, 0))
        assert line.start == Vec(0, 10, 0)
        assert line.end == Vec(1, 10, 0)

    def test_rotated(self):
        line = Line(Vec(1, 0, 0), Vec(2, 0, 0)).rotated(Vec(0, 0, 1), math.pi / 2)
        assert line.start.equals(Vec(0, 1, 0), 1e-9)
        assert line.end.equals(Vec(0, 2, 0), 1e-9)

    def test_scaled(self):
        line = Line(Vec(0, 0, 0), Vec(1, 2, 3)).scaled(2)
        assert line.start == Vec(0, 0, 0)
        assert line.end == Vec(2, 4, 6)

    def test_copy(self):
        line = Line(Vec(0, 0, 0), Vec(1, 0, 0))
        c = line.copy()
        assert c.start == line.start and c.end == line.end
        assert c is not line

    def test_original_unchanged(self):
        line = Line(Vec(0, 0, 0), Vec(1, 0, 0))
        _ = line.mirrored(Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)))
        assert line.start == Vec(0, 0, 0)


# ===========================================================================
# Arc
# ===========================================================================


class TestArcTransform:
    def test_mirrored(self):
        p_yz = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        a = Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 1, 0), math.pi / 2)
        am = a.mirrored(p_yz)
        assert am.start == Vec(-1, 1, 0)
        assert am.center == Vec(0, 0, 0)
        assert abs(am.angle - math.pi / 2) < 1e-9

    def test_translated(self):
        a = Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 2)
        at = a.translated(Vec(0, 0, 10))
        assert at.center == Vec(0, 0, 10)
        assert at.start == Vec(1, 0, 10)

    def test_rotated(self):
        a = Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 2)
        ar = a.rotated(Vec(1, 0, 0), math.pi / 2)
        assert ar.center.equals(Vec(0, 0, 0), 1e-9)

    def test_non_uniform_scale_raises(self):
        a = Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 2)
        with pytest.raises(ValueError, match="non-uniform scale"):
            a.scaled(2, 3, 1)

    def test_uniform_scale_ok(self):
        a = Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 2)
        as_ = a.scaled(2)
        assert abs(as_.radius - 2.0) < 1e-9
        assert abs(as_.angle - math.pi / 2) < 1e-9

    def test_copy(self):
        a = Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 1, 0), math.pi / 2)
        c = a.copy()
        assert c.center == a.center
        assert c.normal == a.normal
        assert c.start == a.start
        assert c is not a


# ===========================================================================
# Plane
# ===========================================================================


class TestPlaneTransform:
    def test_mirrored(self):
        p_yz = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        p = Plane(Vec(1, 2, 3), Vec(1, 0, 0), Vec(0, 1, 0))
        pm = p.mirrored(p_yz)
        assert pm.origin == Vec(-1, 2, 3)
        assert pm.x_axis == Vec(-1, 0, 0)
        assert pm.y_axis == Vec(0, 1, 0)

    def test_translated(self):
        p = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        pt = p.translated(Vec(10, 0, 0))
        assert pt.origin == Vec(10, 0, 0)
        assert pt.x_axis == Vec(1, 0, 0)

    def test_rotated(self):
        p = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        pr = p.rotated(Vec(0, 0, 1), math.pi / 2)
        assert pr.x_axis.equals(Vec(0, 1, 0), 1e-9)

    def test_copy(self):
        p = Plane(Vec(1, 2, 3), Vec(1, 0, 0), Vec(0, 1, 0))
        c = p.copy()
        assert c.origin == p.origin
        assert c.x_axis == p.x_axis
        assert c is not p


# ===========================================================================
# Path
# ===========================================================================


class TestPathTransform:
    @pytest.fixture
    def rect(self):
        return Path.from_pts(
            [Vec(0, 0, 0), Vec(2, 0, 0), Vec(2, 1, 0), Vec(0, 1, 0)], closed=True
        )

    def test_mirrored(self, rect):
        p_yz = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        pm = rect.mirrored(p_yz)
        pts = [s.start for s in pm.segments]
        assert pts[0] == Vec(0, 0, 0)
        assert pts[1] == Vec(-2, 0, 0)

    def test_translated(self, rect):
        pt = rect.translated(Vec(10, 20, 0))
        assert pt.start_point().equals(Vec(10, 20, 0), 1e-9)

    def test_rotated(self, rect):
        pr = rect.rotated(Vec(0, 0, 1), math.pi / 2)
        assert pr.segments[0].start.equals(Vec(0, 0, 0), 1e-9)
        assert pr.segments[0].end.equals(Vec(0, 2, 0), 1e-9)

    def test_rotated_around_center(self, rect):
        ctr = Vec(1, 0.5, 0)
        pr = rect.rotated(Vec(0, 0, 1), math.pi, center=ctr)
        # after 180° around center, rectangle should be opposite
        assert pr.segments[0].start.equals(Vec(2, 1, 0), 1e-9)

    def test_scaled(self, rect):
        ps = rect.scaled(2)
        assert ps.segments[0].end == Vec(4, 0, 0)

    def test_scaled_around_center(self, rect):
        ctr = Vec(1, 0.5, 0)
        ps = rect.scaled(2, center=ctr)
        assert ps.segments[0].start.equals(Vec(-1, -0.5, 0), 1e-9)

    def test_copy(self, rect):
        c = rect.copy()
        assert c.start_point() == rect.start_point()
        assert c is not rect

    def test_original_unchanged(self, rect):
        rect.mirrored(Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)))
        assert rect.segments[0].start == Vec(0, 0, 0)

    def test_non_uniform_scale_with_arc(self):
        path = Path(plane=Plane.world_xy())
        path._segments = [
            Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 2),
            Line(Vec(0, 1, 0), Vec(0, 0, 0)),
        ]
        # Should succeed — arcs sampled to polylines
        ps = path.scaled(2, 3, 1)
        assert len(ps._segments) > 2  # arc was sampled


# ===========================================================================
# Curve (NURBS)
# ===========================================================================


class TestCurveTransform:
    @pytest.fixture
    def curve(self):
        return Curve(
            control_points=[Vec(0, 0, 0), Vec(1, 0, 0), Vec(2, 0, 0)],
            knots=[0, 0, 0, 1, 1, 1],
            multiplicities=[3, 3],
            degree=2,
        )

    def test_transformed(self, curve):
        t = Transform.translation(Vec(10, 0, 0))
        ct = curve.transformed(t)
        assert ct.points[0] == Vec(10, 0, 0)
        assert ct.points[1] == Vec(11, 0, 0)
        assert ct.knots == curve.knots  # knots unchanged
        assert ct.degree == curve.degree

    def test_mirrored(self, curve):
        p_yz = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        cm = curve.mirrored(p_yz)
        assert cm.points[0] == Vec(0, 0, 0)
        assert cm.points[1] == Vec(-1, 0, 0)

    def test_translated(self, curve):
        ct = curve.translated(Vec(0, 5, 0))
        assert ct.points[0] == Vec(0, 5, 0)

    def test_rotated(self, curve):
        cr = curve.rotated(Vec(0, 0, 1), math.pi / 2)
        assert cr.points[0].equals(Vec(0, 0, 0), 1e-9)
        assert cr.points[1].equals(Vec(0, 1, 0), 1e-9)

    def test_scaled(self, curve):
        cs = curve.scaled(2)
        assert cs.points[1] == Vec(2, 0, 0)

    def test_copy(self, curve):
        c = curve.copy()
        assert c.points == curve.points
        assert c is not curve

    def test_reverse_preserved(self, curve):
        """reverse() is separate from transforms, verify it still works."""
        cr = curve.reverse()
        assert cr.points[0] == Vec(2, 0, 0)

    def test_rational_curve(self):
        """Weighted NURBS curve with rational weights."""
        c = Curve(
            control_points=[Vec(0, 0, 0), Vec(1, 1, 0), Vec(2, 0, 0)],
            knots=[0, 0, 0, 1, 1, 1],
            multiplicities=[3, 3],
            degree=2,
            weights=[1.0, 2.0, 1.0],
        )
        assert c._weights == [1.0, 2.0, 1.0]
        ct = c.translated(Vec(10, 0, 0))
        assert ct.points[0] == Vec(10, 0, 0)
        assert ct._weights == [1.0, 2.0, 1.0]  # weights preserved


# ===========================================================================
# Surface (NURBS)
# ===========================================================================


class TestSurfaceTransform:
    @pytest.fixture
    def surface(self):
        return Surface(
            control_points=[[Vec(0, 0, 0), Vec(1, 0, 0)], [Vec(0, 1, 0), Vec(1, 1, 0)]],
            uknots=[0, 0, 1, 1],
            vknots=[0, 0, 1, 1],
            umults=[2, 2],
            vmults=[2, 2],
            udegree=1,
            vdegree=1,
        )

    def test_transformed(self, surface):
        t = Transform.translation(Vec(10, 0, 0))
        st = surface.transformed(t)
        assert st.control_points[0][0] == Vec(10, 0, 0)
        assert st.control_points[1][0] == Vec(10, 1, 0)

    def test_mirrored(self, surface):
        p_yz = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        sm = surface.mirrored(p_yz)
        assert sm.control_points[0][0] == Vec(0, 0, 0)
        assert sm.control_points[0][1] == Vec(-1, 0, 0)

    def test_translated(self, surface):
        st = surface.translated(Vec(0, 5, 0))
        assert st.control_points[0][0] == Vec(0, 5, 0)

    def test_rotated(self, surface):
        sr = surface.rotated(Vec(0, 0, 1), math.pi / 2)
        assert sr.control_points[0][0].equals(Vec(0, 0, 0), 1e-9)
        assert sr.control_points[0][1].equals(Vec(0, 1, 0), 1e-9)

    def test_copy(self, surface):
        c = surface.copy()
        assert c.control_points == surface.control_points
        assert c is not surface

    def test_uknots_preserved(self, surface):
        st = surface.translated(Vec(5, 0, 0))
        assert st.uknots == surface.uknots
        assert st.vknots == surface.vknots


# ===========================================================================
# Intersection
# ===========================================================================


class TestIntersectionTransform:
    def test_transformed(self):
        c = Curve(
            control_points=[Vec(0, 0, 0), Vec(1, 0, 0)],
            knots=[0, 0, 1, 1],
            multiplicities=[2, 2],
            degree=1,
        )
        ix = Intersection(curves=[c], points=[Vec(1, 2, 3)])
        t = Transform.translation(Vec(10, 0, 0))
        ixt = ix.transformed(t)
        assert ixt.points[0] == Vec(11, 2, 3)
        assert ixt.curves[0].points[0] == Vec(10, 0, 0)

    def test_empty(self):
        ix = Intersection()
        ixt = ix.translated(Vec(10, 0, 0))
        assert len(ixt.curves) == 0
        assert len(ixt.points) == 0

    def test_mirrored(self):
        p_yz = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        ix = Intersection(points=[Vec(1, 2, 3)])
        ixm = ix.mirrored(p_yz)
        assert ixm.points[0] == Vec(-1, 2, 3)


# ===========================================================================
# Profile inherits Path transforms
# ===========================================================================


class TestProfileTransform:
    def test_mirrored_via_path(self):
        """Profile inherits Path.transformed() — verify it works."""
        from ifckit.profiles import RectangleProfile
        r = RectangleProfile(100, 50)
        p_yz = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        rm = r.mirrored(p_yz)
        from ifckit.geometry import Path
        assert isinstance(rm, Path)
        # geometry should be mirrored
        pts = [s.start for s in rm.segments]
        # original had pts with x centered: [-50, -50] → [50, -50] → [50, 50] → [-50, 50]
        # mirrored: [50, -50] → [-50, -50] → [-50, 50] → [50, 50]
        assert pts[0].x > 0  # after YZ mirror, the left side becomes right


# ===========================================================================
# Edge cases
# ===========================================================================


class TestTransformEdgeCases:
    def test_zero_vector_rotation(self):
        v = Vec(0, 0, 0).rotated(Vec(0, 0, 1), math.pi)
        assert v == Vec(0, 0, 0)

    def test_mirror_point_on_plane(self):
        plane = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        v = Vec(0, 0, 0).mirrored(plane)
        assert v == Vec(0, 0, 0)

    def test_scale_zero(self):
        v = Vec(1, 2, 3).scaled(0)
        assert v == Vec(0, 0, 0)

    def test_negative_scale(self):
        v = Vec(1, 2, 3).scaled(-1)
        assert v == Vec(-1, -2, -3)

    def test_identity_transform_chain(self):
        p = Path.from_pts([Vec(0, 0, 0), Vec(1, 0, 0)])
        same = p.transformed(Transform.identity())
        assert same.start_point() == Vec(0, 0, 0)


# ===========================================================================
# Chaining
# ===========================================================================


class TestTransformChaining:
    def test_translate_then_mirror(self):
        p = Path.from_pts([Vec(0, 0, 0), Vec(1, 0, 0)])
        p_yz = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        result = p.translated(Vec(0, 10, 0)).mirrored(p_yz)
        assert result.start_point().equals(Vec(0, 10, 0), 1e-9)
        assert result.end_point().equals(Vec(-1, 10, 0), 1e-9)

    def test_mirror_then_rotate(self):
        # mirror over YZ plane: (1,0,0) → (-1,0,0)
        # then rotate 90° CCW around Z: (-1,0,0) → (0,-1,0)
        p = Path.from_pts([Vec(1, 0, 0), Vec(2, 0, 0)])
        p_yz = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        result = p.mirrored(p_yz).rotated(Vec(0, 0, 1), math.pi / 2)
        assert result.start_point().equals(Vec(0, -1, 0), 1e-9)
        assert result.end_point().equals(Vec(0, -2, 0), 1e-9)

    def test_translate_rotate_scale(self):
        rect = Path.from_pts(
            [Vec(0, 0, 0), Vec(2, 0, 0), Vec(2, 1, 0), Vec(0, 1, 0)], closed=True
        )
        result = rect.translated(Vec(5, 0, 0)).rotated(
            Vec(0, 0, 1), math.pi / 2
        ).scaled(2)
        # translate (5,0): (5,0,0) → rotate 90° CCW: (0,5,0) → scale 2: (0,10,0)
        assert result.segments[0].start.equals(Vec(0, 10, 0), 1e-8)
        assert result.segments[0].end.equals(Vec(0, 14, 0), 1e-8)

    def test_curve_chain(self):
        c = Curve(
            control_points=[Vec(0, 0, 0), Vec(1, 0, 0), Vec(2, 0, 0)],
            knots=[0, 0, 0, 1, 1, 1],
            multiplicities=[3, 3],
            degree=2,
        )
        # translate then scale (not scale then translate)
        result = c.translated(Vec(10, 0, 0)).scaled(2, 3, 4)
        assert result.points[0] == Vec(20, 0, 0)
        assert result.points[1] == Vec(22, 0, 0)

    def test_vec_chain(self):
        v = Vec(1, 2, 3)
        result = v.translated(Vec(10, 0, 0)).scaled(2).mirrored(
            Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        )
        assert result == Vec(22, 4, -6)


# ===========================================================================
# Arc rotated endpoint
# ===========================================================================


class TestArcRotatedEndpoint:
    def test_rotated_90_around_z(self):
        a = Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 2)
        ar = a.rotated(Vec(0, 0, 1), math.pi / 2)
        # entire arc shifted 90° CCW: start (1,0,0) → (0,1,0), end (0,1,0) → (-1,0,0)
        assert ar.start.equals(Vec(0, 1, 0), 1e-9), f'start={ar.start}'
        assert ar.end.equals(Vec(-1, 0, 0), 1e-9), f'end={ar.end}'
        assert ar.center.equals(Vec(0, 0, 0), 1e-9)
        assert abs(ar.angle - math.pi / 2) < 1e-9

    def test_rotated_180(self):
        a = Arc(Vec(1, 0, 0), Vec(0, 0, 1), Vec(2, 0, 0), math.pi / 2)
        ar = a.rotated(Vec(0, 0, 1), math.pi)
        assert ar.start.equals(Vec(-2, 0, 0), 1e-9), f'start={ar.start}'
        assert ar.center.equals(Vec(-1, 0, 0), 1e-9), f'center={ar.center}'
        assert abs(ar.angle - math.pi / 2) < 1e-9


# ===========================================================================
# Path with holes
# ===========================================================================


class TestPathHolesTransform:
    def test_mirrored_holes(self):
        outer = Path.from_pts(
            [Vec(0, 0, 0), Vec(10, 0, 0), Vec(10, 10, 0), Vec(0, 10, 0)], closed=True
        )
        inner = Path.from_pts(
            [Vec(3, 3, 0), Vec(7, 3, 0), Vec(7, 7, 0), Vec(3, 7, 0)], closed=True
        )
        path_with_hole = outer.with_hole(inner)
        p_yz = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        mirrored = path_with_hole.mirrored(p_yz)
        # holes should be mirrored too
        assert len(mirrored.holes) == 1
        hole_pts = [s.start for s in mirrored.holes[0].segments]
        assert hole_pts[0] == Vec(-3, 3, 0), f'{hole_pts[0]}'

    def test_translated_holes(self):
        outer = Path.from_pts(
            [Vec(0, 0, 0), Vec(10, 0, 0), Vec(10, 10, 0), Vec(0, 10, 0)], closed=True
        )
        inner = Path.from_pts(
            [Vec(3, 3, 0), Vec(7, 3, 0), Vec(7, 7, 0), Vec(3, 7, 0)], closed=True
        )
        path_with_hole = outer.with_hole(inner)
        translated = path_with_hole.translated(Vec(5, 0, 0))
        assert len(translated.holes) == 1
        assert translated.holes[0].segments[0].start == Vec(8, 3, 0)

    def test_holes_original_unchanged(self):
        outer = Path.from_pts(
            [Vec(0, 0, 0), Vec(10, 0, 0), Vec(10, 10, 0), Vec(0, 10, 0)], closed=True
        )
        inner = Path.from_pts(
            [Vec(3, 3, 0), Vec(7, 3, 0), Vec(7, 7, 0), Vec(3, 7, 0)], closed=True
        )
        path_with_hole = outer.with_hole(inner)
        path_with_hole.translated(Vec(5, 0, 0))
        assert path_with_hole.holes[0].segments[0].start == Vec(3, 3, 0)
