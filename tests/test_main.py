import json
import sys
from io import StringIO

import pytest

from ifckit.__main__ import handle_build


class FakeArgs:
    def __init__(self, input, output, validate_only=False):
        self.input = input
        self.output = output
        self.validate_only = validate_only


class TestHandleBuild:
    def test_missing_input_file(self, capsys):
        result = handle_build(FakeArgs("nonexistent.json", "out.ifc"))
        assert result == 1
        captured = capsys.readouterr()
        assert "Input file not found" in captured.err

    def test_invalid_json_from_str(self, capsys):
        sys.stdin = StringIO("not json")
        try:
            result = handle_build(FakeArgs("-", "out.ifc"))
            assert result == 1
            captured = capsys.readouterr()
            assert "Invalid JSON" in captured.err
        finally:
            sys.stdin = sys.__stdin__

    def test_validate_only_valid_json(self, capsys, tmp_path):
        inp = tmp_path / "valid.json"
        data = {"ifc_version": "IFC4", "project": {"name": "Test"}, "unit": "METRE", "elements": []}
        inp.write_text(json.dumps(data))
        result = handle_build(FakeArgs(str(inp), "out.ifc", validate_only=True))
        assert result == 0
        captured = capsys.readouterr()
        assert "JSON is valid" in captured.out

    def test_build_valid(self, capsys, tmp_path):
        data = {
            "ifc_version": "IFC4",
            "project": {"name": "Test"},
            "unit": "METRE",
            "elements": [
                {
                    "type": "basic_wall",
                    "name": "W1",
                    "axis": {"start": [0, 0, 0], "end": [5000, 0, 0]},
                    "profile": [{"x": -100, "y": -1500}, {"x": 100, "y": -1500}, {"x": 100, "y": 0}, {"x": -100, "y": 0}],
                    "height": 3000,
                    "storey": "L0",
                }
            ],
            "buildings": [{"name": "B1", "storeys": [{"name": "L0"}]}],
        }
        inp = tmp_path / "wall.json"
        inp.write_text(json.dumps(data))
        output = str(tmp_path / "out.ifc")
        result = handle_build(FakeArgs(str(inp), output))
        assert result == 0
        captured = capsys.readouterr()
        assert "Successfully created" in captured.out
