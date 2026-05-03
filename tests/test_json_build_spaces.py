"""Tests for spaces[] in json_build."""
import pytest
from ifckit.json_build import build


BASE = {
    "ifc_version": "IFC4",
    "project": {"name": "SpaceTest"},
    "unit": "METRE",
    "buildings": [
        {
            "name": "B1",
            "storeys": [
                {
                    "name": "Ground Floor",
                    "elevation": 0.0,
                    "elements": [],
                    "spaces": [
                        {
                            "name": "1.01",
                            "long_name": "Reception",
                            "height": 3.0,
                            "footprint": [
                                [0, 0, 0], [6, 0, 0], [6, 4, 0], [0, 4, 0]
                            ],
                        }
                    ],
                }
            ],
        }
    ],
}


def test_build_with_spaces():
    model = build(BASE)
    spaces = model.ifc_file.by_type("IfcSpace")
    assert len(spaces) == 1
    assert spaces[0].Name == "1.01"
    assert spaces[0].LongName == "Reception"


def test_build_space_has_representations():
    model = build(BASE)
    space = model.ifc_file.by_type("IfcSpace")[0]
    assert space.Representation is not None
    identifiers = {r.RepresentationIdentifier
                   for r in space.Representation.Representations}
    assert "Body" in identifiers
    assert "FootPrint" in identifiers


def test_build_space_aggregated():
    model = build(BASE)
    rels = model.ifc_file.by_type("IfcRelAggregates")
    space_rels = [
        r for r in rels
        if any(p.is_a("IfcSpace") for p in r.RelatedObjects)
    ]
    assert len(space_rels) >= 1


def test_build_multiple_spaces():
    data = {
        "ifc_version": "IFC4",
        "project": {"name": "MultiSpace"},
        "unit": "METRE",
        "buildings": [
            {
                "name": "B",
                "storeys": [
                    {
                        "name": "L0",
                        "spaces": [
                            {"name": "1.01", "height": 3.0,
                             "footprint": [[0,0,0],[4,0,0],[4,4,0],[0,4,0]]},
                            {"name": "1.02", "height": 3.0,
                             "footprint": [[4,0,0],[8,0,0],[8,4,0],[4,4,0]]},
                        ],
                    }
                ],
            }
        ],
    }
    model = build(data)
    spaces = model.ifc_file.by_type("IfcSpace")
    assert len(spaces) == 2
    names = {s.Name for s in spaces}
    assert names == {"1.01", "1.02"}


def test_build_space_with_hatch_pattern():
    data = {
        "ifc_version": "IFC4",
        "project": {"name": "HP"},
        "unit": "METRE",
        "buildings": [{"name": "B", "storeys": [{
            "name": "L0",
            "spaces": [{"name": "R", "height": 2.7,
                        "footprint": [[0,0,0],[3,0,0],[3,3,0],[0,3,0]],
                        "hatch_pattern": "ANSI31"}],
        }]}],
    }
    model = build(data)
    # hatch_pattern written to EPset_IfcKit.HatchPattern pset
    psets = model.ifc_file.by_type("IfcPropertySet")
    ifckit_pset = [p for p in psets if p.Name == "EPset_IfcKit"]
    assert len(ifckit_pset) == 1
    props = {p.Name: p.NominalValue.wrappedValue
             for p in ifckit_pset[0].HasProperties}
    assert props.get("HatchPattern") == "ANSI31"
