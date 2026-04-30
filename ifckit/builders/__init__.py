"""
ifckit.builders
===============

Builder implementations and default registry.
"""

from ifckit.builders.base import BuilderRegistry, IIfcBuilder
from ifckit.builders.beam_factory import PathType, build_beam, classify_path
from ifckit.builders.bridge import AlignmentBuilder
from ifckit.builders.extruded import ExtrudedElementBuilder
from ifckit.builders.revolved_beam import RevolvedBeamBuilder
from ifckit.builders.slab import SlabBuilder
from ifckit.builders.wall import WallBuilder


def default_registry() -> BuilderRegistry:
    """Return a BuilderRegistry pre-loaded with all built-in builders."""
    registry = BuilderRegistry()
    registry.register(WallBuilder())
    registry.register(SlabBuilder())
    registry.register(ExtrudedElementBuilder("basic_beam", "IfcBeam"))
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
    "RevolvedBeamBuilder",
    "AlignmentBuilder",
    "PathType",
    "classify_path",
    "build_beam",
    "default_registry",
]
