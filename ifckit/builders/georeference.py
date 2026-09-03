# This file was generated with the assistance of an AI coding tool.
"""ifckit.builders.georeference — RD/NAP en andere CRS."""

from __future__ import annotations

import ifcopenshell
import ifcopenshell.api.georeference


def set_georeference(
    ifc_file: ifcopenshell.file,
    projected_crs: dict | None = None,
    coordinate_operation: dict | None = None,
) -> None:
    """
    Stel georeferentie in (IfcProjectedCRS + IfcMapConversion).

    Voorbeeld RD New (EPSG:28992) op een false origin::

        set_georeference(ifc_file,
            projected_crs={"Name": "EPSG:28992"},
            coordinate_operation={"Eastings": 100000, "Northings": 400000, "OrthogonalHeight": 0})

    Wrapper om ``add_georeferencing`` + ``edit_georeferencing``.
    """
    ifcopenshell.api.georeference.add_georeferencing(ifc_file)
    ifcopenshell.api.georeference.edit_georeferencing(
        ifc_file,
        projected_crs=projected_crs,
        coordinate_operation=coordinate_operation,
    )
