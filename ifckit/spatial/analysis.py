# This file was generated with the assistance of an AI coding tool.
"""Space-syntax-maten op een ``Graph`` (Hillier & Hanson).

TD/MD/RA/integratie/connectiviteit/control/choice. Werkt op elke
``ifckit.spatial.Graph`` (meestal de access-graaf). Vereist een samenhangende
graaf; gebruik ``validate_circulation`` voor bereikbaarheidstoetsing.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from ifckit.spatial.graph import Graph

#: D-waarden (Hillier & Hanson 1984, p.112) voor k knopen.
D_VALUES: dict[int, float] = {
    5: 0.352,
    6: 0.349,
    7: 0.34,
    8: 0.328,
    9: 0.317,
    10: 0.306,
}


def diamond_value(n: int) -> float | None:
    """Return de D-waarde voor *n* knopen, of ``None`` buiten de tabel."""
    return D_VALUES.get(n)


def _distances(graph: Graph, source: str) -> dict[str, int]:
    dist = {source: 0}
    queue: deque[str] = deque([source])
    while queue:
        cur = queue.popleft()
        for nbr in graph.neighbors(cur):
            if nbr not in dist:
                dist[nbr] = dist[cur] + 1
                queue.append(nbr)
    return dist


def _require_connected(graph: Graph) -> None:
    if not graph.is_connected():
        raise ValueError("space-syntax-maten vereisen een samenhangende graaf")


def total_depth(graph: Graph) -> dict[str, float]:
    """Totale diepte per knoop (som van korte-padlengtes naar alle anderen)."""
    _require_connected(graph)
    return {node: float(sum(_distances(graph, node).values())) for node in graph.nodes()}


def mean_depth(graph: Graph) -> dict[str, float]:
    """Gemiddelde diepte per knoop."""
    _require_connected(graph)
    n = len(graph)
    td = total_depth(graph)
    return {node: td[node] / (n - 1) for node in td}


def relative_asymmetry(graph: Graph) -> dict[str, float]:
    """Relatieve asymmetrie (RA) per knoop, 0..1."""
    _require_connected(graph)
    n = len(graph)
    if n <= 2:
        raise ValueError("RA vereist meer dan 2 knopen")
    md = mean_depth(graph)
    return {node: 2.0 * (md[node] - 1.0) / (n - 2) for node in md}


def integration(graph: Graph) -> dict[str, float]:
    """Integratie (1/RRA) per knoop; valt terug op 1/RA buiten de D-tabel."""
    _require_connected(graph)
    ra = relative_asymmetry(graph)
    d = diamond_value(len(graph))
    result = {}
    for node, ra_v in ra.items():
        rra = ra_v / d if d else ra_v
        result[node] = 1.0 / rra if rra > 0 else float("inf")
    return result


def connectivity(graph: Graph) -> dict[str, int]:
    """Connectiviteit (graad) per knoop."""
    return {node: graph.degree(node) for node in graph.nodes()}


def control(graph: Graph) -> dict[str, float]:
    """Control-waarde per knoop: verdeelde graad over buren."""
    result = {}
    for node in graph.nodes():
        total = 0.0
        for nbr in graph.neighbors(node):
            deg = graph.degree(nbr)
            if deg > 0:
                total += 1.0 / deg
        result[node] = total
    return result


def choice(graph: Graph) -> dict[str, float]:
    """Choice (betweenness) per knoop: fractie van korte paden erdoorheen."""
    _require_connected(graph)
    nodes = list(graph.nodes())
    score = {node: 0.0 for node in nodes}
    for s in nodes:
        dist = {s: 0}
        pred: dict[str, list[str]] = {s: []}
        sigma = {s: 1}
        order = [s]
        queue: deque[str] = deque([s])
        while queue:
            cur = queue.popleft()
            for nbr in graph.neighbors(cur):
                if nbr not in dist:
                    dist[nbr] = dist[cur] + 1
                    sigma[nbr] = 0
                    pred[nbr] = []
                    queue.append(nbr)
                    order.append(nbr)
                if dist[nbr] == dist[cur] + 1:
                    sigma[nbr] += sigma[cur]
                    pred[nbr].append(cur)
        delta = {node: 0.0 for node in nodes}
        for w in reversed(order):
            for p in pred[w]:
                delta[p] += (sigma[p] / sigma[w]) * (1.0 + delta[w])
            if w != s:
                score[w] += delta[w]
    return {node: score[node] / 2.0 for node in nodes}


@dataclass
class SpaceSyntax:
    """Alle space-syntax-maten per knoop."""

    depth: dict[str, float] = field(default_factory=dict)
    integration: dict[str, float] = field(default_factory=dict)
    connectivity: dict[str, int] = field(default_factory=dict)
    control: dict[str, float] = field(default_factory=dict)
    choice: dict[str, float] = field(default_factory=dict)


def analyze(graph: Graph) -> SpaceSyntax:
    """Bereken alle space-syntax-maten voor een samenhangende graaf."""
    return SpaceSyntax(
        depth=mean_depth(graph),
        integration=integration(graph),
        connectivity=connectivity(graph),
        control=control(graph),
        choice=choice(graph),
    )
