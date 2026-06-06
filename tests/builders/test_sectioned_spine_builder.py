import pytest

from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.elements.sectioned_spine import PendingSectionedSpine
from ifckit.geometry import Path, Plane, Vec
from ifckit.profiles import RectangleProfile


@pytest.fixture
def builder():
    return SectionedSpineBuilder()


@pytest.fixture
def pending():
    spine = Path.from_pts([Vec(0, 0, 0), Vec(1000, 0, 0)])
    profile = RectangleProfile(50, 70)
    pos1 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    pos2 = Plane(Vec(1000, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    return PendingSectionedSpine(spine=spine, profiles=[profile, profile], positions=[pos1, pos2])


class TestBuildFaceSet:
    def test_returns_face_set(self, builder, pending, ifc4_model):
        fs = builder.build_face_set(ifc4_model.ifc_file, pending)
        assert fs.is_a("IfcTriangulatedFaceSet")
        assert len(fs.CoordIndex) > 0

    def test_closed_spine(self, builder, ifc4_model):
        spine = Path.from_pts([Vec(0, 0, 0), Vec(1000, 0, 0), Vec(1000, 1000, 0), Vec(0, 1000, 0)], closed=True)
        profile = RectangleProfile(50, 70)
        pos1 = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        pos2 = Plane(Vec(1000, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        pos3 = Plane(Vec(1000, 1000, 0), Vec(0, 1, 0), Vec(0, 0, 1))
        pos4 = Plane(Vec(0, 1000, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        p = PendingSectionedSpine(spine=spine, profiles=[profile, profile, profile, profile], positions=[pos1, pos2, pos3, pos4], closed=True)
        fs = builder.build_face_set(ifc4_model.ifc_file, p)
        assert fs.is_a("IfcTriangulatedFaceSet")


class TestBuildShapeRep:
    def test_returns_shape_rep(self, builder, pending, ifc4_model, body_context):
        rep = builder.build_shape_rep(ifc4_model.ifc_file, pending, body_context)
        assert rep.is_a("IfcShapeRepresentation")
        assert rep.RepresentationType == "Tessellation"


class TestBuildFromSpine:
    def test_creates_product(self, builder, ifc4_model, ifc4_storey, body_context):
        spine = Path.from_pts([Vec(0, 0, 0), Vec(1000, 0, 0)])
        profile = RectangleProfile(150, 300)
        starter = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))
        elem = builder.build_from_spine(ifc4_model.ifc_file, spine, profile, starter, ifc4_storey.entity, body_context)
        assert elem.is_a("IfcBuildingElementProxy")
        assert elem.Representation is not None

    def test_creates_containment(self, builder, ifc4_model, ifc4_storey, body_context):
        spine = Path.from_pts([Vec(0, 0, 0), Vec(1000, 0, 0)])
        profile = RectangleProfile(150, 300)
        starter = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))
        elem = builder.build_from_spine(ifc4_model.ifc_file, spine, profile, starter, ifc4_storey.entity, body_context)
        rels = ifc4_model.ifc_file.by_type("IfcRelContainedInSpatialStructure")
        contained = []
        for r in rels:
            for e in r.RelatedElements:
                contained.append(e)
        assert elem in contained


class TestRegistry:
    def test_registered(self, builder):
        assert builder.entity_type == "sectioned_spine"


class TestPendingRoundtrip:
    def test_to_dict_from_dict(self, pending):
        d = pending.to_dict()
        p2 = PendingSectionedSpine.from_dict(d)
        assert p2.name == pending.name
        assert len(p2.profiles) == len(pending.profiles)
        assert len(p2.positions) == len(pending.positions)
