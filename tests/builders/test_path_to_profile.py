"""Integration test: Path → IFC profile."""
import pytest
import ifcopenshell


def test_path_rect_to_ifc_profile():
    """Full chain: Path.rect() → profile_from_points() → IfcArbitraryClosedProfileDef."""
    from ifckit.geometry import Vec, Plane, Path
    from ifckit.builders._geom import profile_from_points

    f = ifcopenshell.file(schema="IFC4")
    pl = Plane.world_xy()
    path = Path.rect(pl, Vec(0, 0, 0), Vec(0.3, 3.0, 0))

    profile = profile_from_points(f, path)

    assert profile.is_a("IfcArbitraryClosedProfileDef")
    outer = profile.OuterCurve
    assert outer is not None


def test_path_from_pts_closed_to_ifc():
    """Path.from_pts(closed=True) → IFC profile."""
    from ifckit.geometry import Vec, Plane, Path
    from ifckit.builders._geom import profile_from_points

    f = ifcopenshell.file(schema="IFC4")
    pts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 2, 0), Vec(0, 2, 0)]
    path = Path.from_pts(pts, closed=True, plane=Plane.world_xy())

    profile = profile_from_points(f, path)

    assert profile.is_a("IfcArbitraryClosedProfileDef")


def test_path_to_profile_with_offset_plane():
    """to_profile_points on offset plane."""
    from ifckit.geometry import Vec, Plane, Path
    from ifckit.builders._geom import profile_from_points

    f = ifcopenshell.file(schema="IFC4")
    offset_plane = Plane(Vec(100, 200, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    path = Path.rect(offset_plane, Vec(0, 0, 0), Vec(50, 30, 0))

    profile = profile_from_points(f, path, profile_name="TestFrame")

    assert profile.is_a("IfcArbitraryClosedProfileDef")
    assert profile.ProfileName == "TestFrame"


def test_path_offset_then_profile():
    """offset() result → IFC profile."""
    from ifckit.geometry import Vec, Plane, Path
    from ifckit.builders._geom import profile_from_points

    f = ifcopenshell.file(schema="IFC4")
    pl = Plane.world_xy()
    original = Path.rect(pl, Vec(0, 0, 0), Vec(200, 150, 0))
    offset_path = original.offset(10)

    profile = profile_from_points(f, offset_path)

    assert profile.is_a("IfcArbitraryClosedProfileDef")