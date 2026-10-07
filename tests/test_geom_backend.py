"""Tests for ifckit.geom_backend — ifcopenshell 0.9 facade."""

import pytest

from ifckit import IfcModel, IfcSchema, PendingWall, geom_backend
from ifckit.elements.opening import PendingOpening
from ifckit.elements.structural import PendingBeam
from ifckit.geometry import Line, Plane, Vec


_SQUARE_PROFILE = [Vec(-0.1, -0.1), Vec(0.1, -0.1), Vec(0.1, 0.1), Vec(-0.1, 0.1)]


def _beam_model():
    m = IfcModel(name="GeomBackendTest", schema=IfcSchema.IFC4)
    floor = m.add_site("S").add_building("B").add_storey("GF")
    floor.add(PendingBeam(Line(Vec(0, 0, 0), Vec(5, 0, 0)), _SQUARE_PROFILE, name="Beam"))
    return m


def _wall_with_opening_model():
    m = IfcModel("TestProject", schema=IfcSchema.IFC4)
    site = m.add_site("Site")
    bldg = m.add_building(site, "Building")
    storey = m.add_storey(bldg, "GF", elevation=0.0)
    wall = m.add(PendingWall(
        footprint=[Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 0.2, 0), Vec(0, 0.2, 0)],
        plane=Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
        height=3.0, name="W1",
    ), storey)
    m.add_opening(
        PendingOpening(
            plane=Plane(Vec(1.0, 0.0, 0.0), Vec(1, 0, 0), Vec(0, 1, 0)),
            width=0.9, height=2.1, name="OP1",
        ),
        host=wall, container=storey,
    )
    return m


class TestVersion:
    def test_get_version(self):
        assert geom_backend.get_version().startswith("0.9")

    def test_require_version_ok(self):
        assert geom_backend.require_version().startswith("0.9")

    def test_require_version_rejects_old(self, monkeypatch):
        monkeypatch.setattr(geom_backend, "get_version", lambda: "0.8.5")
        with pytest.raises(ImportError, match=">= 0.9.0"):
            geom_backend.require_version()


class TestMakeSettings:
    def test_defaults(self):
        s = geom_backend.make_settings()
        assert s.get("mesher-linear-deflection") == pytest.approx(0.05)
        assert s.get("mesher-angular-deflection") == pytest.approx(0.8)
        assert s.get("use-world-coords") is True

    def test_overrides(self):
        s = geom_backend.make_settings(
            {"linear_deflection": 0.01, "angular_deflection": 0.5}
        )
        assert s.get("mesher-linear-deflection") == pytest.approx(0.01)
        assert s.get("mesher-angular-deflection") == pytest.approx(0.5)


class TestMakeSerializer:
    def test_glb(self, tmp_path):
        s = geom_backend.make_settings()
        serializer = geom_backend.make_serializer(str(tmp_path / "out.glb"), s)
        assert hasattr(serializer, "write")

    def test_obj_sidecar(self, tmp_path):
        s = geom_backend.make_settings()
        serializer = geom_backend.make_serializer(str(tmp_path / "out.obj"), s)
        assert hasattr(serializer, "write")

    def test_unknown_extension_raises(self, tmp_path):
        s = geom_backend.make_settings()
        with pytest.raises(ValueError):
            geom_backend.make_serializer(str(tmp_path / "out.xyz"), s)


class TestGuidForId:
    def test_deterministic_22_chars(self):
        g1 = geom_backend.guid_for_id("beam-1")
        g2 = geom_backend.guid_for_id("beam-1")
        assert g1 == g2
        assert len(g1) == 22
        import re

        assert re.fullmatch(r"[0-9A-Za-z_$]{22}", g1)

    def test_distinct_ids_distinct_guids(self):
        assert geom_backend.guid_for_id("beam-1") != geom_backend.guid_for_id("beam-2")

    def test_by_guid_roundtrip(self):
        m = _beam_model()
        guid = geom_backend.guid_for_id("beam-1")
        beam = m.ifc_file.by_type("IfcBeam")[0]
        beam.GlobalId = guid
        assert m.ifc_file.by_guid(guid) == beam


class TestIterShapes:
    def test_beam_shape(self):
        m = _beam_model()
        shapes = list(geom_backend.iter_shapes(m.ifc_file, geom_backend.make_settings()))
        assert len(shapes) == 1
        shape = shapes[0]
        assert shape.entity_type == "IfcBeam"
        assert m.ifc_file.by_guid(shape.guid).is_a("IfcBeam")
        assert len(shape.verts) > 0
        assert len(shape.faces) > 0

    def test_skip_openings(self):
        m = _wall_with_opening_model()
        assert len(m.ifc_file.by_type("IfcOpeningElement")) == 1
        settings = geom_backend.make_settings()
        with_skip = list(geom_backend.iter_shapes(m.ifc_file, settings, skip_openings=True))
        without_skip = list(
            geom_backend.iter_shapes(m.ifc_file, settings, skip_openings=False)
        )
        assert all(s.entity_type != "IfcOpeningElement" for s in with_skip)
        assert any(s.entity_type == "IfcOpeningElement" for s in without_skip)
        assert len(without_skip) == len(with_skip) + 1

    def test_include_guids(self):
        m = _wall_with_opening_model()
        settings = geom_backend.make_settings()
        all_shapes = list(
            geom_backend.iter_shapes(m.ifc_file, settings, skip_openings=False)
        )
        assert len(all_shapes) > 1
        wanted = all_shapes[0].guid
        filtered = list(
            geom_backend.iter_shapes(
                m.ifc_file, settings, skip_openings=False, include_guids=[wanted]
            )
        )
        assert [s.guid for s in filtered] == [wanted]

    def test_include_guids_empty_and_unknown(self):
        m = _beam_model()
        settings = geom_backend.make_settings()
        assert list(geom_backend.iter_shapes(m.ifc_file, settings, include_guids=[])) == []
        assert (
            list(
                geom_backend.iter_shapes(
                    m.ifc_file, settings, include_guids=["0" * 22]
                )
            )
            == []
        )


class TestShapesToMeshDicts:
    def test_format_and_y_up(self):
        m = _beam_model()
        shapes = geom_backend.iter_shapes(m.ifc_file, geom_backend.make_settings())
        dicts = list(geom_backend.shapes_to_mesh_dicts(shapes))
        assert len(dicts) == 1
        d = dicts[0]
        assert d["primitive"] == "triangles"
        assert d["guid"]
        assert d["label"] == "IfcBeam"
        assert len(d["positions"]) > 0
        assert len(d["indices"]) > 0
        # Y-up: positions[1] is Z, positions[2] is -Y.
        shape = list(
            geom_backend.iter_shapes(m.ifc_file, geom_backend.make_settings())
        )[0]
        assert d["positions"][0] == pytest.approx(shape.verts[0])
        assert d["positions"][1] == pytest.approx(shape.verts[2])
        assert d["positions"][2] == pytest.approx(-shape.verts[1])

    def test_no_y_up_is_identity(self):
        m = _beam_model()
        shapes = geom_backend.iter_shapes(m.ifc_file, geom_backend.make_settings())
        dicts = list(geom_backend.shapes_to_mesh_dicts(shapes, y_up=False))
        shape = list(
            geom_backend.iter_shapes(m.ifc_file, geom_backend.make_settings())
        )[0]
        assert dicts[0]["positions"] == pytest.approx(list(shape.verts))
