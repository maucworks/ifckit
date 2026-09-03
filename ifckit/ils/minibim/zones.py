# This file was generated with the assistance of an AI coding tool.
"""ifckit.ils.minibim.zones — groeperen op EenheidNummer / BouwwerkNummer."""

from __future__ import annotations

from typing import Any

from ._version import ILS_NAME


def _file_of(model_or_file: Any) -> Any:
    """Accepteer IfcModel of een rauw ifcopenshell file-object."""
    return getattr(model_or_file, "_file", model_or_file)


def group_zones(model_or_file: Any, by: str = "EenheidNummer") -> list:
    """
    Groepeer alle IfcSpace met een MiniBIM ILS pset op property *by*.

    Schrijft per unieke waarde een IfcZone (via core
    ``ifckit.builders.zones.group_spaces_by_property``).

    Voorbeeld::

        group_zones(model, by="EenheidNummer")
    """
    from ifckit.builders.zones import group_spaces_by_property

    return group_spaces_by_property(_file_of(model_or_file), ILS_NAME, by)


def group_by_eenheid(model_or_file: Any) -> list:
    """Groepeer op EenheidNummer."""
    return group_zones(model_or_file, by="EenheidNummer")


def group_by_bouwwerk(model_or_file: Any) -> list:
    """Groepeer op BouwwerkNummer."""
    return group_zones(model_or_file, by="BouwwerkNummer")
