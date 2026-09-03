"""ifckit.builders.zones — IfcZone groepering."""

from __future__ import annotations

from typing import Any

import ifcopenshell
import ifcopenshell.api.owner
import ifcopenshell.guid


def add_zone(
    ifc_file: ifcopenshell.file,
    name: str,
    spaces: list[ifcopenshell.entity_instance],
    description: str | None = None,
) -> ifcopenshell.entity_instance:
    """
    Maak een IfcZone en koppel *spaces* eraan.

    Generiek — te gebruiken voor MiniBIM EenheidNummer/BouwwerkNummer
    of elke andere groepering.
    """
    zone = ifc_file.create_entity(
        "IfcZone",
        GlobalId=ifcopenshell.guid.new(),
        OwnerHistory=ifcopenshell.api.owner.create_owner_history(ifc_file),
        Name=name,
        Description=description,
    )
    if spaces:
        ifc_file.create_entity(
            "IfcRelAssignsToGroup",
            GlobalId=ifcopenshell.guid.new(),
            OwnerHistory=ifcopenshell.api.owner.create_owner_history(ifc_file),
            RelatedObjects=spaces,
            RelatingGroup=zone,
        )
    return zone


def group_spaces_by_property(
    ifc_file: ifcopenshell.file,
    pset_name: str,
    prop_name: str,
) -> list[ifcopenshell.entity_instance]:
    """
    Groepeer IfcSpace-objecten op een property-waarde.

    Zoekt alle IfcSpace met een pset *pset_name* die *prop_name* bevat,
    en maakt per unieke waarde een IfcZone.
    """
    # Bouw mapping waarde -> spaces
    from collections import defaultdict

    groups: dict[str, list] = defaultdict(list)

    for space in ifc_file.by_type("IfcSpace"):
        # zoek pset
        for rel in getattr(space, "IsDefinedBy", []) or []:
            pset = getattr(rel, "RelatingPropertyDefinition", None)
            if not pset or pset.Name != pset_name:
                continue
            for prop in getattr(pset, "HasProperties", []) or []:
                if getattr(prop, "Name", None) == prop_name:
                    val = getattr(prop.NominalValue, "wrappedValue", None)
                    if val is None:
                        val = str(prop.NominalValue)
                    val = str(val).strip()
                    if val:
                        groups[val].append(space)
                    break

    zones = []
    for val, spaces in sorted(groups.items()):
        zones.append(add_zone(ifc_file, val, spaces))
    return zones
