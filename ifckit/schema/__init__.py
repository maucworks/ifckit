"""
ifckit.schema
=============

IFC schema version management and unit helpers.
"""

from __future__ import annotations

import enum


class IfcSchema(enum.Enum):
    """Supported IFC schema versions."""

    IFC2X3 = "IFC2X3"
    IFC4 = "IFC4"
    IFC4X3 = "IFC4X3"

    def to_ifcopenshell(self) -> str:
        """Return the ifcopenshell schema string for this enum value."""
        return self.value


class TessellationDetail(enum.IntEnum):
    """Profile tessellation quality presets.

    Controls how many polygon segments are used to approximate curved
    profile outlines (circles, arcs).  Higher values produce smoother
    geometry at the cost of larger file size and slower rendering.

    +---------+---------+------------------------------------------+
    | Preset  | segments| Typical use                              |
    +=========+=========+==========================================+
    | COARSE  |    8    | Schematic / early design                 |
    | MEDIUM  |   16    | Construction documents, most profiles    |
    | FINE    |   32    | Detailed coordination, circular sections |
    | ULTRA   |   64    | High-fidelity renders, large-radius arcs |
    +---------+---------+------------------------------------------+

    The value is an integer and can be passed anywhere ``profile_segments``
    is accepted::

        from ifckit import TessellationDetail
        builder.build_from_spine(..., profile_segments=TessellationDetail.FINE)
    """

    COARSE = 8
    MEDIUM = 16
    FINE = 32
    ULTRA = 64


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
