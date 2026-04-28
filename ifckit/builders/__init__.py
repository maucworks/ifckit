"""
ifckit.builders
===============

Builder implementations and default registry.
"""

from ifckit.builders.base import BuilderRegistry, IIfcBuilder
from ifckit.builders.wall import WallBuilder
from ifckit.builders.slab import SlabBuilder
from ifckit.builders.extruded import ExtrudedElementBuilder
from ifckit.builders.revolved_beam import RevolvedBeamBuilder
from ifckit.builders.bridge import AlignmentBuilder

# Convenience aliases
BeamBuilder   = ExtrudedElementBuilder("basic_beam",   "IfcBeam")
ColumnBuilder = ExtrudedElementBuilder("basic_column", "IfcColumn")


def default_registry() -> BuilderRegistry:
    """Return a BuilderRegistry pre-loaded with all built-in builders."""
    registry = BuilderRegistry()
    registry.register(WallBuilder())
    registry.register(SlabBuilder())
    registry.register(ExtrudedElementBuilder("basic_beam",   "IfcBeam"))
    registry.register(ExtrudedElementBuilder("basic_column", "IfcColumn"))
    registry.register(RevolvedBeamBuilder())
    registry.register(AlignmentBuilder())
    return registry


__all__ = [
    "BuilderRegistry",
    "IIfcBuilder",
    "WallBuilder",
    "SlabBuilder",
    "ExtrudedElementBuilder",
    "BeamBuilder",
    "ColumnBuilder",
    "RevolvedBeamBuilder",
    "AlignmentBuilder",
    "default_registry",
]
