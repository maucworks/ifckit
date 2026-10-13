"""
ifckit.geometry.panel_report
============================

Buildability metrics for panel populations (Eigensatz 2010 vocabulary).

``field_report`` measures a cell population: edge-length spread (limited
size bandwidth), right-angle deviation and planarity per cell. Seam
divergence/kink tracking is a follow-up once populations map to IFC
products — the per-cell metrics here are its input. Pure Python.
"""

# This file was generated with the assistance of an AI coding tool.

from __future__ import annotations

import math
from dataclasses import dataclass
from dataclasses import field as _dc_field
from typing import Any, Dict, List, Optional

from ifckit.geometry.field import Field
from ifckit.geometry.primitives import Vec, _fmt_num, _new_id, _short_id


@dataclass(frozen=True)
class FieldReport:
    """Immutable metric snapshot of a panel population.

    Attributes:
        n_cells:      Number of measured cells.
        edge_min:     Smallest edge length.
        edge_mean:    Mean edge length.
        edge_max:     Largest edge length.
        angle_max_dev: Largest absolute deviation from the regular-polygon
            interior angle (90° for quads, 60° for triangles), in degrees.
        planarity_max: Largest distance of a corner to the plane of the
            first three (model units; always 0 for triangles).
    """

    type: str = "field_report"
    id: Optional[str] = None
    meta: Dict[str, Any] = _dc_field(default_factory=dict)
    n_cells: int = 0
    edge_min: float = 0.0
    edge_mean: float = 0.0
    edge_max: float = 0.0
    angle_max_dev: float = 0.0
    planarity_max: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain (JSON-safe) dict."""
        return {
            "type": self.type,
            "id": self.id,
            "meta": dict(self.meta),
            "n_cells": self.n_cells,
            "edge_min": self.edge_min,
            "edge_mean": self.edge_mean,
            "edge_max": self.edge_max,
            "angle_max_dev": self.angle_max_dev,
            "planarity_max": self.planarity_max,
        }

    def __str__(self) -> str:
        return (
            f"FieldReport(id={_short_id(self.id)}, n={self.n_cells}, "
            f"edge=[{_fmt_num(self.edge_min)}..{_fmt_num(self.edge_max)}], "
            f"angle_dev={_fmt_num(self.angle_max_dev)}°, "
            f"planar={_fmt_num(self.planarity_max)})"
        )


def cells_report(cells: List[List[Vec]]) -> FieldReport:
    """Measure a population of polygonal cells (any corner count ≥ 3).

    Args:
        cells: Corner lists (``[Vec × n]``), e.g. from ``patterns``.
            Mixed populations are measured jointly against their own
            regular-polygon angles.

    Returns:
        ``FieldReport`` with zeros when *cells* is empty.
    """
    edges: List[float] = []
    max_dev = 0.0
    max_flat = 0.0
    for poly in cells:
        n = len(poly)
        if n < 3:
            raise ValueError(f"Expected polygonal cells, got {n} corners")
        ref_angle = (n - 2) * 180.0 / n
        for k in range(n):
            p, q = poly[k], poly[(k + 1) % n]
            edges.append((q - p).length())
        for k in range(n):
            u, v = poly[(k - 1) % n] - poly[k], poly[(k + 1) % n] - poly[k]
            denom = u.length() * v.length()
            if denom < 1e-18:
                continue
            cos_a = max(-1.0, min(1.0, u.dot(v) / denom))
            max_dev = max(max_dev, abs(ref_angle - math.degrees(math.acos(cos_a))))
        a, b, c = poly[0], poly[1], poly[2]
        nrm = (b - a) ** (c - a)
        nl = nrm.length()
        if nl > 1e-18:
            for p in poly[3:]:
                max_flat = max(max_flat, abs((p - a).dot(nrm / nl)))
    if not edges:
        return FieldReport(id=_new_id())
    return FieldReport(
        id=_new_id(),
        n_cells=len(cells),
        edge_min=min(edges),
        edge_mean=sum(edges) / len(edges),
        edge_max=max(edges),
        angle_max_dev=max_dev,
        planarity_max=max_flat,
    )


def field_report(field: Field) -> FieldReport:
    """Measure the quad cells of a built field.

    Args:
        field: Built field (see ``ifckit.geometry.field``).

    Returns:
        ``FieldReport`` over ``field.cell_points()``.
    """
    rep = cells_report(field.cell_points())
    return FieldReport(
        id=_new_id(),
        meta={"field_id": field.id},
        n_cells=rep.n_cells,
        edge_min=rep.edge_min,
        edge_mean=rep.edge_mean,
        edge_max=rep.edge_max,
        angle_max_dev=rep.angle_max_dev,
        planarity_max=rep.planarity_max,
    )
