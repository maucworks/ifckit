# This file was generated with the assistance of an AI coding tool.
"""BIM Basis ILS — validators voor tegel 3.1 (bestandsnaam) en 3.3 (bouwlaag).

Bron: specs/bim-basis/tegels.md (infographic v2 + poster v1.0).
Regels zijn aandachtspunten, geen strikte ILS — validatie is advies, geen reject.
"""

from __future__ import annotations

import re

# 3.1 Bestandsnaam — uniform, consistent per aspectmodel.
# BIM Basis ILS schrijft geen harde regex voor, poster/infographic tonen placeholder
# "<...>_<...>_<...>.ifc". In praktijk: projectcode_discipline_fase.ifc, zonder spaties,
# alleen [A-Za-z0-9_-], eindigend op .ifc. We valideren die pragmatische vorm.
_BESTANDSNAAM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*\.ifc$", re.IGNORECASE)
# Aanbevolen structuur: minimaal 2 delen gescheiden door _ of - (bv. PRJ_ARC_01.ifc)
_BESTANDSNAAM_STRUCT_RE = re.compile(r"^.+[_-].+\.ifc$", re.IGNORECASE)


def check_bestandsnaam(path: str) -> list[str]:
    """
    Valideer bestandsnaam tegen BIM Basis tegel 3.1.

    Retourneert foutmeldingen, leeg bij geldig.
    Voorbeelden geldig: "PRJ-ARC-01.ifc", "196-ifckit-admin_ARC_SO.ifc".
    Voorbeelden ongeldig: "model.ifc" (geen structuur), "my model.ifc" (spatie),
    "model.pdf" (geen .ifc).
    """
    fouten: list[str] = []
    # Alleen basename, geen directory
    name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if not name:
        return ["Lege bestandsnaam."]
    if " " in name:
        fouten.append("Bestandsnaam mag geen spatie bevatten (tegel 3.1).")
    if not _BESTANDSNAAM_RE.match(name):
        fouten.append("Bestandsnaam moet eindigen op .ifc en alleen [A-Za-z0-9_-] bevatten.")
    elif not _BESTANDSNAAM_STRUCT_RE.match(name) and name.lower() != "unnamed.ifc":
        fouten.append("Bestandsnaam hoort structuur <...>_<...>_<...>.ifc te hebben (tegel 3.1).")
    return fouten


# 3.3 Bouwlaag — alleen IfcBuildingStorey, Name = "<bouwlaagnummer> <verdiepingsoort> <tekst>"
# Verdiepingsoort in Basis ILS is vrije tekst maar poster/infographic impliceren
# categorieën als "Begane grond", "Verdieping", "Dak", "Kelder", "Zolder".
_STOREY_RE = re.compile(
    r"^(?P<nr>\d{2})\s+(?P<soort>\S.*\S)\s*$"
    # Voorbeelden: "00 Begane grond", "01 Eerste verdieping", "02 Dak"
)


def format_storey_naam(nr: int, soort: str, tekst: str = "") -> str:
    """
    Formatteer bouwlaag-naam volgens tegel 3.3.

    Args:
        nr: bouwlaagnummer (00-99), wordt als 2-cijferig geformat.
        soort: verdiepingsoort, bv. "Begane grond", "Verdieping", "Dak".
        tekst: optionele aanvulling, wordt achter soort geplakt met spatie.

    Retourneert bv. "00 Begane grond", "01 Eerste verdieping".
    """
    base = f"{nr:02d} {soort.strip()}"
    if tekst.strip():
        return f"{base} {tekst.strip()}"
    return base


def check_storey_naam(name: str) -> list[str]:
    """
    Valideer bouwlaag-naam tegen tegel 3.3.

    Retourneert foutmeldingen, leeg bij geldig.
    Verwacht patroon: "NN <verdiepingsoort> [tekst]" (NN = 2 cijfers).
    """
    fouten: list[str] = []
    if not name or not name.strip():
        return ["Bouwlaag-naam mag niet leeg zijn (tegel 3.3)."]
    if not _STOREY_RE.match(name.strip()):
        fouten.append(
            "Bouwlaag-naam moet patroon '<NN> <verdiepingsoort> [tekst]' volgen "
            "(bv. '00 Begane grond', '01 Eerste verdieping') — tegel 3.3."
        )
    return fouten
