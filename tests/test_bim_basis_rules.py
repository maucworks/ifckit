# This file was generated with the assistance of an AI coding tool.
"""Tests voor BIM Basis validatieregels (tegel 3.1 + 3.3)."""

from ifckit.ils.common.rules.bim_basis import (
    check_bestandsnaam,
    check_storey_naam,
    format_storey_naam,
)


def test_check_bestandsnaam_geldig():
    assert check_bestandsnaam("PRJ-ARC-01.ifc") == []
    assert check_bestandsnaam("196-ifckit-admin_ARC_SO.ifc") == []


def test_check_bestandsnaam_spatie():
    assert any("spatie" in e for e in check_bestandsnaam("my model.ifc"))


def test_check_bestandsnaam_geen_ifc():
    assert any(".ifc" in e for e in check_bestandsnaam("model.pdf"))


def test_check_bestandsnaam_geen_structuur():
    # Enkel "model.ifc" zonder _ of - is tegen tegel 3.1
    assert any("structuur" in e for e in check_bestandsnaam("model.ifc"))


def test_format_storey_naam():
    assert format_storey_naam(0, "Begane grond") == "00 Begane grond"
    assert format_storey_naam(1, "Verdieping", "A") == "01 Verdieping A"


def test_check_storey_naam_geldig():
    assert check_storey_naam("00 Begane grond") == []
    assert check_storey_naam("01 Eerste verdieping") == []


def test_check_storey_naam_ongeldig():
    assert check_storey_naam("") != []
    assert check_storey_naam("Begane grond") != []  # mist nummer
    assert check_storey_naam("1 Begane grond") != []  # moet 2 cijfers
