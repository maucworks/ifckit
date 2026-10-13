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
    def test_get_version_supported_line(self):
        parts = geom_backend._version_tuple(geom_backend.get_version())
        assert (0, 8, 4) <= parts < (0, 10)

    def test_require_version_ok(self):
        geom_backend.require_version()

    def test_require_version_accepts_rhino_line(self, monkeypatch):
        monkeypatch.setattr(geom_backend, "get_version", lambda: "0.8.4.post1")
        assert geom_backend.require_version() == "0.8.4.post1"

    def test_require_version_accepts_dev_suffix(self, monkeypatch):
        monkeypatch.setattr(geom_backend, "get_version", lambda: "0.9.0-dev")
        assert geom_backend.require_version() == "0.9.0-dev"

    def test_require_version_rejects_old(self, monkeypatch):
        monkeypatch.setattr(geom_backend, "get_version", lambda: "0.8.3")
        with pytest.raises(ImportError, match=">= 0.8.4"):
            geom_backend.require_version()

    def test_require_version_rejects_next_line(self, monkeypatch):
        monkeypatch.setattr(geom_backend, "get_version", lambda: "0.10.0")
        with pytest.raises(ImportError, match="< 0.10"):
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

    def test_interactive_preset(self):
        s = geom_backend.make_settings(preset="interactive")
        assert s.get("mesher-linear-deflection") == pytest.approx(0.5)
        assert s.get("mesher-angular-deflection") == pytest.approx(1.5)
        assert s.get("use-world-coords") is True

    def test_preset_positional_name(self):
        s = geom_backend.make_settings("interactive")
        assert s.get("mesher-linear-deflection") == pytest.approx(0.5)

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError, match="Unknown tessellation preset"):
            geom_backend.make_settings(preset="ultra")
        with pytest.raises(ValueError, match="Unknown tessellation preset"):
            geom_backend.make_settings("ultra")

    def test_explicit_dict_wins_over_preset(self):
        s = geom_backend.make_settings({"linear_deflection": 0.01}, preset="interactive")
        assert s.get("mesher-linear-deflection") == pytest.approx(0.01)
        assert s.get("mesher-angular-deflection") == pytest.approx(1.5)

    def test_presets_documented(self):
        assert set(geom_backend.PRESETS) == {"final", "interactive"}


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


class TestSerializeSkipOpenings:
    def _obj_groups(self, path):
        with open(path) as f:
            return [ln for ln in f.read().splitlines() if ln.startswith("g ")]

    def test_skip_openings(self, tmp_path):
        m = _wall_with_opening_model()
        settings = geom_backend.make_settings()
        skipped = str(tmp_path / "skipped.obj")
        kept = str(tmp_path / "kept.obj")
        try:
            geom_backend.serialize_to_file(m.ifc_file, skipped, settings)
            geom_backend.serialize_to_file(
                m.ifc_file, kept, settings, skip_openings=False
            )
        except ImportError:
            pytest.skip("OBJ serializer not in this ifcopenshell build")
        assert len(self._obj_groups(skipped)) == 1
        assert len(self._obj_groups(kept)) == 2

    def test_num_threads(self, tmp_path):
        m = _beam_model()
        out = str(tmp_path / "out.glb")
        try:
            geom_backend.serialize_to_file(
                m.ifc_file, out, geom_backend.make_settings(), num_threads=2
            )
        except ImportError:
            pytest.skip("glTF serializer not in this ifcopenshell build")
        import os

        assert os.path.getsize(out) > 0


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


def _two_beam_model():
    """Two identical beams 10 m apart, plus a third with a larger profile."""
    m = IfcModel(name="ChunkTest", schema=IfcSchema.IFC4)
    floor = m.add_site("S").add_building("B").add_storey("GF")
    big = [Vec(-0.2, -0.2), Vec(0.2, -0.2), Vec(0.2, 0.2), Vec(-0.2, 0.2)]
    floor.add(PendingBeam(Line(Vec(0, 0, 0), Vec(5, 0, 0)), _SQUARE_PROFILE, name="B1"))
    floor.add(
        PendingBeam(Line(Vec(10, 0, 0), Vec(15, 0, 0)), _SQUARE_PROFILE, name="B2")
    )
    floor.add(PendingBeam(Line(Vec(20, 0, 0), Vec(25, 0, 0)), big, name="B3"))
    return m


def _decode_floats(raw: bytes):
    from array import array

    return list(array("f", raw))


def _decode_uints(raw: bytes):
    from array import array

    return list(array("I", raw))


class TestShapesToChunks:
    def test_same_shapes_as_mesh_dicts(self):
        m = _beam_model()
        (chunk,) = geom_backend.shapes_to_chunks(
            geom_backend.iter_shapes(m.ifc_file, geom_backend.make_settings())
        )
        (mesh,) = geom_backend.shapes_to_mesh_dicts(
            geom_backend.iter_shapes(m.ifc_file, geom_backend.make_settings())
        )
        assert chunk["guid"] == mesh["guid"]
        assert chunk["label"] == mesh["label"]
        assert chunk["vertex_count"] == len(mesh["positions"]) // 3
        assert chunk["index_count"] == len(mesh["indices"])
        assert _decode_uints(chunk["index"]) == mesh["indices"]
        restored = [
            c + chunk["offset"][i % 3]
            for i, c in enumerate(_decode_floats(chunk["positions"]))
        ]
        assert restored == pytest.approx(mesh["positions"])

    def test_compact_payload(self):
        import json

        m = _beam_model()
        (chunk,) = geom_backend.shapes_to_chunks(
            geom_backend.iter_shapes(m.ifc_file, geom_backend.make_settings())
        )
        (mesh,) = geom_backend.shapes_to_mesh_dicts(
            geom_backend.iter_shapes(m.ifc_file, geom_backend.make_settings())
        )
        binary = len(chunk["positions"]) + len(chunk["index"])
        assert binary < len(json.dumps(mesh, default=str))

    def test_profile_key_groups_identical_products(self):
        m = _two_beam_model()
        chunks = list(
            geom_backend.shapes_to_chunks(
                geom_backend.iter_shapes(m.ifc_file, geom_backend.make_settings())
            )
        )
        assert len(chunks) == 3
        labels = [c["label"] for c in chunks]
        assert labels == ["IfcBeam"] * 3
        b1, b2, b3 = chunks
        assert b1["profile_key"] == b2["profile_key"]
        assert b1["offset"] != b2["offset"]
        assert b3["profile_key"] != b1["profile_key"]

    def test_model_iter_chunks_selective(self):
        m = _two_beam_model()
        guids = [c["guid"] for c in m.to_chunks()]
        assert len(guids) == 3
        (only,) = m.to_chunks(include_guids=[guids[0]])
        assert only["guid"] == guids[0]
        assert m.to_chunks(include_guids=[]) == []
