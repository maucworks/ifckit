# This file was generated with the assistance of an AI coding tool.
"""ifckit.ils.minibim — MiniBIM ILS v3.1 domeinlaag."""

from __future__ import annotations

import json
import pathlib
from typing import Any

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


# Vocabularies (voor validatie / import door gebruikers)
TERREIN_TYPES = _codes("terrein_types.json")
BOUWWERK_TYPES = _codes("bouwwerk_types.json")
GEBIED_SOORTEN = _codes("gebied_soorten.json")
GEBIED_TYPES = _codes("gebied_types.json")
RUIMTE_SOORTEN = _codes("ruimte_soorten.json")
RUIMTE_TYPES = _codes("ruimte_types.json")
BUITENRUIMTE_SOORTEN = _codes("buitenruimte_soorten.json")
BUITENRUIMTE_TYPES = _codes("buitenruimte_types.json")
AFNEMERS = _codes("afnemers.json")
SEGMENTEN = _codes("segmenten.json")
PROGRAMMAS = _codes("programmas.json")
WONING_TYPES = _codes("woning_types.json")

# Re-export common waar MiniBIM op steunt (via common, maar hier voor gemak)
try:
    from ifckit.ils.common import (  # type: ignore
        BEPALINGSMETHODEN,
        GEBRUIKSBESTEMMINGEN,
        ORIENTATIES,
    )
except Exception:  # common nog niet geïnstalleerd in editable zonder src
    BEPALINGSMETHODEN: list[str] = []
    ORIENTATIES: list[str] = []
    GEBRUIKSBESTEMMINGEN: list[str] = []


# Validatie-helpers
def is_valid_ruimte_type(code: str) -> bool:
    return code in RUIMTE_TYPES


def is_valid_gebied_type(code: str) -> bool:
    return code in GEBIED_TYPES


def is_valid_bouwwerk_type(code: str) -> bool:
    return code in BOUWWERK_TYPES


# Pset helper (alleen publieke core-API)
def apply_minibim_pset(element: Any, ifc_file: Any, **props: Any) -> None:
    """
    Schrijf MiniBIM ILS pset op *element*.

    Voorbeeld::

        from ifckit.ils.minibim import apply_minibim_pset
        apply_minibim_pset(space_entity, ifc_file, RuimteType="Slaapkamer", Bepalingsmethode="NVO")
    """
    from ifckit.builders.psets import write_named_pset

    # Filter alleen bekende MiniBIM-params (voorkom typo-psets)
    filtered = {k: v for k, v in props.items() if v not in (None, "")}
    if not filtered:
        return
    write_named_pset(ifc_file, element, ILS_NAME, filtered)


class MiniBimSpec:
    """Toegang tot MiniBIM vocabularies en validatie."""

    version = ILS_VERSION
    name = ILS_NAME

    def validate_ruimtetype(self, code: str) -> bool:
        return is_valid_ruimte_type(code)

    def validate_gebiedtype(self, code: str) -> bool:
        return is_valid_gebied_type(code)

    def load(self, name: str) -> dict:
        return _load(name)


def group_zones(model_or_file: Any, by: str = "EenheidNummer") -> list:
    """Groepeer IfcSpace op een MiniBIM ILS property (bv. EenheidNummer) via IfcZone."""
    from .zones import group_zones as _gz

    return _gz(model_or_file, by=by)


__all__ = [
    "ILS_VERSION",
    "ILS_NAME",
    "MiniBimSpec",
    "apply_minibim_pset",
    "group_zones",
    "is_valid_ruimte_type",
    "is_valid_gebied_type",
    "is_valid_bouwwerk_type",
    "TERREIN_TYPES",
    "BOUWWERK_TYPES",
    "GEBIED_SOORTEN",
    "GEBIED_TYPES",
    "RUIMTE_SOORTEN",
    "RUIMTE_TYPES",
    "BUITENRUIMTE_SOORTEN",
    "BUITENRUIMTE_TYPES",
    "AFNEMERS",
    "SEGMENTEN",
    "PROGRAMMAS",
    "WONING_TYPES",
    "BEPALINGSMETHODEN",
    "ORIENTATIES",
    "GEBRUIKSBESTEMMINGEN",
]
