"""ifckit.ils.minibim.zones — groeperen op EenheidNummer / BouwwerkNummer."""

from __future__ import annotations

from typing import Any


def group_by_eenheid(ifc_file: Any, spaces: list[Any]) -> None:
    """Groeperen op EenheidNummer via IfcZone (via core add_zone wanneer beschikbaar)."""
    # Placeholder — core A3 (add_zone) volgt. Voor nu via directe IFC API.
    _group(ifc_file, spaces, "EenheidNummer")


def group_by_bouwwerk(ifc_file: Any, spaces: list[Any]) -> None:
    _group(ifc_file, spaces, "BouwwerkNummer")


def _group(ifc_file: Any, spaces: list[Any], prop: str) -> None:
    try:
        from ifckit.builders.zones import group_spaces_by_property  # type: ignore
    except Exception:
        # Fallback: geen zones-core yet
        return
    group_spaces_by_property(ifc_file, "MiniBIM ILS", prop)
