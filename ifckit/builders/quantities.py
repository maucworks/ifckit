"""ifckit.builders.quantities — base quantities (Qto_...)."""

from __future__ import annotations

from typing import Any

import ifcopenshell
import ifcopenshell.api.pset
import ifcopenshell.guid


def write_quantities(
    ifc_file: ifcopenshell.file,
    element: ifcopenshell.entity_instance,
    qto_name: str,
    quantities: dict[str, float],
) -> None:
    """
    Schrijf een Qto quantity set (bv. Qto_SpaceBaseQuantities).

    quantities: naam -> waarde (bv. {"NetFloorArea": 42.0, "NetVolume": 120.0})
    Waarden worden als IfcQuantityArea / IfcQuantityVolume / IfcQuantityLength
    geschreven afhankelijk van de naam (heuristiek).
    """
    if not quantities:
        return
    q_items = []
    for name, val in quantities.items():
        lname = name.lower()
        if "area" in lname:
            q = ifc_file.create_entity("IfcQuantityArea", Name=name, AreaValue=float(val))
        elif "volume" in lname:
            q = ifc_file.create_entity("IfcQuantityVolume", Name=name, VolumeValue=float(val))
        elif "length" in lname or "height" in lname or "perimeter" in lname:
            q = ifc_file.create_entity("IfcQuantityLength", Name=name, LengthValue=float(val))
        else:
            # default to area for floor-related, volume for volume
            q = ifc_file.create_entity("IfcQuantityArea", Name=name, AreaValue=float(val))
        q_items.append(q)

    qset = ifc_file.create_entity(
        "IfcElementQuantity",
        GlobalId=ifcopenshell.guid.new(),
        Name=qto_name,
        MethodOfMeasurement="",
        Quantities=q_items,
    )
    ifc_file.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[element],
        RelatingPropertyDefinition=qset,
    )
