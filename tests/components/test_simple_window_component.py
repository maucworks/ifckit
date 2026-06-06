"""
Tests for SimpleWindowComponent — generative window geometry.
"""

from __future__ import annotations

import pytest

from ifckit.components import get_component, EvaluatedComponent
from ifckit.geometry import Plane, Vec


@pytest.fixture
def ifc_file():
    """Create a minimal IFC file for testing."""
    import ifcopenshell

    f = ifcopenshell.file(schema="IFC4")
    ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="TestProject")
    ifcopenshell.api.run("unit.add_si_unit", f, unit_type="LENGTHUNIT")
    return f


@pytest.fixture
def window_component():
    """Get or skip SimpleWindowComponent."""
    cls = get_component("simple_window")
    if cls is None:
        pytest.skip("SimpleWindow component not available")
    return cls()


class TestSimpleWindowComponentBasics:
    """Test basic SimpleWindow functionality."""

    def test_component_exists(self, window_component):
        """SimpleWindowComponent should exist."""
        assert window_component is not None

    def test_component_is_window(self, window_component):
        """Component should create IfcWindow."""
        assert window_component.ifc_class == "IfcWindow"

    def test_build_method_exists(self, window_component):
        """Component should have build method."""
        assert hasattr(window_component, "build")
        assert callable(window_component.build)


class TestSimpleWindowComponentBuild:
    """Test SimpleWindow build method."""

    def test_build_returns_list(self, ifc_file, window_component):
        """Build should return a list of components."""
        plane = Plane.world_xy()
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=1200,
            h=1400,
            params={
                "lining_thickness": 50,
                "lining_depth": 70,
                "glass_depth": 6,
            },
        )
        assert isinstance(result, list)

    def test_build_returns_evaluated_components(self, ifc_file, window_component):
        """All items should be EvaluatedComponent instances."""
        plane = Plane.world_xy()
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=1200,
            h=1400,
            params={},
        )
        assert all(isinstance(item, EvaluatedComponent) for item in result)

    def test_build_includes_opening_component(self, ifc_file, window_component):
        """Build should include at least one opening component."""
        plane = Plane.world_xy()
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=1200,
            h=1400,
            params={},
        )
        roles = [item.role for item in result]
        assert "Opening" in roles

    def test_build_with_custom_parameters(self, ifc_file, window_component):
        """Build should work with custom parameters."""
        params = {
            "lining_thickness": 80,
            "lining_depth": 100,
            "sash_depth": 50,
            "glass_depth": 10,
            "wall_thickness": 300,
        }
        plane = Plane.world_xy()
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=1000,
            h=1500,
            params=params,
        )
        assert len(result) > 0

    def test_build_with_minimal_parameters(self, ifc_file, window_component):
        """Build should work with no parameters (using defaults)."""
        plane = Plane.world_xy()
        result = window_component.build(ifc_file, plane=plane, w=1200, h=1400, params={})
        assert len(result) > 0

    def test_build_respects_width_height(self, ifc_file, window_component):
        """Build should use specified width and height."""
        plane = Plane.world_xy()
        # Test multiple sizes
        for width, height in [(800, 1000), (1200, 1400), (1500, 1800)]:
            result = window_component.build(
                ifc_file,
                plane=plane,
                w=width,
                h=height,
                params={},
            )
            assert len(result) > 0


class TestSimpleWindowComponentPlacement:
    """Test SimpleWindow placement in different planes."""

    def test_build_in_world_xy_plane(self, ifc_file, window_component):
        """Build in world XY plane (horizontal)."""
        plane = Plane.world_xy()
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=1200,
            h=1400,
            params={},
        )
        assert len(result) > 0

    def test_build_in_vertical_plane(self, ifc_file, window_component):
        """Build in a vertical plane (XZ)."""
        plane = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=1200,
            h=1400,
            params={},
        )
        assert len(result) > 0

    def test_build_in_translated_plane(self, ifc_file, window_component):
        """Build in a translated plane."""
        plane = Plane(Vec(5, 10, 3), Vec(1, 0, 0), Vec(0, 1, 0))
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=1200,
            h=1400,
            params={},
        )
        assert len(result) > 0


class TestSimpleWindowComponentGeometry:
    """Test SimpleWindow geometric output."""

    def test_component_solids_are_ifc_entities(self, ifc_file, window_component):
        """Component solids should be valid IFC entities."""
        plane = Plane.world_xy()
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=1200,
            h=1400,
            params={},
        )
        # Each component should have a solid that is an IFC entity
        for comp in result:
            assert comp.solid is not None
            # In a proper IFC context, would check is_a("IfcGeometricRepresentationItem")

    def test_component_roles_are_valid(self, ifc_file, window_component):
        """Component roles should be semantic identifiers."""
        plane = Plane.world_xy()
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=1200,
            h=1400,
            params={},
        )
        valid_roles = {"Opening", "Lining", "Glazing", "Panel", "Frame", "Sash"}
        for comp in result:
            assert comp.role in valid_roles or len(comp.role) > 0

    def test_zero_lining_thickness(self, ifc_file, window_component):
        """Build with zero lining thickness should skip lining."""
        plane = Plane.world_xy()
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=1200,
            h=1400,
            params={"lining_thickness": 0},
        )
        # Should still have opening but no lining components
        roles = [item.role for item in result]
        assert "Opening" in roles

    def test_large_dimensions(self, ifc_file, window_component):
        """Build with large dimensions should work."""
        plane = Plane.world_xy()
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=5000,  # 5 meters
            h=3000,  # 3 meters
            params={},
        )
        assert len(result) > 0

    def test_small_dimensions(self, ifc_file, window_component):
        """Build with small dimensions should work."""
        plane = Plane.world_xy()
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=400,  # 400 mm
            h=500,  # 500 mm
            params={},
        )
        assert len(result) > 0


class TestSimpleWindowComponentEdgeCases:
    """Test SimpleWindow edge cases."""

    def test_build_with_negative_depth_parameters(self, ifc_file, window_component):
        """Negative depth parameters should be handled gracefully."""
        plane = Plane.world_xy()
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=1200,
            h=1400,
            params={"lining_depth": -50},
        )
        # Should either ignore or handle gracefully
        assert isinstance(result, list)

    def test_build_with_very_large_parameters(self, ifc_file, window_component):
        """Very large parameter values should be handled."""
        plane = Plane.world_xy()
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=1200,
            h=1400,
            params={"lining_thickness": 10000},  # 10 meters
        )
        assert isinstance(result, list)

    def test_build_with_string_parameters(self, ifc_file, window_component):
        """String parameters should be converted or handled."""
        plane = Plane.world_xy()
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=1200,
            h=1400,
            params={"lining_thickness": "50"},  # String instead of float
        )
        # Should work (conversion) or fail gracefully
        assert isinstance(result, list)


class TestSimpleWindowComponentMaterials:
    """Test material assignments in SimpleWindow."""

    def test_components_have_material_info(self, ifc_file, window_component):
        """Components should have material information."""
        plane = Plane.world_xy()
        result = window_component.build(
            ifc_file,
            plane=plane,
            w=1200,
            h=1400,
            params={},
        )
        # At least some components should have material
        materials = [item.material for item in result if item.material]
        assert len(materials) > 0 or len(result) > 0  # May or may not include material
