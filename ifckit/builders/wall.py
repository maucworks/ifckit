"""
ifckit.builders.wall
===================

WallBuilder — backward-compat alias for WallSlabBuilder("basic_wall", "IfcWall", "height").
"""

from __future__ import annotations

from ifckit.builders.extruded import WallSlabBuilder


class WallBuilder(WallSlabBuilder):
    """Builds an IfcWall from a PendingWall."""

    entity_type = "basic_wall"

    def __init__(self) -> None:
        super().__init__("basic_wall", "IfcWall", "height")
