# This file was generated with the assistance of an AI coding tool.
"""ifckit.builders.classification — NL-SfB and other classifications."""

from __future__ import annotations

from typing import Optional

import ifcopenshell
import ifcopenshell.api.classification
import ifcopenshell.guid


def add_classification(
    ifc_file: ifcopenshell.file,
    name: str,
    edition: Optional[str] = None,
    source: Optional[str] = None,
) -> ifcopenshell.entity_instance:
    """
    Add a classification system (e.g. NL-SfB).

    Wrapper around ``ifcopenshell.api.classification.add_classification``
    with extra metadata (edition/source) where possible.
    """
    cls = ifcopenshell.api.classification.add_classification(ifc_file, classification=name)
    # Edition is IFC-version dependent; set if provided and not already set
    if edition and not getattr(cls, "Edition", None):
        try:
            cls.Edition = edition
        except Exception:
            pass
    if source and not getattr(cls, "Source", None):
        try:
            cls.Source = source
        except Exception:
            pass
    return cls


def assign_classification(
    ifc_file: ifcopenshell.file,
    products: list[ifcopenshell.entity_instance],
    classification: ifcopenshell.entity_instance,
    identification: str,
    name: str,
) -> ifcopenshell.entity_instance:
    """
    Assign a classification reference (e.g. NL-SfB 21.12).

    Wrapper around ``add_reference``.
    """
    return ifcopenshell.api.classification.add_reference(
        ifc_file,
        products=products,
        classification=classification,
        identification=identification,
        name=name,
    )
