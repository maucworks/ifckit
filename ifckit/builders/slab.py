"""
ifckit.builders.slab
===================

SlabBuilder — backward-compat alias for WallSlabBuilder("basic_slab", "IfcSlab", "thickness").
"""

from __future__ import annotations

from ifckit.builders.extruded import WallSlabBuilder


class SlabBuilder(WallSlabBuilder):
    """Builds an IfcSlab from a PendingSlab."""

    entity_type = "basic_slab"

    def __init__(self) -> None:
        super().__init__("basic_slab", "IfcSlab", "thickness")
