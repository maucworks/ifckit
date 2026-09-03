"""Tests voor ils/common vocabularies."""

from ifckit.ils.common import BEPALINGSMETHODEN, ORIENTATIES, GEBRUIKSBESTEMMINGEN, load_data
from ifckit.ils.common import is_valid_bepalingsmethode, is_valid_orientatie


def test_bepalingsmethoden():
    assert "BI" in BEPALINGSMETHODEN
    assert "NVO" in BEPALINGSMETHODEN
    assert len(BEPALINGSMETHODEN) == 8
    assert is_valid_bepalingsmethode("GO")
    assert not is_valid_bepalingsmethode("XXX")


def test_orientaties():
    assert ORIENTATIES == ["Noord", "Noordoost", "Oost", "Zuidoost", "Zuid", "Zuidwest", "West", "Noordwest"]
    assert is_valid_orientatie("Noord")


def test_gebruiksbestemmingen():
    assert "Woonfunctie" in GEBRUIKSBESTEMMINGEN
    assert len(GEBRUIKSBESTEMMINGEN) == 24


def test_begrippen():
    d = load_data("begrippen.json")
    assert len(d["items"]) == 43
    assert any(x["begrip"] == "Bouwwerk" for x in d["items"])


def test_load_unknown():
    assert load_data("nonexistent.json")["items"] == []
