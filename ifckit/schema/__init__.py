"""
ifckit.schema
=============

IFC schema version management and unit helpers.
"""

from __future__ import annotations

import enum
from typing import Optional


class IfcSchema(enum.Enum):
    """Supported IFC schema versions."""

    IFC2X3 = "IFC2X3"
    IFC4 = "IFC4"
    IFC4X3 = "IFC4X3"


def get_schema_name(schema: IfcSchema) -> str:
    """Return the ifcopenshell schema string for a given IfcSchema enum value."""
    return schema.value


class LengthUnit(enum.Enum):
    """
    Supported length units.

    METRE and MILLIMETRE are fully supported by ``IfcModel``.
    FOOT and INCH are available for unit-conversion via ``unit_scale_to_metres``
    but are **not** supported by ``IfcModel`` (raises ``NotImplementedError``).
    """

    METRE = "METRE"
    MILLIMETRE = "MILLIMETRE"
    FOOT = "FOOT"
    INCH = "INCH"


# Conversion factors to metres
_TO_METRES: dict[LengthUnit, float] = {
    LengthUnit.METRE: 1.0,
    LengthUnit.MILLIMETRE: 0.001,
    LengthUnit.FOOT: 0.3048,
    LengthUnit.INCH: 0.0254,
}


def unit_scale_to_metres(unit: LengthUnit) -> float:
    """Return the scale factor to convert the given unit to metres."""
    return _TO_METRES[unit]
