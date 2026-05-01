"""
Tests for ifckit JSON schema and build function.
"""

import json
import os
import tempfile

import pytest

from ifckit import build, build_from_json, validate_json, PendingWall, Vec, Plane


class TestValidateJson:
    """Tests for JSON schema validation."""

    def test_valid_minimal_json(self):
        data = {
            "ifc_version": "IFC4",
            "project": {"name": "Test"},
            "unit": "METRE",
            "buildings": [],
        }
        result = validate_json(data)
        assert result.ok is True
        assert result.errors == []

    def test_missing_ifc_version(self):
        data = {"project": {"name": "Test"}, "unit": "METRE", "buildings": []}
        result = validate_json(data)
        assert result.ok is False
        assert any("ifc_version" in e for e in result.errors)

    def test_invalid_ifc_version(self):
        data = {
            "ifc_version": "IFC2X",
            "project": {"name": "Test"},
            "unit": "METRE",
            "buildings": [],
        }
        result = validate_json(data)
        assert result.ok is False

    def test_valid_ifc2x3_version(self):
        data = {
            "ifc_version": "IFC2X3",
            "project": {"name": "Test"},
            "unit": "METRE",
            "buildings": [],
        }
        result = validate_json(data)
        assert result.ok is True

    def test_missing_project(self):
        data = {"ifc_version": "IFC4", "unit": "METRE", "buildings": []}
        result = validate_json(data)
        assert result.ok is False

    def test_missing_unit(self):
        data = {"ifc_version": "IFC4", "project": {"name": "Test"}, "buildings": []}
        result = validate_json(data)
        assert result.ok is False

    def test_valid_full_json(self):
        data = {
            "ifc_version": "IFC4",
            "project": {"name": "Test Project", "author": "Test Author"},
            "unit": "MILLIMETRE",
            "site": {"name": "Test Site"},
            "buildings": [
                {
                    "name": "Building 1",
                    "storeys": [
                        {
                            "name": "Ground Floor",
                            "elevation": 0.0,
                            "elements": [
                                {
                                    "type": "basic_wall",
                                    "data": {
                                        "type": "basic_wall",
                                        "name": "Wall 1",
                                        "footprint": [[0, 0, 0], [1000, 0, 0], [1000, 200, 0], [0, 200, 0]],
                                        "height": 3000,
                                        "plane": {
                                            "origin": {"x": 0, "y": 0, "z": 0},
                                            "x_axis": {"x": 1, "y": 0, "z": 0},
                                            "y_axis": {"x": 0, "y": 1, "z": 0},
                                        },
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        result = validate_json(data)
        assert result.ok is True

    def test_invalid_building_missing_name(self):
        data = {
            "ifc_version": "IFC4",
            "project": {"name": "Test"},
            "unit": "METRE",
            "buildings": [{"storeys": []}],
        }
        result = validate_json(data)
        assert result.ok is False


class TestBuild:
    """Tests for building IfcModel from JSON."""

    def test_build_minimal(self):
        data = {
            "ifc_version": "IFC4",
            "project": {"name": "Test"},
            "unit": "METRE",
            "site": {"name": "Site"},
            "buildings": [{"name": "Bldg", "storeys": []}],
        }
        model = build(data)
        assert model is not None
        assert model.name == "Test"

    def test_build_with_wall(self, tmp_path):
        data = {
            "ifc_version": "IFC4",
            "project": {"name": "Test"},
            "unit": "MILLIMETRE",
            "site": {"name": "Site"},
            "buildings": [
                {
                    "name": "Bldg",
                    "storeys": [
                        {
                            "name": "GF",
                            "elevation": 0.0,
                            "elements": [
                                {
                                    "type": "basic_wall",
                                    "data": {
                                        "type": "basic_wall",
                                        "name": "Wall1",
                                        "footprint": [[0, 0, 0], [1000, 0, 0], [1000, 200, 0], [0, 200, 0]],
                                        "height": 3000,
                                        "plane": {
                                            "origin": {"x": 0, "y": 0, "z": 0},
                                            "x_axis": {"x": 1, "y": 0, "z": 0},
                                            "y_axis": {"x": 0, "y": 1, "z": 0},
                                        },
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        output_path = str(tmp_path / "test.ifc")
        model = build(data, output_path)
        assert os.path.exists(output_path)

    def test_build_with_beam(self, tmp_path):
        data = {
            "ifc_version": "IFC4",
            "project": {"name": "Test"},
            "unit": "MILLIMETRE",
            "site": {"name": "Site"},
            "buildings": [
                {
                    "name": "Bldg",
                    "storeys": [
                        {
                            "name": "GF",
                            "elevation": 0.0,
                            "elements": [
                                {
                                    "type": "beam",
                                    "data": {
                                        "type": "basic_beam",
                                        "name": "Beam1",
                                        "axis": {"start": [0, 0, 2500], "end": [5000, 0, 2500]},
                                        "profile": [[-100, 0, 0], [100, 0, 0], [100, 300, 0], [-100, 300, 0]],
                                        "up": [0, 0, 1],
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        output_path = str(tmp_path / "test.ifc")
        model = build(data, output_path)
        assert os.path.exists(output_path)

    def test_build_multiple_storeys(self, tmp_path):
        data = {
            "ifc_version": "IFC4",
            "project": {"name": "Test"},
            "unit": "MILLIMETRE",
            "site": {"name": "Site"},
            "buildings": [
                {
                    "name": "Bldg",
                    "storeys": [
                        {
                            "name": "GF",
                            "elevation": 0.0,
                            "elements": [
                                {
                                    "type": "basic_wall",
                                    "data": {
                                        "type": "basic_wall",
                                        "name": "Wall GF",
                                        "footprint": [[0, 0, 0], [1000, 0, 0], [1000, 200, 0], [0, 200, 0]],
                                        "height": 3000,
                                        "plane": {
                                            "origin": {"x": 0, "y": 0, "z": 0},
                                            "x_axis": {"x": 1, "y": 0, "z": 0},
                                            "y_axis": {"x": 0, "y": 1, "z": 0},
                                        },
                                    },
                                }
                            ],
                        },
                        {
                            "name": "F1",
                            "elevation": 3000.0,
                            "elements": [
                                {
                                    "type": "basic_wall",
                                    "data": {
                                        "type": "basic_wall",
                                        "name": "Wall F1",
                                        "footprint": [[0, 0, 0], [1000, 0, 0], [1000, 200, 0], [0, 200, 0]],
                                        "height": 2800,
                                        "plane": {
                                            "origin": {"x": 0, "y": 0, "z": 3000},
                                            "x_axis": {"x": 1, "y": 0, "z": 0},
                                            "y_axis": {"x": 0, "y": 1, "z": 0},
                                        },
                                    },
                                }
                            ],
                        },
                    ],
                }
            ],
        }
        output_path = str(tmp_path / "test.ifc")
        model = build(data, output_path)
        assert os.path.exists(output_path)

    def test_build_invalid_json_raises(self):
        data = {"ifc_version": "INVALID", "project": {"name": "Test"}, "unit": "METRE", "buildings": []}
        with pytest.raises(ValueError, match="Invalid JSON"):
            build(data)

    def test_build_ifc2x3(self, tmp_path):
        data = {
            "ifc_version": "IFC2X3",
            "project": {"name": "Legacy", "author": "pytest"},
            "unit": "METRE",
            "site": {"name": "Site"},
            "buildings": [{"name": "Bldg", "storeys": [{"name": "L0", "elements": []}]}],
        }
        model = build(data)
        assert model is not None
        assert model.schema.value == "IFC2X3"
        assert "IFC2X3" in model.to_string().upper()


class TestBuildFromJson:
    """Tests for build_from_json function."""

    def test_from_json_string(self, tmp_path):
        data = {
            "ifc_version": "IFC4",
            "project": {"name": "Test"},
            "unit": "METRE",
            "site": {"name": "Site"},
            "buildings": [{"name": "Bldg", "storeys": []}],
        }
        json_str = json.dumps(data)
        output_path = str(tmp_path / "test.ifc")
        model = build_from_json(json_str, output_path)
        assert model is not None
        assert os.path.exists(output_path)


class TestPendingElementSerialization:
    """Tests for to_json/from_json convenience methods."""

    def test_wall_to_json(self):
        wall = PendingWall(
            footprint=[Vec(0, 0, 0), Vec(1000, 0, 0), Vec(1000, 200, 0), Vec(0, 200, 0)],
            plane=Plane.world_xy(),
            height=3000,
            name="Wall1",
        )
        json_str = wall.to_json()
        parsed = json.loads(json_str)
        assert parsed["type"] == "basic_wall"
        assert parsed["name"] == "Wall1"

    def test_wall_from_json(self):
        wall = PendingWall(
            footprint=[Vec(0, 0, 0), Vec(1000, 0, 0), Vec(1000, 200, 0), Vec(0, 200, 0)],
            plane=Plane.world_xy(),
            height=3000,
            name="Wall1",
        )
        json_str = wall.to_json()
        wall2 = PendingWall.from_json(json_str)
        assert wall2.name == "Wall1"
        assert wall2.height == 3000
        assert len(wall2.footprint) == 4

    def test_from_json_unknown_type_raises(self):
        with pytest.raises(KeyError, match="unknown_type"):
            PendingWall.from_json('{"type": "unknown_type"}')


class TestExampleJsonFile:
    """Test the example JSON file."""

    def test_example_json_validates(self):
        example_path = os.path.join(os.path.dirname(__file__), "..", "examples", "example_building.json")
        if os.path.exists(example_path):
            with open(example_path) as f:
                data = json.load(f)
            result = validate_json(data)
            assert result.ok is True
        else:
            pytest.skip("Example file not found")

    def test_example_json_builds(self, tmp_path):
        example_path = os.path.join(os.path.dirname(__file__), "..", "examples", "example_building.json")
        if os.path.exists(example_path):
            with open(example_path) as f:
                data = json.load(f)
            output_path = str(tmp_path / "example.ifc")
            model = build(data, output_path)
            assert os.path.exists(output_path)
        else:
            pytest.skip("Example file not found")


class TestFlatJsonFormat:
    """Test the flat element format: {"type": "...", <fields>} without a "data" key."""

    def test_flat_wall_format_builds(self, tmp_path):
        """Elements described without a nested 'data' dict must build successfully."""
        data = {
            "ifc_version": "IFC4",
            "project": {"name": "FlatTest"},
            "unit": "METRE",
            "site": {"name": "Site"},
            "buildings": [
                {
                    "name": "Building",
                    "storeys": [
                        {
                            "name": "GF",
                            "elevation": 0.0,
                            "elements": [
                                {
                                    "type": "basic_wall",
                                    "footprint": [
                                        [0.0, 0.0, 0.0],
                                        [5.0, 0.0, 0.0],
                                        [5.0, 0.2, 0.0],
                                        [0.0, 0.2, 0.0],
                                    ],
                                    "height": 3.0,
                                    "plane": {
                                        "origin": {"x": 0.0, "y": 0.0, "z": 0.0},
                                        "x_axis": {"x": 1.0, "y": 0.0, "z": 0.0},
                                        "y_axis": {"x": 0.0, "y": 1.0, "z": 0.0},
                                    },
                                    "name": "W1",
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        output_path = str(tmp_path / "flat.ifc")
        build(data, output_path)
        import os
        assert os.path.exists(output_path)

    def test_nested_data_format_builds(self, tmp_path):
        """Nested {'type': ..., 'data': {...}} format must also build successfully."""
        wall_fields = {
            "footprint": [
                [0.0, 0.0, 0.0],
                [5.0, 0.0, 0.0],
                [5.0, 0.2, 0.0],
                [0.0, 0.2, 0.0],
            ],
            "height": 3.0,
            "plane": {
                "origin": {"x": 0.0, "y": 0.0, "z": 0.0},
                "x_axis": {"x": 1.0, "y": 0.0, "z": 0.0},
                "y_axis": {"x": 0.0, "y": 1.0, "z": 0.0},
            },
            "name": "W1",
        }
        data = {
            "ifc_version": "IFC4",
            "project": {"name": "NestedTest"},
            "unit": "METRE",
            "site": {"name": "Site"},
            "buildings": [
                {
                    "name": "Building",
                    "storeys": [
                        {
                            "name": "GF",
                            "elevation": 0.0,
                            "elements": [{"type": "basic_wall", "data": wall_fields}],
                        }
                    ],
                }
            ],
        }
        output_path = str(tmp_path / "nested.ifc")
        build(data, output_path)
        import os
        assert os.path.exists(output_path)