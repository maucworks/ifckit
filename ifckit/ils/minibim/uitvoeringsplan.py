# This file was generated with the assistance of an AI coding tool.
"""ifckit.ils.minibim.uitvoeringsplan — SO/VO/DO fase-matrix."""

from __future__ import annotations

import json
import pathlib

_DATA = pathlib.Path(__file__).parent / "data" / "uitvoeringsplan_raw.json"

FASEN = ["SO", "VO", "DO"]


def _raw() -> dict:
    if not _DATA.exists():
        return {"headers": {}, "rows": []}
    with open(_DATA, encoding="utf-8") as f:
        return json.load(f)


def load_raw() -> dict:
    """Ruwe boolean matrix zoals uit deel B geëxtraheerd (headers deels incompleet in openpyxl)."""
    return _raw()


def headers() -> dict:
    return _raw().get("headers", {})


def rows() -> list[dict]:
    """Lijst van rijen met Onderdeel/Type_Soort en booleans per kolom-index."""
    return _raw().get("rows", [])


def get_row(type_soort: str, onderdeel: str = "") -> dict | None:
    """Zoek rij op type_soort (en optioneel onderdeel)."""
    for r in rows():
        if r.get("type_soort") == type_soort:
            if not onderdeel or r.get("onderdeel") == onderdeel or not r.get("onderdeel"):
                # bij lege onderdeel-rijen (de meeste) match op type alleen
                if r.get("type_soort") == type_soort:
                    return r
    return None


def is_required(onderdeel: str, type_soort: str, col: int) -> bool | None:
    """
    Vraag of een cel True is. *col* is kolom-index (25-41, overeenkomend met
    openpyxl kolommen Y-AO). Mapping naar fase/property vereist handmatige
    verificatie uit PDF — zie uitvoeringsplan_raw.json opmerking.
    """
    row = get_row(type_soort, onderdeel)
    if row is None:
        return None
    bools = row.get("bools", {})
    # JSON keys zijn strings
    return bools.get(str(col), bools.get(col))  # type: ignore[arg-type]


def required_cols(type_soort: str, onderdeel: str = "") -> list[int]:
    """Lijst van kolom-indices waar de cel True is voor dit type."""
    row = get_row(type_soort, onderdeel)
    if not row:
        return []
    return sorted(int(k) for k, v in row.get("bools", {}).items() if v)
