# This file was generated with the assistance of an AI coding tool.
"""ifckit.spatial — ruimtelijk programma (PvE) als graaf, afleiding en conformance.

Het fundament van de agent-loop: een PvE wordt vastgelegd als getypeerde graaf
(:class:`RoomProgram`), de gerealiseerde graaf wordt afgeleid uit een IFC-model
(:func:`space_adjacency`, :func:`wall_graph`), en :func:`conform` vergelijkt de
twee. Graaf-gedreven operatoren (:mod:`ifckit.spatial.operators`) genereren
deterministische geometrie uit het PvE. Alles draait op een stdlib-graaf
(:class:`Graph`); ``networkx`` en ``shapely`` zijn optioneel.
"""

from ifckit.spatial.analysis import (
    D_VALUES,
    SpaceSyntax,
    analyze,
    choice,
    connectivity,
    control,
    diamond_value,
    integration,
    mean_depth,
    relative_asymmetry,
    total_depth,
)
from ifckit.spatial.conform import (
    CirculationReport,
    ConformanceReport,
    check_program,
    conform,
    validate_circulation,
)
from ifckit.spatial.derive import (
    perimeter_spaces,
    space_adjacency,
    space_footprint_points,
    space_footprints,
    wall_graph,
)
from ifckit.spatial.graph import Graph
from ifckit.spatial.operators import (
    add_room,
    layout_row,
    mirror_footprint,
    place_space,
    remove_room,
    split_footprint,
)
from ifckit.spatial.program import EDGE_KINDS, SPACE_ROLES, ProgramEdge, ProgramSpace, RoomProgram

__all__ = [
    "Graph",
    "RoomProgram",
    "ProgramSpace",
    "ProgramEdge",
    "EDGE_KINDS",
    "SPACE_ROLES",
    "place_space",
    "split_footprint",
    "mirror_footprint",
    "add_room",
    "remove_room",
    "layout_row",
    "ConformanceReport",
    "CirculationReport",
    "space_adjacency",
    "wall_graph",
    "space_footprints",
    "space_footprint_points",
    "perimeter_spaces",
    "conform",
    "check_program",
    "validate_circulation",
    "D_VALUES",
    "SpaceSyntax",
    "analyze",
    "total_depth",
    "mean_depth",
    "relative_asymmetry",
    "diamond_value",
    "integration",
    "connectivity",
    "control",
    "choice",
]
