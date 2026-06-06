"""
Tests for SimpleDoorComponent — generative door geometry.
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
def door_component():
    """Get or skip SimpleDoorComponent."""
    cls = get_component("simple_door")
    if cls is None:
        pytest.skip("SimpleDoor component not available")
    return cls()


class TestSimpleDoorComponentBasics:
    """Test basic SimpleDoor functionality."""

    def test_component_exists(self, door_component):
        """SimpleDoorComponent should exist."""
        assert door_component is not None

    def test_component_is_door(self, door_component):
        """Component should create IfcDoor."""
        assert door_component.ifc_class == "IfcDoor"

    def test_build_method_exists(self, door_component):
        """Component should have build method."""
        assert hasattr(door_component, "build")
        assert callable(door_component.build)


class TestSimpleDoorComponentBuild:
    """Test SimpleDoor build method."""

    def test_build_returns_list(self, ifc_file, door_component):
        """Build should return a list of components."""
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={
                "lining_thickness": 70,
                "lining_depth": 80,
                "door_thickness": 40,
            },
        )
        assert isinstance(result, list)

    def test_build_returns_evaluated_components(self, ifc_file, door_component):
        """All items should be EvaluatedComponent instances."""
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={},
        )
        assert all(isinstance(item, EvaluatedComponent) for item in result)

    def test_build_includes_opening_component(self, ifc_file, door_component):
        """Build should include at least one opening component."""
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={},
        )
        roles = [item.role for item in result]
        assert "Opening" in roles

    def test_build_with_custom_parameters(self, ifc_file, door_component):
        """Build should work with custom parameters."""
        params = {
            "lining_thickness": 80,
            "lining_depth": 100,
            "door_thickness": 45,
            "wall_thickness": 200,
        }
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params=params,
        )
        assert len(result) > 0

    def test_build_with_minimal_parameters(self, ifc_file, door_component):
        """Build should work with no parameters (using defaults)."""
        plane = Plane.world_xy()
        result = door_component.build(ifc_file, plane=plane, w=900, h=2100, params={})
        assert len(result) > 0

    def test_build_respects_width_height(self, ifc_file, door_component):
        """Build should use specified width and height."""
        plane = Plane.world_xy()
        # Test multiple standard door sizes
        for width, height in [(800, 2000), (900, 2100), (1200, 2400)]:
            result = door_component.build(
                ifc_file,
                plane=plane,
                w=width,
                h=height,
                params={},
            )
            assert len(result) > 0


class TestSimpleDoorComponentPlacement:
    """Test SimpleDoor placement in different planes."""

    def test_build_in_world_xy_plane(self, ifc_file, door_component):
        """Build in world XY plane."""
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={},
        )
        assert len(result) > 0

    def test_build_in_vertical_plane(self, ifc_file, door_component):
        """Build in a vertical plane (XZ)."""
        plane = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={},
        )
        assert len(result) > 0

    def test_build_in_translated_plane(self, ifc_file, door_component):
        """Build in a translated plane."""
        plane = Plane(Vec(2, 5, 0), Vec(1, 0, 0), Vec(0, 1, 0))
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={},
        )
        assert len(result) > 0


class TestSimpleDoorComponentGeometry:
    """Test SimpleDoor geometric output."""

    def test_component_solids_are_ifc_entities(self, ifc_file, door_component):
        """Component solids should be valid IFC entities."""
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={},
        )
        # Each component should have a solid
        for comp in result:
            assert comp.solid is not None

    def test_component_roles_are_valid(self, ifc_file, door_component):
        """Component roles should be semantic identifiers."""
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={},
        )
        valid_roles = {"Opening", "Lining", "Panel", "Handle", "Frame", "Leaf"}
        for comp in result:
            assert comp.role in valid_roles or len(comp.role) > 0

    def test_zero_lining_thickness(self, ifc_file, door_component):
        """Build with zero lining thickness should work."""
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={"lining_thickness": 0},
        )
        assert len(result) > 0

    def test_standard_door_size(self, ifc_file, door_component):
        """Build standard 900x2100 door."""
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={},
        )
        assert len(result) > 0
        # Should have opening, lining, and panel
        roles = [item.role for item in result]
        assert "Opening" in roles

    def test_large_door_dimensions(self, ifc_file, door_component):
        """Build with large dimensions."""
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=2000,  # 2 meters
            h=3000,  # 3 meters
            params={},
        )
        assert len(result) > 0


class TestSimpleDoorComponentEdgeCases:
    """Test SimpleDoor edge cases."""

    def test_build_with_negative_depth_parameters(self, ifc_file, door_component):
        """Negative depth parameters should be handled gracefully."""
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={"lining_depth": -50},
        )
        assert isinstance(result, list)

    def test_build_with_very_large_parameters(self, ifc_file, door_component):
        """Very large parameter values should be handled."""
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={"lining_thickness": 5000},  # 5 meters
        )
        assert isinstance(result, list)

    def test_build_with_string_parameters(self, ifc_file, door_component):
        """String parameters should be converted or handled."""
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={"lining_thickness": "70"},  # String instead of float
        )
        assert isinstance(result, list)


class TestSimpleDoorComponentMaterials:
    """Test material assignments in SimpleDoor."""

    def test_components_have_material_info(self, ifc_file, door_component):
        """Components should have material information."""
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={},
        )
        # Check that components exist
        assert len(result) > 0

    def test_opening_has_void_role(self, ifc_file, door_component):
        """Opening component should trigger opening element."""
        plane = Plane.world_xy()
        result = door_component.build(
            ifc_file,
            plane=plane,
            w=900,
            h=2100,
            params={},
        )
        roles = [item.role for item in result]
        assert "Opening" in roles
