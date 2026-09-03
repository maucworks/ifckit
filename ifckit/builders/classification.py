"""ifckit.builders.classification — NL-SfB en andere classificaties."""

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
    Voeg een classificatiesysteem toe (bv. NL-SfB).

    Wrapper om ``ifcopenshell.api.classification.add_classification`` met
    extra metadata (edition/source) waar mogelijk.
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
    Ken een classificatiereferentie toe (bv. NL-SfB 21.12).

    Wrapper om ``add_reference``.
    """
    return ifcopenshell.api.classification.add_reference(
        ifc_file,
        products=products,
        classification=classification,
        identification=identification,
        name=name,
    )
