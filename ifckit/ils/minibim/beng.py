# This file was generated with the assistance of an AI coding tool.
"""ifckit.ils.minibim.beng — BENG gevelwandregels."""

from __future__ import annotations

import json
import pathlib

_DATA = pathlib.Path(__file__).parent / "data" / "beng.json"


def load_beng() -> list[dict]:
    if not _DATA.exists():
        return []
    with open(_DATA, encoding="utf-8") as f:
        return json.load(f).get("items", [])


def by_gebruiksbestemming(code: str) -> list[dict]:
    return [r for r in load_beng() if r.get("Gebruiksbestemming") == code]


def glaspercentages() -> list[str]:
    return [
        r.get("Glaspercentage", "")
        for r in load_beng()
        if r.get("Glaspercentage") not in (None, "")
    ]


# Convenience: alle 11 combinaties (Gebruiksbestemming × Oriëntatie × Glaspercentage)
BENG_ROWS: list[dict] = load_beng()
