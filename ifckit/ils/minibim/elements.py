# This file was generated with the assistance of an AI coding tool.
"""ifckit.ils.minibim.elements — Elementen-schema (IfcEntityClass, NL-SfB, afmeting)."""

import json
import pathlib

_DATA = pathlib.Path(__file__).parent / "data" / "elementen.json"


def load_elements() -> list[dict]:
    if not _DATA.exists():
        return []
    with open(_DATA, encoding="utf-8") as f:
        d = json.load(f)
        return d.get("items", [])
