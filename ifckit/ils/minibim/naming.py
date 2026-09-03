# This file was generated with the assistance of an AI coding tool.
"""ifckit.ils.minibim.naming — naamgevingsregels (EenheidNummer, bestandsnaam, bouwlaag)."""

from __future__ import annotations

import re

_EENHEID_RE = re.compile(r"^\d{2}\.\d{2}\.\d{2}$")


def format_eenheid_nummer(bouwwerk: int, bouwlaag: int, volg: int) -> str:
    """01.00.01 etc. — bouwwerk.bouwlaag.volgnummer."""
    return f"{bouwwerk:02d}.{bouwlaag:02d}.{volg:02d}"


def is_valid_eenheid_nummer(code: str) -> bool:
    return bool(_EENHEID_RE.match(code))


def format_bestandsnaam(project: str, fase: str, discipline: str = "VORM") -> str:
    """MiniBIM bestandsnaam-conventie (vereenvoudigd)."""
    return f"MiniBIM {fase}_{project}_{discipline}.ifc"
