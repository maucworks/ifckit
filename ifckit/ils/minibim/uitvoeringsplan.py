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
    """Raw boolean matrix as extracted from part B (partially incomplete in openpyxl)."""
    return _raw()


def headers() -> dict:
    return _raw().get("headers", {})


def rows() -> list[dict]:
    """List of rows with Onderdeel/Type_Soort and booleans per column index."""
    return _raw().get("rows", [])


def get_row(type_soort: str, onderdeel: str = "") -> dict | None:
    """Look up a row by type_soort (and optionally onderdeel)."""
    for r in rows():
        if r.get("type_soort") == type_soort:
            if not onderdeel or r.get("onderdeel") == onderdeel or not r.get("onderdeel"):
                # empty onderdeel rows (the majority) match on type only
                if r.get("type_soort") == type_soort:
                    return r
    return None


def is_required(onderdeel: str, type_soort: str, col: int) -> bool | None:
    """
    Query whether a cell is True. *col* is the column index (25-41,
    matching openpyxl columns Y-AO). Mapping to phase/property requires
    manual PDF verification — see the note in uitvoeringsplan_raw.json.
    """
    row = get_row(type_soort, onderdeel)
    if row is None:
        return None
    bools = row.get("bools", {})
    # JSON keys are strings
    return bools.get(str(col), bools.get(col))  # type: ignore[arg-type]


def required_cols(type_soort: str, onderdeel: str = "") -> list[int]:
    """List of column indices where the cell is True for this type."""
    row = get_row(type_soort, onderdeel)
    if not row:
        return []
    return sorted(int(k) for k, v in row.get("bools", {}).items() if v)
