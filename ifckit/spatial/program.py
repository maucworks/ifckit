# This file was generated with the assistance of an AI coding tool.
"""Ruimtelijk programma (PvE) als getypeerde graaf.

Het PvE is het *stabiele contract* in de agent-loop: knopen zijn ruimten
(incl. buitenruimten), kanten zijn getypeerde relaties met een hard/zacht
onderscheid.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Bekende kanttypen. ``door``/``forbidden``/``facade`` zijn hard;
#: ``wall``/``visual`` zijn zacht (hints, geen poort).
EDGE_KINDS = ("door", "forbidden", "facade", "wall", "visual")

#: Harde kanttypen — de conformance-poort toetst deze.
HARD_EDGE_KINDS = ("door", "forbidden", "facade")


@dataclass
class ProgramSpace:
    """Eén programmaruimte (knoop).

    Attributes:
        name: Ruimtenummer/-code (``IfcSpace.Name``), bijv. ``"1.01"``.
        long_name: Beschrijvende naam (``IfcSpace.LongName``), bijv. ``"Keuken"``.
        area_min: Ondergrens oppervlak in m² (optioneel).
        area_max: Bovengrens oppervlak in m² (optioneel).
        required: ``False`` = geprefereerd, geen harde eis.
        exterior: ``True`` = buitenruimte-declaratie (buiten, veranda, ...);
            wordt niet als ``IfcSpace`` verwacht.
    """

    name: str = ""
    long_name: str = ""
    area_min: float | None = None
    area_max: float | None = None
    required: bool = True
    exterior: bool = False


@dataclass
class ProgramEdge:
    """Eén getypeerde relatie (kant) tussen twee programmaruimten.

    Attributes:
        a: Sleutel van de ene knoop.
        b: Sleutel van de andere knoop.
        kind: ``"door"`` | ``"forbidden"`` | ``"facade"`` | ``"wall"`` | ``"visual"``.
        required: ``False`` = zachte hint (geen poort).
        orientation: Nice-to-have bij ``"facade"``: ``"N"``/``"O"``/``"Z"``/``"W"``.
    """

    a: str
    b: str
    kind: str = "wall"
    required: bool = True
    orientation: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in EDGE_KINDS:
            raise ValueError(f"onbekend kanttype {self.kind!r}; verwacht een van {EDGE_KINDS}")


@dataclass
class RoomProgram:
    """Het PvE als getypeerde graaf.

    ``nodes`` is een mapping van sleutel (uuid, stabiel over iteraties) naar
    :class:`ProgramSpace`. ``edges`` is een lijst van :class:`ProgramEdge`.
    """

    nodes: dict[str, ProgramSpace] = field(default_factory=dict)
    edges: list[ProgramEdge] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Return a JSON-serialisable dict."""
        return {
            "nodes": {k: v.__dict__ for k, v in self.nodes.items()},
            "edges": [e.__dict__ for e in self.edges],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RoomProgram":
        """Build a RoomProgram from a dict (see ``to_dict``)."""
        nodes = {k: ProgramSpace(**v) for k, v in data.get("nodes", {}).items()}
        edges = [ProgramEdge(**e) for e in data.get("edges", [])]
        return cls(nodes=nodes, edges=edges)
