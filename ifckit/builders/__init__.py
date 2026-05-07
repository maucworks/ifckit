"""
ifckit.builders
==============

Builder implementations and default registry.
"""

from ifckit.builders._geom import get_precision, set_precision
from ifckit.builders.base import BuilderRegistry, IIfcBuilder
from ifckit.builders.beam_factory import PathType, build_beam, classify_path
from ifckit.builders.bridge import AlignmentBuilder
from ifckit.builders.extruded import ExtrudedElementBuilder
from ifckit.builders.revolved_beam import RevolvedBeamBuilder
from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.builders.slab import SlabBuilder
from ifckit.builders.space import SpaceBuilder
from ifckit.builders.wall import WallBuilder


def default_registry() -> BuilderRegistry:
    """Return a BuilderRegistry pre-loaded with all built-in builders."""
    registry = BuilderRegistry()
    registry.register(WallBuilder())
    registry.register(SlabBuilder())
    registry.register(SpaceBuilder())
    registry.register(ExtrudedElementBuilder("basic_beam", "IfcBeam"))
    registry.register(ExtrudedElementBuilder("basic_column", "IfcColumn"))
    registry.register(RevolvedBeamBuilder())
    # Skip SectionedSpineBuilder for now - register manually when needed
    return registry


__all__ = [
    "BuilderRegistry",
    "IIfcBuilder",
    "WallBuilder",
    "SlabBuilder",
    "SpaceBuilder",
    "ExtrudedElementBuilder",
    "RevolvedBeamBuilder",
    "SectionedSpineBuilder",  # NEW
    "AlignmentBuilder",
    "PathType",
    "classify_path",
    "build_beam",
    "default_registry",
    "set_precision",
    "get_precision",
]
