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


def is_required(onderdeel: str, type_soort: str, col: int) -> bool | None:
    """
    Vraag of een cel True is. *col* is kolom-index (25-41, overeenkomend met
    openpyxl kolommen Y-AO). Mapping naar fase/property vereist handmatige
    verificatie uit PDF — zie uitvoeringsplan_raw.json opmerking.
    """
    for r in rows():
        if r.get("onderdeel") == onderdeel and r.get("type_soort") == type_soort:
            return r.get("bools", {}).get(str(col))  # note: json keys are strings
        # also search where onderdeel is empty and type matches
        if not r.get("onderdeel") and r.get("type_soort") == type_soort and not onderdeel:
            return r.get("bools", {}).get(str(col))
    return None
