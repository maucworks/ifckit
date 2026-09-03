# This file was generated with the assistance of an AI coding tool.
"""ifckit.builders.system — IfcSystem / IfcDistributionSystem groepering.

BIM Basis ILS tegel 4.2: groepeer installatietechnische objecten per systeem.
Proof-implementatie voor één van de drie gaps (IfcSystem, IfcMaterial, Pset_*Common).
"""

from __future__ import annotations

from typing import Any

import ifcopenshell
import ifcopenshell.api.owner
import ifcopenshell.guid


def add_system(
    ifc_file: Any,
    name: str,
    products: list[Any] | None = None,
    description: str | None = None,
    predefined_type: str | None = None,
) -> Any:
    """
    Maak een IfcSystem en koppel *products* eraan.

    Args:
        ifc_file: ifcopenshell file.
        name: systeemnaam (bv. "Verwarming").
        products: optionele lijst van elementen (IfcFlowSegment, IfcDistributionElement...).
        description: optionele beschrijving.
        predefined_type: subtype indien gewenst (wordt genegeerd — altijd IfcSystem).

    Retourneert de IfcSystem entiteit.
    """
    # IfcSystem is subtype van IfcGroup → IfcRelAssignsToGroup voor members
    system = ifc_file.create_entity(
        "IfcSystem",
        GlobalId=ifcopenshell.guid.new(),
        OwnerHistory=ifcopenshell.api.owner.create_owner_history(ifc_file),
        Name=name,
        Description=description,
    )
    if products:
        ifc_file.create_entity(
            "IfcRelAssignsToGroup",
            GlobalId=ifcopenshell.guid.new(),
            OwnerHistory=ifcopenshell.api.owner.create_owner_history(ifc_file),
            RelatedObjects=list(products),
            RelatingGroup=system,
        )
    return system


def add_distribution_system(
    ifc_file: Any,
    name: str,
    products: list[Any] | None = None,
    long_name: str | None = None,
) -> Any:
    """
    Maak een IfcDistributionSystem (subtype van IfcSystem).

    Voorbeeld: ventilatie, sanitair, elektra.
    """
    system = ifc_file.create_entity(
        "IfcDistributionSystem",
        GlobalId=ifcopenshell.guid.new(),
        OwnerHistory=ifcopenshell.api.owner.create_owner_history(ifc_file),
        Name=name,
        LongName=long_name,
    )
    if products:
        ifc_file.create_entity(
            "IfcRelAssignsToGroup",
            GlobalId=ifcopenshell.guid.new(),
            OwnerHistory=ifcopenshell.api.owner.create_owner_history(ifc_file),
            RelatedObjects=list(products),
            RelatingGroup=system,
        )
    return system
