# This file was generated with the assistance of an AI coding tool.

"""Tests for IfcModel.apply_delta (PLAN-interactive-preview, I-1)."""

import pytest

from ifckit import IfcModel, IfcSchema, PendingWall, geom_backend
from ifckit.elements.opening import PendingWindow
from ifckit.geometry import Plane, Vec


def _wall_body(height=3.0, name="W1"):
    return PendingWall(
        footprint=[Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 0.2, 0), Vec(0, 0.2, 0)],
        plane=Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
        height=height,
        name=name,
    ).to_dict()


def _window_body(width=1.0, name="WIN1"):
    return PendingWindow(
        overall_width=width,
        overall_height=1.2,
        plane=Plane(Vec(1.0, 0.0, 0.0), Vec(1, 0, 0), Vec(0, 1, 0)),
        component_graph="fixed_casement",
        name=name,
    ).to_dict()


@pytest.fixture
def empty_model():
    """IFC4 model with site/building/storey but no products."""
    m = IfcModel("DeltaTest", schema=IfcSchema.IFC4)
    m.add_site("S").add_building("B").add_storey("GF")
    return m


class TestApplyDeltaBasics:
    def test_create_assigns_deterministic_guids(self, empty_model):
        m = empty_model
        changed = m.apply_delta([{**_wall_body(), "id": "w1"}])
        assert changed == [geom_backend.guid_for_id("w1")]
        assert m.ifc_file.by_guid(changed[0]).is_a("IfcWall")

    def test_identical_redelta_returns_empty(self, empty_model):
        m = empty_model
        elem = {**_wall_body(), "id": "w1"}
        assert m.apply_delta([elem]) != []
        assert m.apply_delta([elem]) == []

    def test_one_changed_measure_returns_exact_guid(self, empty_model):
        """Plan acceptance: 1 changed measure -> exactly those GUID(s)."""
        m = empty_model
        w1 = {**_wall_body(height=3.0), "id": "w1"}
        w2 = {**_wall_body(height=2.5, name="W2"), "id": "w2"}
        first = m.apply_delta([w1, w2])
        assert len(first) == 2
        w2_before = m.ifc_file.by_guid(geom_backend.guid_for_id("w2"))

        second = m.apply_delta([{**_wall_body(height=3.5), "id": "w1"}, w2])
        assert second == [geom_backend.guid_for_id("w1")]
        # Untouched product is still the same entity.
        assert m.ifc_file.by_guid(geom_backend.guid_for_id("w2")) == w2_before
        # Changed GUIDs feed selective re-tessellation (I-2) directly.
        selective = m.to_mesh_dicts(include_guids=second)
        assert [d["guid"] for d in selective] == second

    def test_rebuilt_wall_tessellates(self, empty_model):
        m = empty_model
        m.apply_delta([{**_wall_body(height=3.0), "id": "w1"}])
        m.apply_delta([{**_wall_body(height=3.5), "id": "w1"}])
        dicts = m.to_mesh_dicts()
        assert len(dicts) == 1
        assert dicts[0]["guid"] == geom_backend.guid_for_id("w1")


class TestApplyDeltaGuidPolicy:
    def test_global_id_wins_and_sticks(self, empty_model):
        import ifcopenshell.guid

        m = empty_model
        custom = ifcopenshell.guid.new()
        changed = m.apply_delta([{**_wall_body(), "id": "w1", "global_id": custom}])
        assert changed == [custom]
        # Resend without global_id: mapped GUID is kept, nothing rebuilds.
        assert m.apply_delta([{**_wall_body(), "id": "w1"}]) == []
        assert m.ifc_file.by_guid(custom).is_a("IfcWall")

    def test_guid_only_key_works(self, empty_model):
        import ifcopenshell.guid

        m = empty_model
        custom = ifcopenshell.guid.new()
        assert m.apply_delta([{**_wall_body(), "global_id": custom}]) == [custom]
        assert m.apply_delta([{**_wall_body(), "global_id": custom}]) == []

    def test_adopts_entity_built_outside_delta(self, empty_model):
        m = empty_model
        storey = m.ifc_file.by_type("IfcBuildingStorey")[0]
        from ifckit.handles import StoreyHandle

        handle = StoreyHandle(storey, m).add(
            PendingWall(
                footprint=[Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 0.2, 0), Vec(0, 0.2, 0)],
                plane=Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
                height=3.0,
                name="W9",
            )
        )
        handle.entity.GlobalId = geom_backend.guid_for_id("w9")
        changed = m.apply_delta([{**_wall_body(), "id": "w9"}])
        assert changed == [geom_backend.guid_for_id("w9")]
        assert len(m.ifc_file.by_type("IfcWall")) == 1

    def test_missing_identity_raises(self, empty_model):
        with pytest.raises(ValueError, match="'id' or 'global_id'"):
            empty_model.apply_delta([_wall_body()])

    def test_unknown_type_raises(self, empty_model):
        with pytest.raises(ValueError, match="unknown element type"):
            empty_model.apply_delta([{"id": "x", "element_type": "nope"}])

    def test_bad_global_id_raises(self, empty_model):
        with pytest.raises(ValueError, match="22-char"):
            empty_model.apply_delta([{**_wall_body(), "id": "w1", "global_id": "short"}])

    def test_missing_type_raises(self, empty_model):
        with pytest.raises(ValueError, match="element_type"):
            empty_model.apply_delta([{"id": "x", "height": 3.0}])

    def test_duplicate_global_id_raises(self, empty_model):
        import ifcopenshell.guid

        m = empty_model
        custom = ifcopenshell.guid.new()
        m.apply_delta([{**_wall_body(), "id": "w1", "global_id": custom}])
        with pytest.raises(ValueError, match="already used"):
            m.apply_delta([{**_wall_body(name="W2"), "id": "w2", "global_id": custom}])


class TestApplyDeltaHosts:
    def test_model_b_fill_roundtrip(self, empty_model):
        m = empty_model
        wall = {**_wall_body(), "id": "w1"}
        win = {**_window_body(), "id": "win1", "host_id": "w1"}
        guids = m.apply_delta([wall, win])
        assert guids == [geom_backend.guid_for_id("w1"), geom_backend.guid_for_id("win1")]
        assert m.apply_delta([wall, win]) == []
        assert len(m.ifc_file.by_type("IfcWindow")) == 1
        assert len(m.ifc_file.by_type("IfcOpeningElement")) == 1

    def test_fill_param_change_returns_only_fill(self, empty_model):
        m = empty_model
        wall = {**_wall_body(), "id": "w1"}
        m.apply_delta([wall, {**_window_body(width=1.0), "id": "win1", "host_id": "w1"}])
        changed = m.apply_delta([wall, {**_window_body(width=1.5), "id": "win1", "host_id": "w1"}])
        assert changed == [geom_backend.guid_for_id("win1")]

    def test_host_replace_cascades_and_resend_rebuilds(self, empty_model):
        m = empty_model
        wall = {**_wall_body(height=3.0), "id": "w1"}
        win = {**_window_body(), "id": "win1", "host_id": "w1"}
        guids = m.apply_delta([wall, win])
        changed = m.apply_delta([{**_wall_body(height=3.5), "id": "w1"}, win])
        assert changed == guids
        assert len(m.ifc_file.by_type("IfcWall")) == 1
        assert len(m.ifc_file.by_type("IfcWindow")) == 1
        assert len(m.ifc_file.by_type("IfcOpeningElement")) == 1
        assert m.apply_delta([{**_wall_body(height=3.5), "id": "w1"}, win]) == []

    def test_missing_host_raises(self, empty_model):
        with pytest.raises(ValueError, match="host_id .* not found"):
            empty_model.apply_delta([{**_window_body(), "id": "win1", "host_id": "ghost"}])

    def test_fill_without_preset_raises(self, empty_model):
        m = empty_model
        m.apply_delta([{**_wall_body(), "id": "w1"}])
        plain = _window_body()
        del plain["component_graph"]
        with pytest.raises(ValueError, match="component_graph"):
            m.apply_delta([{**plain, "id": "win1", "host_id": "w1"}])
