"""Tests for ifckit.rhinokit — curve, path, and surface conversion."""

import sys
from unittest import mock

import pytest

import ifckit.rhinokit as rk
from ifckit.geometry import Arc, Curve, Line, Path, Surface, Vec

# ---------------------------------------------------------------------------
# Mock Rhino objects for testing conversion functions
# ---------------------------------------------------------------------------


class _Point:
    """Fake Rhino Point3d."""

    def __init__(self, x, y, z):
        self.X, self.Y, self.Z = x, y, z


class _ControlPoint:
    """Fake Rhino ControlPoint."""

    def __init__(self, loc, weight=1.0):
        self.Location = loc
        self.Weight = weight


class FakeNurbsCurve:
    """Minimal mock of Rhino.Geometry.NurbsCurve (read‑only)."""

    def __init__(self, degree, points, knots, is_closed=False, is_rational=False, weights=None):
        self.Degree = degree
        self.IsRational = is_rational
        self.IsClosed = is_closed

        pts = []
        for i, p in enumerate(points):
            w = weights[i] if weights else 1.0
            pts.append(_ControlPoint(p, w))
        self._pts = pts

        self._knots_list = list(knots)

        class _Pts:
            Count = len(pts)

            def __getitem__(s, i):
                return self._pts[i]

        self.Points = _Pts()

        class _Knots:
            Count = len(knots)

            def __getitem__(s, i):
                return self._knots_list[i]

        self.Knots = _Knots()


class FakeNurbsSurface:
    """Mock Rhino NurbsSurface — works in both read and write modes.

    Read mode: directly constructed with all data (for rhino_brep_to_surface).
    Write mode: constructed via ``Create()`` classmethod (for surface_to_rhino).
    """

    def __init__(
        self,
        udeg=0,
        vdeg=0,
        points_2d=None,
        uknots=None,
        vknots=None,
        is_rational=False,
        weights_2d=None,
        is_u_closed=False,
        is_v_closed=False,
    ):
        self._udeg = udeg
        self._vdeg = vdeg
        self.IsRational = is_rational
        self._points_2d = points_2d or []
        self._weights_2d = weights_2d
        self._uknots_read = list(uknots or [])
        self._vknots_read = list(vknots or [])
        self._uclosed = is_u_closed
        self._vclosed = is_v_closed

        self.init_kwargs: dict = {}
        self._set_point_calls: list = []
        self.u_knot_values: dict = {}
        self.v_knot_values: dict = {}

    @classmethod
    def Create(
        cls,
        dimension=None,
        isRational=False,
        uOrder=2,
        vOrder=2,
        uControlPointCount=1,
        vControlPointCount=1,
    ):
        inst = cls(udeg=uOrder - 1, vdeg=vOrder - 1)
        inst.init_kwargs = dict(
            dimension=dimension,
            isRational=isRational,
            uOrder=uOrder,
            vOrder=vOrder,
            uControlPointCount=uControlPointCount,
            vControlPointCount=vControlPointCount,
        )
        return inst

    def Degree(self, d):
        return self._udeg if d == 0 else self._vdeg

    def IsClosed(self, d):
        return self._uclosed if d == 0 else self._vclosed

    class _Points:
        def __init__(self, p):
            self._p = p

        @property
        def CountU(self):
            return len(self._p._points_2d) if self._p._points_2d else 0

        @property
        def CountV(self):
            return len(self._p._points_2d[0]) if self._p._points_2d and self._p._points_2d[0] else 0

        def GetControlPoint(self, i, j):
            loc = self._p._points_2d[i][j]
            w = self._p._weights_2d[i][j] if self._p._weights_2d else 1.0
            return _ControlPoint(loc, w)

        def SetPoint(self, i, j, *args):
            self._p._set_point_calls.append((i, j) + args)

    class _Knots:
        def __init__(self, p, direction):
            self._p = p
            self._d = direction

        @property
        def Count(self):
            return len(self._p._uknots_read) if self._d == "u" else len(self._p._vknots_read)

        def __getitem__(self, i):
            return self._p._uknots_read[i] if self._d == "u" else self._p._vknots_read[i]

        def __setitem__(self, i, value):
            if self._d == "u":
                self._p.u_knot_values[i] = value
            else:
                self._p.v_knot_values[i] = value

    @property
    def Points(self):
        return FakeNurbsSurface._Points(self)

    @property
    def KnotsU(self):
        return FakeNurbsSurface._Knots(self, "u")

    @property
    def KnotsV(self):
        return FakeNurbsSurface._Knots(self, "v")


class FakeBrep:
    """Minimal mock of Rhino.Geometry.Brep wrapping a single NurbsSurface."""

    def __init__(self, ns):
        self._ns = ns

    class _Face:
        def __init__(self, underlying):
            self._underlying = underlying

        def UnderlyingSurface(self):
            return self._underlying

    class _Faces:
        def __init__(self, face):
            self._face = face

        @property
        def Count(self):
            return 1

        def __getitem__(self, i):
            return self._face

    @property
    def Faces(self):
        return FakeBrep._Faces(FakeBrep._Face(self._ns))


# ---------------------------------------------------------------------------
# Mock for curve_to_rhino_nurbs — intercepts the Rhino constructor
# ---------------------------------------------------------------------------


class _CapturingNurbsCurve:
    """A NurbsCurve‑like that records all Points.SetPoint / Knots[i] calls."""

    def __init__(self, dimension=None, isRational=False, order=4, pointCount=0):
        self.init_args = (dimension, isRational, order, pointCount)
        self._set_point_calls = []  # [(i, args...)]
        self.knot_values = {}  # {i: value}

    class _Points:
        def __init__(self, owner):
            self._o = owner

        def SetPoint(self, i, *args):
            self._o._set_point_calls.append((i,) + args)

    @property
    def Points(self):
        return _CapturingNurbsCurve._Points(self)

    class _Knots:
        def __init__(self, owner):
            self._o = owner

        def __setitem__(self, i, value):
            self._o.knot_values[i] = value

    @property
    def Knots(self):
        return _CapturingNurbsCurve._Knots(self)


# ---------------------------------------------------------------------------
# Helpers for building test data
# ---------------------------------------------------------------------------


def _cubic_bezier():
    """Standard cubic Bezier: 4 CPs, degree 3, clamped knots [0,0,0,0,1,1,1,1]."""
    return Curve(
        control_points=[
            Vec(0, 0, 0),
            Vec(1, 2, 0),
            Vec(3, 2, 0),
            Vec(4, 0, 0),
        ],
        knots=[0.0, 1.0],
        multiplicities=[4, 4],
        degree=3,
    )


def _quadratic_curve():
    """Quadratic BSpline: 3 CPs, degree 2, clamped knots [0,0,0,1,1,1]."""
    return Curve(
        control_points=[
            Vec(0, 0, 0),
            Vec(2, 3, 0),
            Vec(4, 0, 0),
        ],
        knots=[0.0, 1.0],
        multiplicities=[3, 3],
        degree=2,
    )


def _rational_curve():
    """Rational quadratic: 3 CPs with weights."""
    return Curve(
        control_points=[
            Vec(0, 0, 0),
            Vec(2, 2, 0),
            Vec(4, 0, 0),
        ],
        knots=[0.0, 1.0],
        multiplicities=[3, 3],
        degree=2,
        weights=[1.0, 0.5, 1.0],
    )


def _test_surface():
    """2×2 bilinear surface (plane)."""
    return Surface(
        control_points=[
            [Vec(0, 0, 0), Vec(0, 5, 0)],
            [Vec(5, 0, 0), Vec(5, 5, 0)],
        ],
        uknots=[0.0, 1.0],
        vknots=[0.0, 1.0],
        umults=[2, 2],
        vmults=[2, 2],
        udegree=1,
        vdegree=1,
    )


# ===================================================================
# Knot helpers (pure Python — no Rhino needed)
# ===================================================================


class TestExpandKnots:
    def test_cubic_bezier(self):
        result = list(rk._expand_knots([0.0, 1.0], [4, 4]))
        assert result == [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0]

    def test_multiple_interior(self):
        result = list(rk._expand_knots([0.0, 0.5, 1.0], [3, 2, 3]))
        assert result == [0.0, 0.0, 0.0, 0.5, 0.5, 1.0, 1.0, 1.0]

    def test_quadratic(self):
        result = list(rk._expand_knots([0.0, 1.0], [3, 3]))
        assert result == [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]


class TestCompactKnots:
    def test_cubic_bezier(self):
        u, m = rk._compact_knots([0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0])
        assert u == [0.0, 1.0]
        assert m == [4, 4]

    def test_interior_knots(self):
        u, m = rk._compact_knots([0.0, 0.0, 0.0, 0.5, 0.5, 1.0, 1.0, 1.0])
        assert u == [0.0, 0.5, 1.0]
        assert m == [3, 2, 3]

    def test_empty(self):
        u, m = rk._compact_knots([])
        assert u == []
        assert m == []

    def test_roundtrip_cubic(self):
        orig_knots, orig_mults = [0.0, 0.25, 0.5, 0.75, 1.0], [1, 1, 1, 1, 1]
        expanded = list(rk._expand_knots(orig_knots, orig_mults))
        u, m = rk._compact_knots(expanded)
        assert u == orig_knots
        assert m == orig_mults


# ===================================================================
# rhino_nurbs_to_curve
# ===================================================================


@pytest.fixture(autouse=True)
def _patch_rhino_available(monkeypatch):
    """Make _RHINO_AVAILABLE True for all rhino‑dependent tests."""
    monkeypatch.setattr(rk, "_RHINO_AVAILABLE", True)


@pytest.fixture(autouse=True)
def _patch_rhino_module(monkeypatch):
    """Make _RHINO_AVAILABLE True and provide mock Rhino / Rhino.Geometry."""
    monkeypatch.setattr(rk, "_RHINO_AVAILABLE", True)
    fake_geom = mock.MagicMock(name="Rhino.Geometry")
    fake_geom.NurbsCurve = FakeNurbsCurve
    fake_geom.NurbsSurface = FakeNurbsSurface
    fake_rhino = mock.MagicMock(name="Rhino", Geometry=fake_geom)
    monkeypatch.setattr(rk, "Rhino", fake_rhino, raising=False)
    # Also inject into sys.modules for local `import Rhino.Geometry` statements
    monkeypatch.setitem(sys.modules, "Rhino", fake_rhino)
    monkeypatch.setitem(sys.modules, "Rhino.Geometry", fake_geom)


class TestRhinoNurbsToCurve:
    def test_cubic_clamped(self):
        pts = [_Point(0, 0, 0), _Point(1, 3, 0), _Point(3, 3, 0), _Point(4, 0, 0)]
        rhino_knots = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]  # n+d-1 = 4+3-1 = 6
        fake = FakeNurbsCurve(degree=3, points=pts, knots=rhino_knots)

        c = rk.rhino_nurbs_to_curve(fake)
        assert c.degree == 3
        assert not c.rational
        assert not c.closed
        assert len(c.points) == 4
        assert c.knots == [0.0, 1.0]
        assert c.multiplicities == [4, 4]

    def test_quadratic_rational(self):
        pts = [_Point(0, 0, 0), _Point(2, 2, 0), _Point(4, 0, 0)]
        rhino_knots = [0.0, 0.0, 1.0, 1.0]  # n+d-1 = 3+2-1 = 4
        fake = FakeNurbsCurve(
            degree=2, points=pts, knots=rhino_knots, is_rational=True, weights=[1.0, 0.5, 1.0]
        )

        c = rk.rhino_nurbs_to_curve(fake)
        assert c.rational
        assert c._weights == [1.0, 0.5, 1.0]
        assert c.knots == [0.0, 1.0]
        assert c.multiplicities == [3, 3]

    def test_closed_flag(self):
        pts = [_Point(0, 0, 0), _Point(2, 2, 0), _Point(4, 0, 0), _Point(0, 0, 0)]
        rhino_knots = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
        fake = FakeNurbsCurve(degree=3, points=pts, knots=rhino_knots, is_closed=True)

        c = rk.rhino_nurbs_to_curve(fake)
        assert c.closed


# ===================================================================
# curve_to_rhino_nurbs
# ===================================================================


class TestCurveToRhinoNurbs:
    def test_cubic_bezier_constructor_args(self, monkeypatch):
        curve = _cubic_bezier()
        captured = _CapturingNurbsCurve()

        class MockNC:
            def __new__(cls, *args, **kwargs):
                captured.__init__(*args, **kwargs)
                return captured

        monkeypatch.setattr(rk.Rhino.Geometry, "NurbsCurve", MockNC)

        rk.curve_to_rhino_nurbs(curve)
        dim, rat, order, pt_count = captured.init_args
        assert dim == 3
        assert not rat
        assert order == 4  # degree + 1
        assert pt_count == 4

    def test_knot_stripping(self, monkeypatch):
        """Rhino convention: strip first and last knot from full expanded vector."""
        curve = _cubic_bezier()
        captured = _CapturingNurbsCurve()

        class MockNC:
            def __new__(cls, *args, **kwargs):
                captured.__init__(*args, **kwargs)
                return captured

        monkeypatch.setattr(rk.Rhino.Geometry, "NurbsCurve", MockNC)

        rk.curve_to_rhino_nurbs(curve)
        knots = [captured.knot_values[i] for i in sorted(captured.knot_values)]
        # Full: [0,0,0,0,1,1,1,1] → Rhino: [0,0,0,1,1,1]
        assert knots == [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
        assert len(knots) == 6  # n + d - 1 = 4 + 3 - 1

    def test_control_points_written(self, monkeypatch):
        curve = _cubic_bezier()
        captured = _CapturingNurbsCurve()

        class MockNC:
            def __new__(cls, *args, **kwargs):
                captured.__init__(*args, **kwargs)
                return captured

        monkeypatch.setattr(rk.Rhino.Geometry, "NurbsCurve", MockNC)

        rk.curve_to_rhino_nurbs(curve)
        assert len(captured._set_point_calls) == 4
        for i, x, y, z in captured._set_point_calls:
            assert curve.points[i].x == pytest.approx(x)
            assert curve.points[i].y == pytest.approx(y)
            assert curve.points[i].z == pytest.approx(z)

    def test_rational_homogeneous_points(self, monkeypatch):
        curve = _rational_curve()
        captured = _CapturingNurbsCurve()

        class MockNC:
            def __new__(cls, *args, **kwargs):
                captured.__init__(*args, **kwargs)
                return captured

        monkeypatch.setattr(rk.Rhino.Geometry, "NurbsCurve", MockNC)

        rk.curve_to_rhino_nurbs(curve)
        # Rational: SetPoint receives (i, wx, wy, wz, w)
        assert len(captured._set_point_calls) == 3
        for i, wx, wy, wz, w in captured._set_point_calls:
            assert w == pytest.approx(curve._weights[i])
            assert wx / w == pytest.approx(curve.points[i].x)
            assert wy / w == pytest.approx(curve.points[i].y)
            assert wz / w == pytest.approx(curve.points[i].z)


# ===================================================================
# Round‑trip: ifckit Curve → (mock) Rhino NurbsCurve → ifckit Curve
# ===================================================================


class TestCurveRoundtrip:
    """Test that serialising to Rhino and back preserves the knot vector."""

    @staticmethod
    def _simulate_roundtrip(curve):
        """Manually simulate the knot transform without needing Rhino runtime."""
        full = list(rk._expand_knots(curve.knots, curve.multiplicities))
        rhino_knots = full[1:-1]
        expanded_back = [rhino_knots[0]] + rhino_knots + [rhino_knots[-1]]
        u, m = rk._compact_knots(expanded_back)
        return u, m

    def test_cubic_roundtrip(self):
        curve = _cubic_bezier()
        u, m = self._simulate_roundtrip(curve)
        assert u == curve.knots
        assert m == curve.multiplicities

    def test_with_interior_knot(self):
        curve = Curve(
            control_points=[Vec(0, 0, 0), Vec(1, 1, 0), Vec(2, 1, 0), Vec(3, 0, 0), Vec(4, 0, 0)],
            knots=[0.0, 0.5, 1.0],
            multiplicities=[4, 1, 4],
            degree=3,
        )
        u, m = self._simulate_roundtrip(curve)
        assert u == [0.0, 0.5, 1.0]
        assert m == [4, 1, 4]

    def test_degree_1_polyline(self):
        curve = Curve(
            control_points=[Vec(0, 0, 0), Vec(2, 0, 0), Vec(4, 2, 0)],
            knots=[0.0, 0.5, 1.0],
            multiplicities=[2, 1, 2],
            degree=1,
        )
        u, m = self._simulate_roundtrip(curve)
        assert u == [0.0, 0.5, 1.0]
        assert m == [2, 1, 2]


# ===================================================================
# rhino_brep_to_surface
# ===================================================================


class TestRhinoBrepToSurface:
    def test_planar_surface(self):
        pts = [
            [_Point(0, 0, 0), _Point(0, 10, 0)],
            [_Point(10, 0, 0), _Point(10, 10, 0)],
        ]
        rhino_uk = [0.0, 1.0]  # n+d-1 = 2+1-1 = 2
        rhino_vk = [0.0, 1.0]  # n+d-1 = 2+1-1 = 2
        ns = FakeNurbsSurface(udeg=1, vdeg=1, points_2d=pts, uknots=rhino_uk, vknots=rhino_vk)
        brep = FakeBrep(ns)

        surf = rk.rhino_brep_to_surface(brep)
        assert surf.udegree == 1
        assert surf.vdegree == 1
        assert surf.nu == 2
        assert surf.nv == 2
        assert not surf.rational

    def test_knot_expansion(self):
        """Verify Rhino n+d-1 knots → standard n+d+1."""
        pts = [[_Point(i, j, 0) for j in range(3)] for i in range(3)]
        rhino_uk = [0.0, 0.0, 1.0, 1.0]  # 3+2-1 = 4
        rhino_vk = [0.0, 0.0, 1.0, 1.0]
        ns = FakeNurbsSurface(udeg=2, vdeg=2, points_2d=pts, uknots=rhino_uk, vknots=rhino_vk)
        brep = FakeBrep(ns)

        surf = rk.rhino_brep_to_surface(brep)
        # After expansion: compact should have 3 clamp mults
        assert surf.uknots == [0.0, 1.0]
        assert surf.umults == [3, 3]
        assert surf.vknots == [0.0, 1.0]
        assert surf.vmults == [3, 3]

    def test_none_brep_raises(self):
        with pytest.raises(ValueError, match="rh_brep is None"):
            rk.rhino_brep_to_surface(None)

    def test_closed_surface_flags(self):
        pts = [[_Point(i, j, 0) for j in range(3)] for i in range(3)]
        rhino_knots = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
        ns = FakeNurbsSurface(
            udeg=2,
            vdeg=2,
            points_2d=pts,
            uknots=rhino_knots,
            vknots=rhino_knots,
            is_u_closed=True,
            is_v_closed=True,
        )
        brep = FakeBrep(ns)

        surf = rk.rhino_brep_to_surface(brep)
        assert surf.uclosed
        assert surf.vclosed


# ===================================================================
# surface_to_rhino
# ===================================================================


class TestSurfaceToRhino:
    def test_bilinear_constructor_args(self):
        surf = _test_surface()
        result = rk.surface_to_rhino(surf)
        kw = result.init_kwargs
        assert kw["dimension"] == 3
        assert not kw["isRational"]
        assert kw["uOrder"] == 2  # udegree + 1
        assert kw["vOrder"] == 2  # vdegree + 1
        assert kw["uControlPointCount"] == 2
        assert kw["vControlPointCount"] == 2

    def test_knot_stripping(self):
        surf = _test_surface()
        result = rk.surface_to_rhino(surf)
        u_vals = [result.u_knot_values[i] for i in sorted(result.u_knot_values)]
        v_vals = [result.v_knot_values[i] for i in sorted(result.v_knot_values)]
        assert u_vals == [0.0, 1.0]
        assert v_vals == [0.0, 1.0]

    def test_control_points_written(self):
        surf = _test_surface()
        result = rk.surface_to_rhino(surf)
        assert len(result._set_point_calls) == 4  # 2×2 grid
        for i, j, x, y, z in result._set_point_calls:
            assert surf.control_points[i][j].x == pytest.approx(x)
            assert surf.control_points[i][j].y == pytest.approx(y)
            assert surf.control_points[i][j].z == pytest.approx(z)


# ===================================================================
# curves_to_path — NURBS detection
# ===================================================================


class TestCurvesToPath:
    def test_none_returns_empty_path(self):
        p = rk.curves_to_path(None)
        assert isinstance(p, Path)
        assert len(p.segments) == 0

    def test_rhino_nurbs_auto_biarc(self, monkeypatch):
        """A NurbsCurve input should be converted via biarc fitting."""
        curve = _cubic_bezier()

        rhino_knots = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
        pts = [_Point(p.x, p.y, p.z) for p in curve.points]
        fake_nurbs = FakeNurbsCurve(degree=3, points=pts, knots=rhino_knots)

        monkeypatch.setattr(rk.Rhino.Geometry, "NurbsCurve", FakeNurbsCurve)

        p = rk.curves_to_path(fake_nurbs)
        assert isinstance(p, Path)
        assert len(p.segments) > 0

    def test_polycurve_with_nurbs_segment(self, monkeypatch):
        """PolyCurve exploded → NURBS segment → biarc handling."""
        curve = _cubic_bezier()
        rhino_knots = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
        pts = [_Point(p.x, p.y, p.z) for p in curve.points]
        fake_nurbs = FakeNurbsCurve(degree=3, points=pts, knots=rhino_knots)

        monkeypatch.setattr(rk.Rhino.Geometry, "NurbsCurve", FakeNurbsCurve)

        path = rk.curves_to_path(fake_nurbs)
        assert len(path.segments) > 0
        for seg in path.segments:
            assert isinstance(seg, (Line, Arc))


# ===================================================================
# Surface knot convention round‑trip
# ===================================================================


class TestSurfaceKnotRoundtrip:
    def test_bilinear_roundtrip(self):
        surf = _test_surface()
        full_u = list(rk._expand_knots(surf.uknots, surf.umults))
        full_v = list(rk._expand_knots(surf.vknots, surf.vmults))
        rhino_u = full_u[1:-1]
        rhino_v = full_v[1:-1]
        back_u = [rhino_u[0]] + rhino_u + [rhino_u[-1]]
        back_v = [rhino_v[0]] + rhino_v + [rhino_v[-1]]

        uu, um = rk._compact_knots(back_u)
        vu, vm = rk._compact_knots(back_v)
        assert uu == surf.uknots
        assert um == surf.umults
        assert vu == surf.vknots
        assert vm == surf.vmults

    def test_cubic_surface_roundtrip(self):
        surf = Surface(
            control_points=[[Vec(i, j, 0) for j in range(4)] for i in range(4)],
            uknots=[0.0, 1.0],
            vknots=[0.0, 1.0],
            umults=[4, 4],
            vmults=[4, 4],
            udegree=3,
            vdegree=3,
        )
        full_u = list(rk._expand_knots(surf.uknots, surf.umults))
        full_v = list(rk._expand_knots(surf.vknots, surf.vmults))
        rhino_u = full_u[1:-1]
        rhino_v = full_v[1:-1]
        back_u = [rhino_u[0]] + rhino_u + [rhino_u[-1]]
        back_v = [rhino_v[0]] + rhino_v + [rhino_v[-1]]

        uu, um = rk._compact_knots(back_u)
        vu, vm = rk._compact_knots(back_v)
        assert uu == surf.uknots
        assert um == surf.umults
        assert vu == surf.vknots
        assert vm == surf.vmults
