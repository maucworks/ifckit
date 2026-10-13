# This file was generated with the assistance of an AI coding tool.
"""ifckit.builders.system — IfcSystem / IfcDistributionSystem grouping.

BIM Basis ILS tile 4.2: group building-service objects per system.
Proof implementation for one of the three gaps
(IfcSystem, IfcMaterial, Pset_*Common).
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
    Create an IfcSystem and assign *products* to it.

    Args:
        ifc_file: ifcopenshell file.
        name: system name (e.g. "Heating").
        products: optional list of elements (IfcFlowSegment,
            IfcDistributionElement...).
        description: optional description.
        predefined_type: subtype if desired (ignored — always IfcSystem).

    Returns the IfcSystem entity.
    """
    # IfcSystem is a subtype of IfcGroup → IfcRelAssignsToGroup for members
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
    Create an IfcDistributionSystem (subtype of IfcSystem).

    Example: ventilation, sanitary plumbing, electrical.
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
