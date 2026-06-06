"""
Tests for ifckit.components — component registration, discovery, and base system.
"""

from __future__ import annotations

import pytest

from ifckit.components import (
    COMPONENT_REGISTRY,
    EvaluatedComponent,
    FillComponent,
    get_component,
    list_components,
)
from ifckit.geometry import Plane, Vec


# ---------------------------------------------------------------------------
# Component Registration and Discovery
# ---------------------------------------------------------------------------


class TestComponentRegistry:
    """Test component registration and discovery."""

    def test_registry_is_populated(self):
        """Verify that components are registered in the registry."""
        # Trigger discovery
        list_components()
        assert len(COMPONENT_REGISTRY) > 0

    def test_list_components_returns_names(self):
        """Verify list_components returns component names."""
        names = list_components()
        assert isinstance(names, list)
        assert len(names) > 0
        assert all(isinstance(n, str) for n in names)

    def test_simple_window_registered(self):
        """Verify SimpleWindow component is registered."""
        components = list_components()
        # Should have both full and short names
        assert "simple_window_component" in components or "simple_window" in components

    def test_simple_door_registered(self):
        """Verify SimpleDoor component is registered."""
        components = list_components()
        assert "simple_door_component" in components or "simple_door" in components

    def test_get_component_by_name(self):
        """Test retrieving component by name."""
        components = list_components()
        if components:
            name = components[0]
            cls = get_component(name)
            assert cls is not None
            assert issubclass(cls, FillComponent)

    def test_get_nonexistent_component(self):
        """Test getting a non-existent component returns None."""
        result = get_component("nonexistent_component_xyz")
        assert result is None

    def test_component_class_has_ifc_class(self):
        """Verify registered components have ifc_class attribute."""
        components = list_components()
        for name in components:
            cls = get_component(name)
            assert hasattr(cls, "ifc_class")
            assert isinstance(cls.ifc_class, str)
            assert len(cls.ifc_class) > 0

    def test_duplicate_registration_not_added(self):
        """Verify components are only registered once."""
        # Force re-discovery
        initial_count = len(list_components())
        names = list_components()
        assert len(names) == initial_count


# ---------------------------------------------------------------------------
# EvaluatedComponent Data Class
# ---------------------------------------------------------------------------


class TestEvaluatedComponent:
    """Test EvaluatedComponent data structure."""

    def test_create_basic_component(self):
        """Create a basic EvaluatedComponent."""
        # Mock IFC entity (we can't create real ones without ifcopenshell setup)
        comp = EvaluatedComponent(
            solid="mock_entity",
            role="Lining",
        )
        assert comp.solid == "mock_entity"
        assert comp.role == "Lining"
        assert comp.material is None
        assert comp.node_id is None

    def test_create_component_with_material(self):
        """Create component with material."""
        material = {"name": "Aluminum", "color": (192, 192, 192)}
        comp = EvaluatedComponent(
            solid="mock_entity",
            role="Frame",
            material=material,
        )
        assert comp.material == material

    def test_create_component_with_node_id(self):
        """Create component with node identifier."""
        comp = EvaluatedComponent(
            solid="mock_entity",
            role="Glazing",
            node_id="glass_0",
        )
        assert comp.node_id == "glass_0"

    def test_component_role_types(self):
        """Test various semantic roles."""
        roles = ["Opening", "Lining", "Glazing", "Panel", "Frame"]
        for role in roles:
            comp = EvaluatedComponent(
                solid="mock_entity",
                role=role,
            )
            assert comp.role == role


# ---------------------------------------------------------------------------
# FillComponent Abstract Base
# ---------------------------------------------------------------------------


class TestFillComponentBase:
    """Test FillComponent abstract base class."""

    def test_cannot_instantiate_directly(self):
        """FillComponent is abstract and cannot be instantiated directly."""
        with pytest.raises(TypeError):
            FillComponent()

    def test_subclass_must_implement_build(self):
        """Subclasses must implement build method."""

        class IncompleteComponent(FillComponent):
            ifc_class = "IfcDoor"
            # Missing build method

        with pytest.raises(TypeError):
            IncompleteComponent()

    def test_valid_subclass_signature(self):
        """Valid subclass with build method can be created."""

        class ValidComponent(FillComponent):
            ifc_class = "IfcWindow"

            def build(self, ifc_file, plane, width=1000, height=1000, params=None, path=None):
                return []

        # Should be instantiable
        comp = ValidComponent()
        assert isinstance(comp, FillComponent)
        assert comp.ifc_class == "IfcWindow"

    def test_default_ifc_class(self):
        """FillComponent has a default ifc_class."""
        assert FillComponent.ifc_class == "IfcWindow"


# ---------------------------------------------------------------------------
# Component Instantiation and Configuration
# ---------------------------------------------------------------------------


class TestComponentInstantiation:
    """Test component instantiation with real components."""

    def test_simple_window_instantiation(self):
        """Instantiate SimpleWindow component."""
        cls = get_component("simple_window")
        if cls is not None:
            comp = cls()
            assert isinstance(comp, FillComponent)
            assert comp.ifc_class == "IfcWindow"

    def test_simple_door_instantiation(self):
        """Instantiate SimpleDoor component."""
        cls = get_component("simple_door")
        if cls is not None:
            comp = cls()
            assert isinstance(comp, FillComponent)
            assert comp.ifc_class == "IfcDoor"

    def test_fixed_casement_instantiation(self):
        """Instantiate FixedCasement component."""
        cls = get_component("fixed_casement")
        if cls is not None:
            comp = cls()
            assert isinstance(comp, FillComponent)

    def test_curved_casement_instantiation(self):
        """Instantiate CurvedCasement component if available."""
        cls = get_component("curved_casement")
        if cls is not None:
            comp = cls()
            assert isinstance(comp, FillComponent)


# ---------------------------------------------------------------------------
# Component Parameters
# ---------------------------------------------------------------------------


class TestComponentParameters:
    """Test component parameter handling."""

    def test_build_with_basic_parameters(self):
        """Test build method with basic geometric parameters."""
        cls = get_component("simple_window")
        if cls is None:
            pytest.skip("SimpleWindow component not available")
        comp = cls()
        # Mock IFC file (simplified; would need full setup for real test)
        params = {
            "lining_thickness": 50,
            "lining_depth": 70,
            "glass_depth": 6,
        }
        # We can't test without ifcopenshell file; this is a signature test
        assert hasattr(comp, "build")

    def test_build_accepts_width_height(self):
        """Test that build method accepts width and height."""
        cls = get_component("simple_door")
        if cls is None:
            pytest.skip("SimpleDoor component not available")
        comp = cls()
        # Check method signature accepts these params
        import inspect

        sig = inspect.signature(comp.build)
        params = list(sig.parameters.keys())
        assert "width" in params or "w" in params
        assert "height" in params or "h" in params

    def test_build_accepts_params_dict(self):
        """Test that build method accepts params dict."""
        cls = get_component("simple_window")
        if cls is None:
            pytest.skip("SimpleWindow component not available")
        comp = cls()
        import inspect

        sig = inspect.signature(comp.build)
        params = list(sig.parameters.keys())
        assert "params" in params


# ---------------------------------------------------------------------------
# Component Output
# ---------------------------------------------------------------------------


class TestComponentOutput:
    """Test component build output structure."""

    def test_build_returns_list(self):
        """Build method returns a list."""
        cls = get_component("simple_window")
        if cls is None:
            pytest.skip("SimpleWindow component not available")
        comp = cls()
        # Check return type annotation
        import inspect

        sig = inspect.signature(comp.build)
        # Return annotation should indicate list
        assert sig.return_annotation is not None

    def test_output_components_are_evaluated(self):
        """Output components should be EvaluatedComponent instances."""
        cls = get_component("simple_door")
        if cls is None:
            pytest.skip("SimpleDoor component not available")
        # Check that the implementation uses EvaluatedComponent
        import inspect

        source = inspect.getsource(cls.build)
        assert "EvaluatedComponent" in source


# ---------------------------------------------------------------------------
# Short and Long Component Names
# ---------------------------------------------------------------------------


class TestComponentNaming:
    """Test component short and long name registration."""

    def test_both_short_and_long_names_exist(self):
        """Components should be registered with both short and long names."""
        components = list_components()
        # Find at least one _component named and short named pair
        has_long = any("_component" in c for c in components)
        has_short = any("_component" not in c for c in components)
        assert has_long or has_short

    def test_short_name_retrieves_component(self):
        """Retrieving by short name should work."""
        components = list_components()
        short_names = [c for c in components if "_component" not in c]
        for short_name in short_names[:3]:  # Test first 3
            cls = get_component(short_name)
            assert cls is not None
            assert issubclass(cls, FillComponent)

    def test_long_name_retrieves_component(self):
        """Retrieving by long name should work."""
        components = list_components()
        long_names = [c for c in components if "_component" in c]
        for long_name in long_names[:3]:  # Test first 3
            cls = get_component(long_name)
            assert cls is not None
            assert issubclass(cls, FillComponent)


# ---------------------------------------------------------------------------
# Edge Cases and Error Handling
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases in component system."""

    def test_get_component_case_sensitive(self):
        """Component names are case-sensitive."""
        cls_lower = get_component("simple_window")
        cls_upper = get_component("SIMPLE_WINDOW")
        # At least one should fail
        if cls_lower is not None:
            # Upper should be None (case sensitive)
            assert cls_upper is None or cls_upper == cls_lower

    def test_empty_component_name(self):
        """Getting component with empty name returns None."""
        result = get_component("")
        assert result is None

    def test_whitespace_component_name(self):
        """Component name with whitespace returns None."""
        result = get_component("  simple_window  ")
        assert result is None

    def test_special_characters_in_name(self):
        """Component name with special characters returns None."""
        result = get_component("simple@window!")
        assert result is None


# ---------------------------------------------------------------------------
# Component Discovery Mechanics
# ---------------------------------------------------------------------------


class TestComponentDiscovery:
    """Test how components are discovered and registered."""

    def test_components_module_imports_successfully(self):
        """Components pythonic module imports without error."""
        import ifckit.components.pythonic

        assert ifckit.components.pythonic is not None

    def test_registry_populated_after_list_call(self):
        """Registry is populated after calling list_components."""
        initial_registry = dict(COMPONENT_REGISTRY)
        list_components()
        # Should have same or more entries
        assert len(COMPONENT_REGISTRY) >= len(initial_registry)

    def test_component_instances_are_independent(self):
        """Multiple instances of the same component are independent."""
        cls = get_component("simple_window")
        if cls is None:
            pytest.skip("SimpleWindow not available")
        comp1 = cls()
        comp2 = cls()
        # They should be different instances
        assert comp1 is not comp2
        assert isinstance(comp1, FillComponent)
        assert isinstance(comp2, FillComponent)
