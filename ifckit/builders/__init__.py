"""
ifckit.builders
==============

Builder implementations and default registry.
"""

from ifckit.builders._precision import get_precision, set_precision
from ifckit.builders.base import BuilderRegistry, IIfcBuilder
from ifckit.builders.beam_factory import PathType, build_beam, classify_path
from ifckit.builders.bridge import AlignmentBuilder
from ifckit.builders.extruded import ExtrudedElementBuilder, WallSlabBuilder
from ifckit.builders.fill_builder import FillBuilder
from ifckit.builders.opening import OpeningBuilder
from ifckit.builders.revolved_beam import RevolvedBeamBuilder
from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.builders.space import SpaceBuilder
from ifckit.builders.tapered import TaperedExtrusionBuilder
from ifckit.builders.wall_graph import WallGraphBuilder


def default_registry() -> BuilderRegistry:
    """Return a BuilderRegistry pre-loaded with all built-in builders."""
    registry = BuilderRegistry()
    registry.register(WallSlabBuilder("basic_wall", "IfcWall", "height"))
    registry.register(WallGraphBuilder())
    registry.register(WallSlabBuilder("basic_slab", "IfcSlab", "thickness"))
    registry.register(SpaceBuilder())
    registry.register(ExtrudedElementBuilder("basic_beam", "IfcBeam"))
    registry.register(ExtrudedElementBuilder("basic_column", "IfcColumn"))
    registry.register(RevolvedBeamBuilder())
    registry.register(SectionedSpineBuilder())
    registry.register(TaperedExtrusionBuilder())
    registry.register(FillBuilder())
    registry.register(OpeningBuilder())

    return registry


__all__ = [
    "BuilderRegistry",
    "IIfcBuilder",
    "WallGraphBuilder",
    "WallSlabBuilder",
    "ExtrudedElementBuilder",
    "SpaceBuilder",
    "RevolvedBeamBuilder",
    "SectionedSpineBuilder",
    "TaperedExtrusionBuilder",
    "OpeningBuilder",
    "AlignmentBuilder",
    "PathType",
    "classify_path",
    "build_beam",
    "default_registry",
    "set_precision",
    "get_precision",
]
