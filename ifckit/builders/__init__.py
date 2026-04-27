"""
ifckit.builders
===============

Builder implementations and default registry.
"""

from ifckit.builders.base import BuilderRegistry, IIfcBuilder
from ifckit.builders.wall import WallBuilder
from ifckit.builders.slab import SlabBuilder
from ifckit.builders.beam import BeamBuilder
from ifckit.builders.column import ColumnBuilder
from ifckit.builders.revolved_beam import RevolvedBeamBuilder
from ifckit.builders.bridge import AlignmentBuilder


def default_registry() -> BuilderRegistry:
    """Return a BuilderRegistry pre-loaded with all built-in builders."""
    registry = BuilderRegistry()
    registry.register(WallBuilder())
    registry.register(SlabBuilder())
    registry.register(BeamBuilder())
    registry.register(ColumnBuilder())
    registry.register(RevolvedBeamBuilder())
    registry.register(AlignmentBuilder())
    return registry


__all__ = [
    "BuilderRegistry",
    "IIfcBuilder",
    "WallBuilder",
    "SlabBuilder",
    "BeamBuilder",
    "ColumnBuilder",
    "RevolvedBeamBuilder",
    "AlignmentBuilder",
    "default_registry",
]
