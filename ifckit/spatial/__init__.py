# This file was generated with the assistance of an AI coding tool.
"""ifckit.spatial — ruimtelijk programma (PvE) als graaf, afleiding en conformance.

Het fundament van de agent-loop: een PvE wordt vastgelegd als getypeerde graaf
(:class:`RoomProgram`), de gerealiseerde graaf wordt afgeleid uit een IFC-model
(:func:`space_adjacency`, :func:`wall_graph`), en :func:`conform` vergelijkt de
twee. Alles draait op een stdlib-graaf (:class:`Graph`); ``networkx`` en
``shapely`` zijn optioneel.
"""

from ifckit.spatial.conform import ConformanceReport, check_program, conform
from ifckit.spatial.derive import perimeter_spaces, space_adjacency, space_footprints, wall_graph
from ifckit.spatial.graph import Graph
from ifckit.spatial.program import EDGE_KINDS, ProgramEdge, ProgramSpace, RoomProgram

__all__ = [
    "Graph",
    "RoomProgram",
    "ProgramSpace",
    "ProgramEdge",
    "EDGE_KINDS",
    "ConformanceReport",
    "space_adjacency",
    "wall_graph",
    "space_footprints",
    "perimeter_spaces",
    "conform",
    "check_program",
]
