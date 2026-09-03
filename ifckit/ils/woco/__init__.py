# This file was generated with the assistance of an AI coding tool.
"""ifckit.ils.woco — ILS-woco 3.1 domeinlaag (Aedes)."""

from __future__ import annotations

import json
import pathlib

from ._version import ILS_NAME, ILS_VERSION

_DATA = pathlib.Path(__file__).parent / "data"


def _load(name: str) -> dict:
    p = _DATA / name
    if not p.exists():
        return {"_meta": {}, "items": []}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _codes(name: str) -> list[str]:
    d = _load(name)
    return [x["code"] for x in d.get("items", [])]


# Vocabularies
RUIMTE_SOORTEN = _codes("ruimtesoort.json")
RUIMTETYPES_RUIMTE = _codes("ruimtetype_ruimte.json")
RUIMTETYPES_SUBRUIMTE = _codes("ruimtetype_subruimte.json")
RUIMTETYPES_BUITEN = _codes("ruimtetype_buitenruimte.json")
GEBIED_SOORTEN = _codes("gebiedssoort.json")
GEBRUIKSBESTEMMINGEN = _codes("gebruiksbestemming.json")
ORIENTATIES = _codes("orientatie.json")
BEPALINGSMETHODEN = _codes("bepalingsmethode.json")
TOEGANGEN = _codes("toegang.json")

# Hergebruik common waar mogelijk (BBL, NEN2580)
try:
    from ifckit.ils.common import GEBRUIKSBESTEMMINGEN as _COMMON_GEBR  # noqa
except Exception:
    pass


def is_valid_ruimtetype(code: str, kind: str = "ruimte") -> bool:
    if kind == "ruimte":
        return code in RUIMTETYPES_RUIMTE
    if kind == "subruimte":
        return code in RUIMTETYPES_SUBRUIMTE
    if kind == "buitenruimte":
        return code in RUIMTETYPES_BUITEN
    return code in RUIMTETYPES_RUIMTE + RUIMTETYPES_SUBRUIMTE + RUIMTETYPES_BUITEN


def load_bsdd_classes() -> list[dict]:
    return _load("bsdd_classes.json").get("items", [])


def load_parameters() -> list[dict]:
    return _load("parameters.json").get("items", [])


class WocoSpec:
    """Toegang tot ILS-woco vocabularies en validatie."""

    version = ILS_VERSION
    name = ILS_NAME

    def validate_ruimtetype(self, code: str, kind: str = "ruimte") -> bool:
        return is_valid_ruimtetype(code, kind)

    def load(self, name: str) -> dict:
        return _load(name)


__all__ = [
    "ILS_VERSION",
    "ILS_NAME",
    "WocoSpec",
    "is_valid_ruimtetype",
    "load_bsdd_classes",
    "load_parameters",
    "RUIMTE_SOORTEN",
    "RUIMTETYPES_RUIMTE",
    "RUIMTETYPES_SUBRUIMTE",
    "RUIMTETYPES_BUITEN",
    "GEBIED_SOORTEN",
    "GEBRUIKSBESTEMMINGEN",
    "ORIENTATIES",
    "BEPALINGSMETHODEN",
]
