# This file was generated with the assistance of an AI coding tool.
"""BIM Basis ILS — validators for tile 3.1 (file name) and 3.3 (storey).

Source: specs/bim-basis/tegels.md (infographic v2 + poster v1.0). The
rules are points of attention, not a strict ILS — validation is advice,
not a rejection.
"""

from __future__ import annotations

import re

# 3.1 File name — uniform, consistent per aspect model.
# The BIM Basis ILS does not prescribe a hard regex; the poster/infographic
# show the placeholder "<...>_<...>_<...>.ifc". In practice:
# projectcode_discipline_fase.ifc, without spaces, only [A-Za-z0-9_-],
# ending in .ifc. We validate that pragmatic form.
_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*\.ifc$", re.IGNORECASE)
# Recommended structure: at least 2 parts separated by _ or - (e.g. PRJ_ARC_01.ifc)
_FILENAME_STRUCT_RE = re.compile(r"^.+[_-].+\.ifc$", re.IGNORECASE)


def check_filename(path: str) -> list[str]:
    """
    Validate a file name against BIM Basis tile 3.1.

    Returns error messages, empty when valid.
    Valid examples: "PRJ-ARC-01.ifc", "196-ifckit-admin_ARC_SO.ifc".
    Invalid examples: "model.ifc" (no structure), "my model.ifc" (space),
    "model.pdf" (no .ifc).
    """
    errors: list[str] = []
    # Basename only, no directory
    name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if not name:
        return ["Empty file name."]
    if " " in name:
        errors.append("File name must not contain spaces (tile 3.1).")
    if not _FILENAME_RE.match(name):
        errors.append("File name must end in .ifc and contain only [A-Za-z0-9_-] (tile 3.1).")
    elif not _FILENAME_STRUCT_RE.match(name) and name.lower() != "unnamed.ifc":
        errors.append("File name should follow the structure <...>_<...>_<...>.ifc (tile 3.1).")
    return errors


# 3.3 Storey — only IfcBuildingStorey, Name = "<storey number> <storey kind> <text>"
# The storey kind in Basis ILS is free text but the poster/infographic imply
# categories like "Begane grond", "Verdieping", "Dak", "Kelder", "Zolder".
_STOREY_RE = re.compile(
    r"^(?P<nr>\d{2})\s+(?P<soort>\S.*\S)\s*$"
    # Examples: "00 Begane grond", "01 Eerste verdieping", "02 Dak"
)


def format_storey_name(nr: int, soort: str, tekst: str = "") -> str:
    """
    Format a storey name according to tile 3.3.

    Args:
        nr: storey number (00-99), formatted as two digits.
        soort: storey kind, e.g. "Begane grond", "Verdieping", "Dak".
        tekst: optional extra text, appended after *soort* with a space.

    Returns e.g. "00 Begane grond", "01 Eerste verdieping".
    """
    base = f"{nr:02d} {soort.strip()}"
    if tekst.strip():
        return f"{base} {tekst.strip()}"
    return base


def check_storey_name(name: str) -> list[str]:
    """
    Validate a storey name against tile 3.3.

    Returns error messages, empty when valid.
    Expected pattern: "NN <storey kind> [text]" (NN = 2 digits).
    """
    errors: list[str] = []
    if not name or not name.strip():
        return ["Storey name must not be empty (tile 3.3)."]
    if not _STOREY_RE.match(name.strip()):
        errors.append(
            "Storey name must follow the pattern '<NN> <storey kind> [text]' "
            "(e.g. '00 Begane grond', '01 Eerste verdieping') — tile 3.3."
        )
    return errors
