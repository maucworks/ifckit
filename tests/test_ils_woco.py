# This file was generated with the assistance of an AI coding tool.
"""Tests voor ils/woco vocabularies."""

from ifckit.ils.woco import RUIMTETYPES_RUIMTE, WocoSpec, is_valid_ruimtetype


def test_ruimtetypes():
    assert len(RUIMTETYPES_RUIMTE) == 48
    assert "Atrium" in RUIMTETYPES_RUIMTE
    assert "Woonkamer" in RUIMTETYPES_RUIMTE
    assert is_valid_ruimtetype("Atrium", "ruimte")
    assert not is_valid_ruimtetype("Onzin", "ruimte")


def test_bsd_classes():
    from ifckit.ils.woco import load_bsdd_classes

    classes = load_bsdd_classes()
    assert len(classes) == 179
    codes = {c["code"] for c in classes}
    assert "BOUWKUNDIGELEMENT" in codes


def test_parameters():
    from ifckit.ils.woco import load_parameters

    params = load_parameters()
    assert len(params) == 76
    codes = {p["property"] for p in params}
    assert "BagPandId" in codes


def test_woco_spec():
    s = WocoSpec()
    assert s.version == "3.1"
    assert s.validate_ruimtetype("Atrium", "ruimte")
