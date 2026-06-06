"""Tests for WallGraphBuilder — graph-offset mode (Shapely-based)."""
import pytest
import ifcopenshell

from ifckit.elements.wall_graph import PendingWallGraph
from ifckit.builders.wall_graph import WallGraphBuilder
from ifckit.geometry import Vec, Plane
from ifckit.geometry.path import Path

XY = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build(ifc4_model, ifc4_storey, body_context, pending):
    builder = WallGraphBuilder()
    return builder.build(ifc4_model.ifc_file, pending, ifc4_storey.entity, body_context)


# ---------------------------------------------------------------------------
# Straight single-segment wall
# ---------------------------------------------------------------------------

class TestStraightWall:
    def test_produces_ifc_wall(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingWallGraph(
            vertices=[Vec(0, 0, 0), Vec(5000, 0, 0)],
            edges=[(0, 1)],
            plane=XY,
            thickness=200,
            height=3000,
            name="Straight",
        )
        wall = _build(ifc4_model, ifc4_storey, body_context, pending)
        assert wall.is_a("IfcWall")
        assert wall.Name == "Straight"

    def test_single_extruded_solid(self, ifc4_model, ifc4_storey, body_context):
        """Graph-offset always produces exactly one ExtrudedAreaSolid."""
        pending = PendingWallGraph(
            vertices=[Vec(0, 0, 0), Vec(5000, 0, 0)],
            edges=[(0, 1)],
            plane=XY,
            thickness=200,
            height=3000,
        )
        _build(ifc4_model, ifc4_storey, body_context, pending)
        solids = ifc4_model.ifc_file.by_type("IfcExtrudedAreaSolid")
        assert len(solids) == 1

    def test_no_boolean_results(self, ifc4_model, ifc4_storey, body_context):
        """Old edge mode used IfcBooleanResult; new mode must not."""
        pending = PendingWallGraph(
            vertices=[Vec(0, 0, 0), Vec(5000, 0, 0)],
            edges=[(0, 1)],
            plane=XY,
            thickness=200,
            height=3000,
        )
        _build(ifc4_model, ifc4_storey, body_context, pending)
        bools = ifc4_model.ifc_file.by_type("IfcBooleanResult")
        assert len(bools) == 0

    def test_extrude_depth_matches_height(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingWallGraph(
            vertices=[Vec(0, 0, 0), Vec(5000, 0, 0)],
            edges=[(0, 1)],
            plane=XY,
            thickness=200,
            height=2500,
        )
        _build(ifc4_model, ifc4_storey, body_context, pending)
        solid = ifc4_model.ifc_file.by_type("IfcExtrudedAreaSolid")[0]
        assert solid.Depth == pytest.approx(2500)

    def test_rep_type_is_swept_solid(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingWallGraph(
            vertices=[Vec(0, 0, 0), Vec(5000, 0, 0)],
            edges=[(0, 1)],
            plane=XY,
            thickness=200,
            height=3000,
        )
        wall = _build(ifc4_model, ifc4_storey, body_context, pending)
        rep = wall.Representation.Representations[0]
        assert rep.RepresentationType == "SweptSolid"


# ---------------------------------------------------------------------------
# L-corner (two edges, degree-2 vertex)
# ---------------------------------------------------------------------------

class TestLCorner:
    def test_produces_one_solid(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingWallGraph(
            vertices=[Vec(0, 0, 0), Vec(5000, 0, 0), Vec(5000, 3000, 0)],
            edges=[(0, 1), (1, 2)],
            plane=XY,
            thickness=200,
            height=3000,
        )
        _build(ifc4_model, ifc4_storey, body_context, pending)
        assert len(ifc4_model.ifc_file.by_type("IfcExtrudedAreaSolid")) == 1
        assert len(ifc4_model.ifc_file.by_type("IfcBooleanResult")) == 0


# ---------------------------------------------------------------------------
# T-junction (three edges sharing one vertex)
# ---------------------------------------------------------------------------

class TestTJunction:
    def test_produces_one_solid(self, ifc4_model, ifc4_storey, body_context):
        # Horizontal run split at midpoint + perpendicular branch — vertex 2 has degree 3
        pending = PendingWallGraph(
            vertices=[
                Vec(0, 0, 0),     # 0 — left end
                Vec(6000, 0, 0),  # 1 — right end
                Vec(3000, 0, 0),  # 2 — T-junction (degree 3)
                Vec(3000, -3000, 0),  # 3 — branch end
            ],
            edges=[(0, 2), (2, 1), (2, 3)],  # vertex 2 shared by 3 edges
            plane=XY,
            thickness=200,
            height=3000,
        )
        _build(ifc4_model, ifc4_storey, body_context, pending)
        assert len(ifc4_model.ifc_file.by_type("IfcExtrudedAreaSolid")) == 1
        assert len(ifc4_model.ifc_file.by_type("IfcBooleanResult")) == 0


# ---------------------------------------------------------------------------
# X-junction (four edges meeting at center)
# ---------------------------------------------------------------------------

class TestXJunction:
    def test_produces_one_solid(self, ifc4_model, ifc4_storey, body_context):
        center = Vec(3000, 3000, 0)
        pending = PendingWallGraph(
            vertices=[
                Vec(3000, 0, 0),
                Vec(3000, 6000, 0),
                Vec(0, 3000, 0),
                Vec(6000, 3000, 0),
                center,
            ],
            edges=[(0, 4), (4, 1), (2, 4), (4, 3)],
            plane=XY,
            thickness=200,
            height=3000,
        )
        _build(ifc4_model, ifc4_storey, body_context, pending)
        assert len(ifc4_model.ifc_file.by_type("IfcExtrudedAreaSolid")) == 1
        assert len(ifc4_model.ifc_file.by_type("IfcBooleanResult")) == 0


# ---------------------------------------------------------------------------
# Placement and containment
# ---------------------------------------------------------------------------

class TestPlacementAndContainment:
    def test_wall_contained_in_storey(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingWallGraph(
            vertices=[Vec(0, 0, 0), Vec(5000, 0, 0)],
            edges=[(0, 1)],
            plane=XY,
            thickness=200,
            height=3000,
        )
        _build(ifc4_model, ifc4_storey, body_context, pending)
        rels = ifc4_model.ifc_file.by_type("IfcRelContainedInSpatialStructure")
        assert any(r.RelatingStructure == ifc4_storey.entity for r in rels)

    def test_wall_has_local_placement(self, ifc4_model, ifc4_storey, body_context):
        pending = PendingWallGraph(
            vertices=[Vec(0, 0, 0), Vec(5000, 0, 0)],
            edges=[(0, 1)],
            plane=XY,
            thickness=200,
            height=3000,
        )
        wall = _build(ifc4_model, ifc4_storey, body_context, pending)
        assert wall.ObjectPlacement is not None


# ---------------------------------------------------------------------------
# File round-trip
# ---------------------------------------------------------------------------

class TestFileRoundTrip:
    def test_file_parses_after_save(self, ifc4_model, ifc4_storey, body_context, tmp_path):
        pending = PendingWallGraph(
            vertices=[Vec(0, 0, 0), Vec(5000, 0, 0), Vec(5000, 3000, 0)],
            edges=[(0, 1), (1, 2)],
            plane=XY,
            thickness=200,
            height=3000,
        )
        _build(ifc4_model, ifc4_storey, body_context, pending)
        path = str(tmp_path / "wall_graph.ifc")
        ifc4_model.save(path)
        reopened = ifcopenshell.open(path)
        assert len(reopened.by_type("IfcWall")) == 1
        assert len(reopened.by_type("IfcExtrudedAreaSolid")) == 1
        assert len(reopened.by_type("IfcBooleanResult")) == 0


# ---------------------------------------------------------------------------
# Non-XY plane (open-path mode)
# ---------------------------------------------------------------------------

class TestNonXYPlane:
    def _profile_y_coords(self, ifc_file):
        profile = ifc_file.by_type("IfcArbitraryClosedProfileDef")[0]
        return [pt.Coordinates[1] for pt in profile.OuterCurve.Points]

    def test_xz_plane_open_path_non_degenerate(self, ifc4_model, ifc4_storey, body_context):
        """Profile must span ±thickness/2 in local Y; Vec.z must not be silently dropped."""
        path = Path(plane=Plane.world_xz()).add_line(Vec(0, 0, 0), Vec(5000, 0, 0))
        pending = PendingWallGraph(
            path=path,
            plane=Plane.world_xz(),
            thickness=200,
            height=3000,
            name="XZ-wall",
        )
        _build(ifc4_model, ifc4_storey, body_context, pending)

        y_coords = self._profile_y_coords(ifc4_model.ifc_file)
        assert min(y_coords) < -1, "profile collapsed: all Y coords near zero"
        assert max(y_coords) > 1, "profile collapsed: all Y coords near zero"

    def test_xz_plane_produces_one_solid(self, ifc4_model, ifc4_storey, body_context):
        path = Path(plane=Plane.world_xz()).add_line(Vec(0, 0, 0), Vec(5000, 0, 0))
        pending = PendingWallGraph(
            path=path,
            plane=Plane.world_xz(),
            thickness=200,
            height=3000,
        )
        _build(ifc4_model, ifc4_storey, body_context, pending)
        assert len(ifc4_model.ifc_file.by_type("IfcExtrudedAreaSolid")) == 1
