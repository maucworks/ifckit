# This file was generated with the assistance of an AI coding tool.
"""Conformance: vergelijk een gerealiseerd IFC-model met een PvE-graaf."""

from __future__ import annotations

from dataclasses import dataclass, field

from ifckit.spatial.derive import perimeter_spaces, space_adjacency, space_footprints
from ifckit.spatial.graph import Graph
from ifckit.spatial.program import RoomProgram


@dataclass
class ConformanceReport:
    """Resultaat van :func:`conform`.

    Attributes:
        satisfied: Labels van voldane harde eisen.
        violated: Labels van geschonden harde eisen.
        missing: Labels van vereiste ruimten die ontbreken in het model.
        unconstrained: Labels die niet getoetst konden worden (zacht/onbekend).
    """

    satisfied: list[str] = field(default_factory=list)
    violated: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unconstrained: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Return whether no required constraint is violated or missing."""
        return not self.violated and not self.missing


def _match(model, program: RoomProgram):
    """Koppel programmasleutels aan gerealiseerde ruimte-ids (op naam)."""
    graph = space_adjacency(model)
    footprints = space_footprints(model)
    perimeter = perimeter_spaces(footprints)

    name_to_gid: dict[str, str] = {}
    for gid, attrs in graph.nodes().items():
        name = attrs.get("name") or ""
        if name:
            name_to_gid.setdefault(name, gid)

    gid_by_key: dict[str, str] = {}
    for key, space in program.nodes.items():
        if space.name and space.name in name_to_gid:
            gid_by_key[key] = name_to_gid[space.name]
    return graph, footprints, perimeter, gid_by_key


def conform(model, program: RoomProgram) -> ConformanceReport:
    """Vergelijk een gerealiseerd IFC-model met een PvE-graaf.

    Koppelt programmaruimten aan ``IfcSpace``-entiteiten op naam, toetst
    oppervlakte-ranges en de getypeerde kanten:

    - ``door``: vereist een ``door``-kant in de gerealiseerde graaf.
    - ``forbidden``: overtreden als de twee ruimten een grens delen.
    - ``facade``: voldaan als de ruimte op de envelop ligt (buitengevel).
    - ``wall``/``visual``: zacht; voldaan bij elke grens, anders ``unconstrained``
      (of ``violated`` wanneer expliciet ``required=True``).
    """
    graph, footprints, perimeter, gid_by_key = _match(model, program)
    report = ConformanceReport()

    # Buitenruimten (doel van een facade-kant) zijn declaraties, geen te
    # realiseren IfcSpace's; die toetsen we niet op aanwezigheid.
    exterior_nodes = {e.b for e in program.edges if e.kind == "facade"}

    for key, space in program.nodes.items():
        if key in exterior_nodes:
            continue
        gid = gid_by_key.get(key)
        if gid is None:
            target = report.missing if space.required else report.unconstrained
            target.append(f"space:{key}")
            continue
        if gid in footprints:
            area = footprints[gid].area
            if space.area_min is not None and area < space.area_min:
                report.violated.append(f"space:{key}:area<{space.area_min}")
                continue
            if space.area_max is not None and area > space.area_max:
                report.violated.append(f"space:{key}:area>{space.area_max}")
                continue
        report.satisfied.append(f"space:{key}")

    for edge in program.edges:
        label = f"edge:{edge.a}-{edge.b}:{edge.kind}"
        ga = gid_by_key.get(edge.a)
        gb = gid_by_key.get(edge.b)
        if edge.kind == "facade":
            # edge.b is de buitenruimte (buiten/balkon): informatief. De eis is
            # dat edge.a een buitengevel heeft (op de envelop ligt).
            if ga is None:
                report.unconstrained.append(label)
            elif ga in perimeter:
                report.satisfied.append(label)
            else:
                report.violated.append(label)
            continue
        if ga is None or gb is None:
            report.unconstrained.append(label)
            continue
        if edge.kind == "forbidden":
            if graph.has_edge(ga, gb):
                report.violated.append(label)
            else:
                report.satisfied.append(label)
        elif edge.kind == "door":
            attrs = graph.edge_attrs(ga, gb)
            if attrs is not None and attrs.get("kind") == "door":
                report.satisfied.append(label)
            else:
                report.violated.append(label)
        else:  # "wall", "visual" — zacht
            if graph.has_edge(ga, gb):
                report.satisfied.append(label)
            elif edge.required:
                report.violated.append(label)
            else:
                report.unconstrained.append(label)

    return report


def check_program(program: RoomProgram) -> list[str]:
    """Statische controles op een PvE-graaf: onbekende refs en geïsoleerde knopen."""
    issues: list[str] = []
    keys = set(program.nodes)
    for edge in program.edges:
        if edge.a not in keys:
            issues.append(f"kant verwijst naar onbekende knoop {edge.a!r}")
        if edge.b not in keys:
            issues.append(f"kant verwijst naar onbekende knoop {edge.b!r}")

    g = Graph()
    for key in keys:
        g.add_node(key)
    for edge in program.edges:
        if edge.kind != "forbidden":
            g.add_edge(edge.a, edge.b)
    for key in keys:
        if g.degree(key) == 0:
            issues.append(f"geïsoleerde knoop {key!r}")
    return issues
