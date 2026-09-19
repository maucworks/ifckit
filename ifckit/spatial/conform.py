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
    - ``forbidden``: tussen twee ruimten overtreden als ze een grens delen;
      naar een buitenruimte (knoop zonder oppervlakte-eis) betekent "geen
      buitengevel" en is overtreden als de ruimte op de envelop ligt.
    - ``facade``: voldaan als de ruimte op de envelop ligt (buitengevel).
    - ``wall``/``visual``: zacht; voldaan bij elke grens, anders ``unconstrained``
      (of ``violated`` wanneer expliciet ``required=True``).

    Buitenruimten zijn knopen met ``exterior=True``; die worden niet als
    ``IfcSpace`` verwacht.
    """
    graph, footprints, perimeter, gid_by_key = _match(model, program)
    report = ConformanceReport()

    # Buitenruimten zijn declaraties (``exterior=True``), geen te realiseren
    # IfcSpace's; die toetsen we niet op aanwezigheid.
    exterior_nodes = {key for key, space in program.nodes.items() if space.exterior}

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
        if edge.kind == "forbidden" and edge.b in exterior_nodes:
            # verbod op buitengevel: edge.a mag niet op de envelop liggen.
            if ga is None:
                report.unconstrained.append(label)
            elif ga in perimeter:
                report.violated.append(label)
            else:
                report.satisfied.append(label)
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


@dataclass
class CirculationReport:
    """Resultaat van :func:`validate_circulation` op de access-graaf.

    Attributes:
        root: Wortel van de bereikbaarheidstoets (entree/buitenknoop).
        reachable: Programmasleutels bereikbaar vanaf de wortel.
        unreachable: Vereiste, niet-exterieure ruimten die niet bereikbaar zijn.
        components: Samenhangende componenten van de access-graaf.
    """

    root: str | None = None
    reachable: list[str] = field(default_factory=list)
    unreachable: list[str] = field(default_factory=list)
    components: list[list[str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Return whether every required space is reachable."""
        return not self.unreachable


def _default_root(program: RoomProgram) -> str | None:
    """Wortel: eerste buitenknoop, anders eerste verkeersruimte, anders eerste knoop."""
    for key, space in program.nodes.items():
        if space.exterior:
            return key
    for key, space in program.nodes.items():
        if space.role == "verkeer":
            return key
    return next(iter(program.nodes), None)


def validate_circulation(program: RoomProgram, root: str | None = None) -> CirculationReport:
    """Toets de verkeersstructuur van een PvE op de access-graaf (``door``-kanten).

    Controleert dat elke vereiste, niet-exterieure ruimte bereikbaar is vanaf
    de wortel. Dit is de "gang verbindt alles"-toets.
    """
    access = program.access_graph()
    if root is None:
        root = _default_root(program)
    report = CirculationReport(root=root)
    for comp in access.connected_components():
        report.components.append(sorted(comp))

    if root is None or not access.has_node(root):
        report.unreachable = sorted(
            key for key, space in program.nodes.items() if space.required and not space.exterior
        )
        return report

    from collections import deque

    seen = {root}
    queue: deque[str] = deque([root])
    while queue:
        cur = queue.popleft()
        for nbr in access.neighbors(cur):
            if nbr not in seen:
                seen.add(nbr)
                queue.append(nbr)
    report.reachable = sorted(seen)
    report.unreachable = sorted(
        key
        for key, space in program.nodes.items()
        if space.required and not space.exterior and key not in seen
    )
    return report
