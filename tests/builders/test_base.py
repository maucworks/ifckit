"""Tests for BuilderRegistry, IIfcBuilder base, and _geom helpers."""
import ifcopenshell
import ifcopenshell.api
import pytest

from ifckit.builders import default_registry
from ifckit.builders._geom import (
    extrude_profile,
    get_body_context,
    profile_from_points,
)
from ifckit.builders.base import BuilderRegistry
from ifckit.builders.slab import SlabBuilder
from ifckit.builders.wall import WallBuilder


class TestBuildRegistry:
    def test_register_and_get(self):
        r = BuilderRegistry()
        b = WallBuilder()
        r.register(b)
        assert r.get("basic_wall") is b

    def test_register_duplicate_raises(self):
        r = BuilderRegistry()
        r.register(WallBuilder())
        with pytest.raises(ValueError, match="already registered"):
            r.register(WallBuilder())

    def test_get_unknown_raises(self):
        r = BuilderRegistry()
        with pytest.raises(KeyError, match="No builder"):
            r.get("nonexistent")

    def test_registered_types(self):
        r = BuilderRegistry()
        r.register(WallBuilder())
        r.register(SlabBuilder())
        types = r.registered_types()
        assert "basic_wall" in types
        assert "basic_slab" in types

    @pytest.mark.parametrize(
        "builder_type",
        ["basic_wall", "basic_slab", "basic_beam", "basic_column", "revolved_beam"],
    )
    def test_default_registry_has_all(self, builder_type):
        r = default_registry()
        assert builder_type in r.registered_types()

    def test_default_registry_excludes_alignment(self):
        """AlignmentBuilder is intentionally excluded — it is called directly by
        IfcModel.add_alignment(), not via model.add()."""
        r = default_registry()
        assert "alignment" not in r.registered_types()

    def test_entity_type_on_builders(self):
        assert WallBuilder().entity_type == "basic_wall"
        assert SlabBuilder().entity_type == "basic_slab"


class TestGeomHelpers:
    def _make_ifc4_file(self):
        """Create a minimal IFC4 file with a Model context."""
        f = ifcopenshell.file(schema="IFC4")
        ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="P")
        ifcopenshell.api.run("context.add_context", f, context_type="Model")
        return f

    def test_extrude_profile_no_position(self):
        f = self._make_ifc4_file()
        pts = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        profile = profile_from_points(f, pts)
        solid = extrude_profile(f, profile, depth=3.0, position=None)
        assert solid.is_a("IfcExtrudedAreaSolid")
        assert solid.Position is not None

    def test_get_body_context_returns_body_subcontext(self):
        f = self._make_ifc4_file()
        ifcopenshell.api.run("context.add_context", f, context_type="Model",
                              context_identifier="Body", target_view="MODEL_VIEW",
                              parent=f.by_type("IfcGeometricRepresentationContext")[0])
        ctx = get_body_context(f)
        assert ctx.ContextIdentifier == "Body"

    def test_get_body_context_falls_back_to_model(self):
        f = self._make_ifc4_file()
        ctx = get_body_context(f)
        assert ctx.ContextType == "Model"

    def test_get_body_context_raises_when_none(self):
        f = ifcopenshell.file(schema="IFC4")
        with pytest.raises(RuntimeError, match="No suitable"):
            get_body_context(f)
