# This file was generated with the assistance of an AI coding tool.
"""ifckit.ils.minibim.demarcatie — demarcatie Bouwwerk en Gebruiksbestemming.

Regels uit MiniBIM ILS v3.1 deel A §9.3 en §9.4. Tekstueel van aard;
hier als data + validatie-helpers voor modelcontrole, niet als automatische
geometrie-splitsing.
"""

from __future__ import annotations

# §9.3 — 6 demarcatie-gevallen voor Bouwwerk
BOUWWERK_REGELS: list[dict] = [
    {
        "id": 1,
        "titel": "Fysiek gescheiden gebouwen",
        "regel": "Ondergeschikte gebouwen negeren.",
    },
    {
        "id": 2,
        "titel": "Niet-fysiek gescheiden met eigen lifthal/hoofdtrap",
        "regel": "Model opdelen naar (mogelijke) afnemer.",
    },
    {
        "id": 3,
        "titel": (
            "Niet-fysiek gescheiden met eigen lifthal/hoofdtrap"
            " + gemeenschappelijke onderbouw"
        ),
        "regel": (
            "Onderbouw is apart bouwwerk. Doorgaande lifthallen/trappenhuizen"
            " horen bij bovenliggende bouwwerken."
        ),
    },
    {
        "id": 4,
        "titel": "Fysiek gescheiden op gemeenschappelijke onderbouw",
        "regel": (
            "Onderbouw is apart bouwwerk. Doorgaande lifthallen/trappenhuizen"
            " horen bij bovenliggende bouwwerken."
        ),
    },
    {
        "id": 5,
        "titel": "Fysiek gescheiden op plint met andere gebruiksfunctie",
        "regel": (
            "Onderbouw is apart bouwwerk. Andere gebruiksfunctie is onderdeel"
            " van één van de bouwwerken."
        ),
    },
    {
        "id": 6,
        "titel": "Fysiek gescheiden op plint met andere gebruiksfunctie (plint apart)",
        "regel": (
            "Plint is apart bouwwerk, eventueel samen met onderbouw."
            " Doorgaande lifthallen/trappenhuizen horen bij bovenliggende"
            " bouwwerken."
        ),
    },
]

# §9.4 — Gebruiksbestemming
GEBRUIKSBESTEMMING_REGELS: list[dict] = [
    {
        "id": "woonfunctie-ontsluiting",
        "regel": (
            "Een Gemeenschappelijke (verkeers)ruimte die Gebruiksfuncties met "
            "Gebruiksbestemming Woonfunctie ontsluit wordt tot de Woonfunctie gerekend. "
            "Ontsluit zij ook andere Gebruiksbestemmingen, dan krijgt zij meerdere "
            "Gebruiksbestemmingen gescheiden door ', '."
        ),
    },
    {
        "id": "parkeren",
        "regel": (
            "Parkeren (incl. in-/uitritten en bijbehorende ruimten) wordt tot "
            "Overige gebruiksfunctie gerekend."
        ),
    },
]

# NEN 2580 is uitgangspunt voor vloeroppervlakte-demarcatie (geen code, wel principe)
NEN2580_OPMERKING = "NEN 2580 is uitgangspunt voor vloeroppervlakte-demarcatie."


def bouwwerk_regel(regel_id: int) -> dict | None:
    for r in BOUWWERK_REGELS:
        if r["id"] == regel_id:
            return r
    return None


def validate_gebruiksbestemmingen(codes: list[str]) -> list[str]:
    """
    Valideer lijst van Gebruiksbestemming-codes (komma-gescheiden in model).
    Retourneert foutmeldingen, leeg bij geldig.
    """
    from ifckit.ils.common import GEBRUIKSBESTEMMINGEN

    fouten = []
    for c in codes:
        if c not in GEBRUIKSBESTEMMINGEN:
            fouten.append(f"Onbekende Gebruiksbestemming: {c!r}")
    # Gemeenschappelijke ruimte met meerdere bestemmingen moet komma-gescheiden zijn —
    # dat is al afgehandeld door de caller die split(',').
    return fouten
