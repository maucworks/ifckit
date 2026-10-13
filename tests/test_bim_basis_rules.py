# This file was generated with the assistance of an AI coding tool.
"""Tests for the BIM Basis validation rules (tiles 3.1 + 3.3)."""

from ifckit.ils.common.rules.bim_basis import (
    check_filename,
    check_storey_name,
    format_storey_name,
)


def test_check_filename_valid():
    assert check_filename("PRJ-ARC-01.ifc") == []
    assert check_filename("196-ifckit-admin_ARC_SO.ifc") == []


def test_check_filename_space():
    assert any("spaces" in e for e in check_filename("my model.ifc"))


def test_check_filename_not_ifc():
    assert any(".ifc" in e for e in check_filename("model.pdf"))


def test_check_filename_no_structure():
    # "model.ifc" without _ or - violates tile 3.1
    assert any("structure" in e for e in check_filename("model.ifc"))


def test_format_storey_name():
    assert format_storey_name(0, "Begane grond") == "00 Begane grond"
    assert format_storey_name(1, "Verdieping", "A") == "01 Verdieping A"


def test_check_storey_name_valid():
    assert check_storey_name("00 Begane grond") == []
    assert check_storey_name("01 Eerste verdieping") == []


def test_check_storey_name_invalid():
    assert check_storey_name("") != []
    assert check_storey_name("Begane grond") != []  # missing number
    assert check_storey_name("1 Begane grond") != []  # must be two digits
