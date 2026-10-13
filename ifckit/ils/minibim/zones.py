# This file was generated with the assistance of an AI coding tool.
"""ifckit.ils.minibim.zones — group by EenheidNummer / BouwwerkNummer."""

from __future__ import annotations

from typing import Any

from ._version import ILS_NAME


def _file_of(model_or_file: Any) -> Any:
    """Accept an IfcModel or a raw ifcopenshell file object."""
    return getattr(model_or_file, "_file", model_or_file)


def group_zones(model_or_file: Any, by: str = "EenheidNummer") -> list:
    """
    Group every IfcSpace carrying a MiniBIM ILS pset by property *by*.

    Writes one IfcZone per unique value (via the core
    ``ifckit.builders.zones.group_spaces_by_property``).

    Example::

        group_zones(model, by="EenheidNummer")
    """
    from ifckit.builders.zones import group_spaces_by_property

    return group_spaces_by_property(_file_of(model_or_file), ILS_NAME, by)


def group_by_eenheid(model_or_file: Any) -> list:
    """Group by EenheidNummer."""
    return group_zones(model_or_file, by="EenheidNummer")


def group_by_bouwwerk(model_or_file: Any) -> list:
    """Group by BouwwerkNummer."""
    return group_zones(model_or_file, by="BouwwerkNummer")
