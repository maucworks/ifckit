# This file was generated with the assistance of an AI coding tool.
"""ifckit.ils.minibim.pset — MiniBIM ILS pset-definitie en writer."""

from __future__ import annotations

from typing import Any

from ._version import ILS_NAME

# MiniBIM ILS pset-parameters (19 stuks, zie deel A)
PARAMS = [
    "Afnemer",
    "Bepalingsmethode",
    "BouwwerkNummer",
    "BouwwerkType",
    "BuitenruimteSoort",
    "BuitenruimteType",
    "EenheidNummer",
    "GebiedsSoort",
    "GebiedsType",
    "Gebruiksbestemming",
    "Glaspercentage",
    "Orientatie",
    "Programma",
    "RuimteNummer",
    "RuimteSoort",
    "RuimteType",
    "Segment",
    "TerreinType",
    "WoningType",
]

PSET_NAME = ILS_NAME


def apply_pset(element: Any, ifc_file: Any, **props: Any) -> None:
    """Schrijf MiniBIM ILS pset (alias voor apply_minibim_pset)."""
    from ifckit.builders.psets import write_named_pset

    filtered = {k: v for k, v in props.items() if v not in (None, "")}
    # alleen bekende params
    filtered = {k: v for k, v in filtered.items() if k in PARAMS}
    if not filtered:
        return
    write_named_pset(ifc_file, element, PSET_NAME, filtered)
