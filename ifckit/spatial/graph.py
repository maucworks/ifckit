# This file was generated with the assistance of an AI coding tool.
"""Minimal stdlib-first undirected graph with an optional networkx bridge."""

from __future__ import annotations

from collections import deque


class Graph:
    """A minimal undirected graph storing node/edge attributes.

    Nodes and edges carry dictionaries of attributes. The graph is undirected;
    ``add_edge(a, b, ...)`` is symmetric. Node ids are strings.

    This is the dependency-free core of ``ifckit.spatial``. Use
    :meth:`to_networkx` to opt into the richer ``networkx`` algorithm set.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, dict] = {}
        self._adj: dict[str, dict[str, dict]] = {}

    def add_node(self, node: str, **attrs) -> None:
        """Add *node*, merging *attrs* into any existing attributes."""
        self._nodes.setdefault(node, {}).update(attrs)
        self._adj.setdefault(node, {})

    def add_edge(self, a: str, b: str, **attrs) -> None:
        """Add an undirected edge ``a``-``b``, merging *attrs*."""
        self.add_node(a)
        self.add_node(b)
        if b not in self._adj[a]:
            self._adj[a][b] = {}
            self._adj[b][a] = {}
        self._adj[a][b].update(attrs)
        self._adj[b][a].update(attrs)

    def has_node(self, node: str) -> bool:
        """Return whether *node* is present."""
        return node in self._nodes

    def has_edge(self, a: str, b: str) -> bool:
        """Return whether an edge connects *a* and *b*."""
        return a in self._adj and b in self._adj[a]

    def nodes(self) -> dict[str, dict]:
        """Return a mapping of node id to its attribute dict."""
        return dict(self._nodes)

    def edges(self) -> dict[tuple[str, str], dict]:
        """Return edges keyed by ``(min, max)`` node ids with attribute dicts."""
        seen: set[tuple[str, str]] = set()
        result: dict[tuple[str, str], dict] = {}
        for a, nbrs in self._adj.items():
            for b, attrs in nbrs.items():
                key = (a, b) if a <= b else (b, a)
                if key not in seen:
                    seen.add(key)
                    result[key] = dict(attrs)
        return result

    def neighbors(self, node: str) -> dict[str, dict]:
        """Return a mapping of *node*'s neighbors to their edge attribute dicts."""
        return dict(self._adj.get(node, {}))

    def edge_attrs(self, a: str, b: str) -> dict | None:
        """Return the attribute dict of the edge ``a``-``b``, or ``None``."""
        if not self.has_edge(a, b):
            return None
        return dict(self._adj[a][b])

    def degree(self, node: str) -> int:
        """Return the number of edges incident to *node*."""
        return len(self._adj.get(node, {}))

    def __len__(self) -> int:
        return len(self._nodes)

    def __contains__(self, node: object) -> bool:
        return self.has_node(node)  # type: ignore[arg-type]

    def shortest_path(self, a: str, b: str) -> list[str] | None:
        """Return a shortest path from *a* to *b* via BFS, or ``None`` if unreachable."""
        if not self.has_node(a) or not self.has_node(b):
            return None
        prev: dict[str, str | None] = {a: None}
        queue: deque[str] = deque([a])
        while queue:
            cur = queue.popleft()
            if cur == b:
                break
            for nbr in self._adj[cur]:
                if nbr not in prev:
                    prev[nbr] = cur
                    queue.append(nbr)
        if b not in prev:
            return None
        path = [b]
        while prev[path[-1]] is not None:
            path.append(prev[path[-1]])  # type: ignore[arg-type]
        path.reverse()
        return path

    def connected_components(self) -> list[set[str]]:
        """Return the connected components as a list of node sets."""
        seen: set[str] = set()
        comps: list[set[str]] = []
        for node in self._nodes:
            if node in seen:
                continue
            comp: set[str] = set()
            queue: deque[str] = deque([node])
            seen.add(node)
            while queue:
                cur = queue.popleft()
                comp.add(cur)
                for nbr in self._adj[cur]:
                    if nbr not in seen:
                        seen.add(nbr)
                        queue.append(nbr)
            comps.append(comp)
        return comps

    def is_connected(self) -> bool:
        """Return whether all nodes form a single connected component."""
        return len(self.connected_components()) <= 1

    def to_networkx(self):
        """Return an equivalent ``networkx.Graph`` (requires networkx)."""
        import networkx as nx

        g = nx.Graph()
        for node, attrs in self._nodes.items():
            g.add_node(node, **attrs)
        for (a, b), attrs in self.edges().items():
            g.add_edge(a, b, **attrs)
        return g
