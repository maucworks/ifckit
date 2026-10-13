# This file was generated with the assistance of an AI coding tool.

"""Tests for ifckit.session.ModelSession (PLAN-interactive-preview, I-7)."""

import pytest

from ifckit import IfcModel, IfcSchema, ModelSession, PendingWall, geom_backend
from ifckit.geometry import Plane, Vec


def _wall(height=3.0):
    return {
        **PendingWall(
            footprint=[Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 0.2, 0), Vec(0, 0.2, 0)],
            plane=Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
            height=height,
            name="W1",
        ).to_dict(),
        "id": "w1",
    }


class TestModelSession:
    def test_three_ticks_one_session(self):
        session = ModelSession()
        file_before = session.model.ifc_file
        changed, payload = session.tick([_wall(2.6)])
        assert changed == [geom_backend.guid_for_id("w1")]
        assert len(payload) == 1
        assert session.model.ifc_file is file_before

        changed, payload = session.tick([_wall(2.6)])
        assert changed == []
        assert payload == []

        changed, payload = session.tick([_wall(3.0)])
        assert changed == [geom_backend.guid_for_id("w1")]
        assert [c["guid"] for c in payload] == changed

    def test_full_returns_everything(self):
        session = ModelSession()
        session.tick([_wall()])
        changed, payload = session.tick([_wall()], full=True)
        assert changed == []
        assert len(payload) == 1

    def test_kind_dicts(self):
        session = ModelSession()
        _, payload = session.tick([_wall()], kind="dicts")
        assert payload[0]["primitive"] == "triangles"

    def test_unknown_kind_raises(self):
        with pytest.raises(ValueError, match="kind must be"):
            ModelSession().tick([_wall()], kind="mesh")

    def test_settings_cached(self):
        session = ModelSession()
        session.tick([_wall()])
        session.tick([_wall(3.5)])
        assert len(session._settings_cache) == 1
        session.tick([_wall(3.5)], preset="final")
        assert len(session._settings_cache) == 2

    def test_wraps_existing_model(self):
        m = IfcModel(name="Mine", schema=IfcSchema.IFC4)
        m.add_site("S").add_building("B").add_storey("GF")
        session = ModelSession(model=m)
        assert session.model is m
        changed, _ = session.tick([_wall()])
        assert changed == [geom_backend.guid_for_id("w1")]
