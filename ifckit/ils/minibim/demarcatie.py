# This file was generated with the assistance of an AI coding tool.
"""ifckit.ils.minibim.demarcatie — Bouwwerk and Gebruiksbestemming demarcation.

Rules from MiniBIM ILS v3.1 part A §9.3 and §9.4. Textual in nature;
used here as data + validation helpers for model checking, not as
automatic geometry splitting.
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
            "Niet-fysiek gescheiden met eigen lifthal/hoofdtrap + gemeenschappelijke onderbouw"
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

# NEN 2580 is the baseline for floor-area demarcation (no code, but a principle)
NEN2580_OPMERKING = "NEN 2580 is uitgangspunt voor vloeroppervlakte-demarcatie."


def bouwwerk_regel(regel_id: int) -> dict | None:
    for r in BOUWWERK_REGELS:
        if r["id"] == regel_id:
            return r
    return None


def validate_gebruiksbestemmingen(codes: list[str]) -> list[str]:
    """
    Validate a list of Gebruiksbestemming codes (comma-separated in the model).
    Returns error messages, empty when valid.
    """
    from ifckit.ils.common import GEBRUIKSBESTEMMINGEN

    errors = []
    for c in codes:
        if c not in GEBRUIKSBESTEMMINGEN:
            errors.append(f"Unknown Gebruiksbestemming: {c!r}")
    # A shared space with multiple destinations must be comma-separated —
    # already handled by the caller that splits on ','.
