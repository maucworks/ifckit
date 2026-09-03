# This file was generated with the assistance of an AI coding tool.
"""ifckit.ils.common — gedeelde NL-vocabularies (ILS-neutraal)."""

from __future__ import annotations

import json
import pathlib

_DATA = pathlib.Path(__file__).parent / "data"


def _load(name: str) -> dict:
    p = _DATA / name
    if not p.exists():
        return {"_meta": {}, "items": []}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _codes(name: str) -> list[str]:
    d = _load(name)
    # begrippen.json has different shape (list of dicts with 'begrip')
    if name == "begrippen.json":
        return [x["begrip"] for x in d.get("items", [])]
    return [x["code"] for x in d.get("items", [])]


# Publieke vocabularies
BEPALINGSMETHODEN: list[str] = _codes("bepalingsmethoden.json")
ORIENTATIES: list[str] = _codes("orientaties.json")
GEBRUIKSBESTEMMINGEN: list[str] = _codes("gebruiksbestemmingen.json")
NLSFB: list[str] = _codes("nlsfb.json")
NAAKT: list[str] = _codes("naakt.json")

# Laag-niveau helper voor andere ILS'en
def load_data(name: str) -> dict:
    """Laad een data-bestand uit ils/common/data (bv. 'bepalingsmethoden.json')."""
    return _load(name)


def is_valid_bepalingsmethode(code: str) -> bool:
    return code in BEPALINGSMETHODEN


def is_valid_orientatie(code: str) -> bool:
    return code in ORIENTATIES


def is_valid_gebruiksbestemming(code: str) -> bool:
    return code in GEBRUIKSBESTEMMINGEN


__all__ = [
    "BEPALINGSMETHODEN",
    "ORIENTATIES",
    "GEBRUIKSBESTEMMINGEN",
    "NLSFB",
    "NAAKT",
    "load_data",
    "is_valid_bepalingsmethode",
    "is_valid_orientatie",
    "is_valid_gebruiksbestemming",
]
