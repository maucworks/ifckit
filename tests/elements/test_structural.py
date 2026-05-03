"""Tests for PendingBeam, PendingColumn, PendingRevolvedBeam."""

import math
import pytest
from ifckit.geometry import Vec, Line, Arc, Path, Plane
from ifckit.elements.structural import PendingBeam, PendingColumn, PendingRevolvedBeam


AXIS = Line(Vec(0, 0, 0), Vec(5, 0, 0))
PROFILE = [Vec(0, -0.1, 0), Vec(0.2, -0.1, 0), Vec(0.2, 0.1, 0), Vec(0, 0.1, 0)]
ARC = Arc(Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0), math.pi / 2)


class TestPendingBeam:
    def test_element_type(self):
        b = PendingBeam(AXIS, PROFILE)
        assert b.element_type == "basic_beam"

    def test_fields(self):
        b = PendingBeam(AXIS, PROFILE, name="B1")
        assert b.name == "B1"
        assert len(b.profile) == 4
        assert b.ref_line is None
        assert b.clips == []

    def test_ref_line(self):
        b = PendingBeam(AXIS, PROFILE, ref_line=AXIS)
        assert b.ref_line is AXIS

    def test_to_dict(self):
        b = PendingBeam(AXIS, PROFILE, name="B1")
        d = b.to_dict()
        assert d["type"] == "basic_beam"
        assert d["axis"]["start"] == (0.0, 0.0, 0.0)
        assert d["axis"]["end"] == (5.0, 0.0, 0.0)
        assert len(d["profile"]) == 4

    def test_from_dict_roundtrip(self):
        b = PendingBeam(AXIS, PROFILE, name="B1")
        d = b.to_dict()
        b2 = PendingBeam.from_dict(d)
        assert b2.name == "B1"
        assert b2.axis.start.equals(AXIS.start)
        assert b2.axis.end.equals(AXIS.end)
        assert len(b2.profile) == 4

    def test_from_dict_missing_axis_raises(self):
        with pytest.raises(ValueError, match="axis"):
            PendingBeam.from_dict({"profile": [(0, 0, 0)]})

    def test_from_dict_missing_profile_raises(self):
        with pytest.raises(ValueError, match="profile"):
            PendingBeam.from_dict({"axis": {"start": (0, 0, 0), "end": (1, 0, 0)}})

    def test_profile_is_copy(self):
        pts = list(PROFILE)
        b = PendingBeam(AXIS, pts)
        pts.append(Vec(99, 0, 0))
        assert len(b.profile) == 4

    def test_up_default_is_none(self):
        b = PendingBeam(AXIS, PROFILE)
        assert b.up is None

    def test_up_stored(self):
        b = PendingBeam(AXIS, PROFILE, up=Vec(0, 0, 1))
        assert b.up.equals(Vec(0, 0, 1))

    def test_up_parallel_to_axis_raises(self):
        with pytest.raises(ValueError, match="parallel"):
            PendingBeam(AXIS, PROFILE, up=Vec(1, 0, 0))  # axis is along +X

    def test_up_zero_raises(self):
        with pytest.raises(ValueError):
            PendingBeam(AXIS, PROFILE, up=Vec(0, 0, 0))

    def test_from_plane_extracts_y_axis(self):
        plane = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))
        b = PendingBeam.from_plane(AXIS, PROFILE, plane)
        assert b.up.equals(plane.y_axis)

    def test_up_roundtrip(self):
        b = PendingBeam(AXIS, PROFILE, up=Vec(0, 1, 1))
        d = b.to_dict()
        assert "up" in d
        b2 = PendingBeam.from_dict(d)
        assert b2.up.equals(Vec(0, 1, 1))

    def test_no_up_not_in_dict(self):
        b = PendingBeam(AXIS, PROFILE)
        assert "up" not in b.to_dict()


class TestPendingColumn:
    def test_element_type(self):
        c = PendingColumn(AXIS, PROFILE)
        assert c.element_type == "basic_column"

    def test_fields(self):
        c = PendingColumn(AXIS, PROFILE, name="C1")
        assert c.name == "C1"
        assert len(c.profile) == 4

    def test_to_dict(self):
        c = PendingColumn(AXIS, PROFILE, name="C1")
        d = c.to_dict()
        assert d["type"] == "basic_column"
        assert "axis" in d
        assert "profile" in d

    def test_from_dict_roundtrip(self):
        c = PendingColumn(AXIS, PROFILE, name="C1")
        d = c.to_dict()
        c2 = PendingColumn.from_dict(d)
        assert c2.name == "C1"
        assert c2.axis.start.equals(AXIS.start)

    def test_from_dict_missing_axis_raises(self):
        with pytest.raises(ValueError):
            PendingColumn.from_dict({"profile": [(0, 0, 0)]})

    def test_up_default_is_none(self):
        c = PendingColumn(AXIS, PROFILE)
        assert c.up is None

    def test_up_stored(self):
        c = PendingColumn(AXIS, PROFILE, up=Vec(0, 0, 1))
        assert c.up.equals(Vec(0, 0, 1))

    def test_up_parallel_to_axis_raises(self):
        with pytest.raises(ValueError, match="parallel"):
            PendingColumn(AXIS, PROFILE, up=Vec(1, 0, 0))

    def test_from_plane_extracts_y_axis(self):
        plane = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))
        c = PendingColumn.from_plane(AXIS, PROFILE, plane)
        assert c.up.equals(plane.y_axis)

    def test_up_roundtrip(self):
        c = PendingColumn(AXIS, PROFILE, up=Vec(0, 1, 1))
        d = c.to_dict()
        b2 = PendingColumn.from_dict(d)
        assert b2.up.equals(Vec(0, 1, 1))


class TestPendingRevolvedBeam:
    def test_element_type(self):
        rb = PendingRevolvedBeam(ARC, PROFILE)
        assert rb.element_type == "revolved_beam"

    def test_fields(self):
        rb = PendingRevolvedBeam(ARC, PROFILE, name="RB1")
        assert rb.name == "RB1"
        assert rb.arc is ARC
        assert len(rb.profile) == 4
        assert rb.ref_line is None

    def test_ref_line(self):
        rb = PendingRevolvedBeam(ARC, PROFILE, ref_line=AXIS)
        assert rb.ref_line is AXIS

    def test_to_dict(self):
        rb = PendingRevolvedBeam(ARC, PROFILE)
        d = rb.to_dict()
        assert d["type"] == "revolved_beam"
        assert abs(d["arc"]["angle_deg"] - 90.0) < 1e-6

    def test_from_dict_roundtrip(self):
        rb = PendingRevolvedBeam(ARC, PROFILE, name="RB1")
        d = rb.to_dict()
        rb2 = PendingRevolvedBeam.from_dict(d)
        assert rb2.name == "RB1"
        assert rb2.arc.radius == pytest.approx(ARC.radius)
        assert rb2.arc.angle == pytest.approx(ARC.angle)

    def test_from_dict_missing_arc_raises(self):
        with pytest.raises(ValueError):
            PendingRevolvedBeam.from_dict({"profile": [(0, 0, 0)]})


# ---------------------------------------------------------------------------
# TC4 — from_dict round-trip verifies plane is preserved
# ---------------------------------------------------------------------------


class TestFromDictPlaneLoss:
    """TC4: Verifies that PendingWall.from_dict correctly round-trips the plane."""

    def test_wall_from_dict_plane_roundtrip(self):
        """
        PendingWall.to_dict serialises the plane and from_dict restores it.
        This test was previously misnamed 'PlaneLoss' and failed to assert the plane;
        it now confirms the round-trip is correct.
        """
        from ifckit.elements.building import PendingWall

        footprint = [Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 0.3, 0), Vec(0, 0.3, 0)]
        plane = Plane(Vec(0, 0, 1), Vec(1, 0, 0), Vec(0, 1, 0))
        w = PendingWall(footprint, plane, 3.0, name="W")
        d = w.to_dict()
        w2 = PendingWall.from_dict(d)
        assert w2.name == "W"
        assert len(w2.footprint) == 4
        # Plane origin, x_axis, and y_axis must survive the round-trip
        assert w2.plane.origin.equals(plane.origin)
        assert w2.plane.x_axis.equals(plane.x_axis)
        assert w2.plane.y_axis.equals(plane.y_axis)
