# This file was generated with the assistance of an AI coding tool.
"""Graaf-gedreven generatie-operatoren: deterministische geometrie uit het PvE.

De LLM roept deze operatoren aan in plaats van zelf coördinaten uit te
rekenen. Alles is deterministisch en zonder optionele dependencies.
"""

from __future__ import annotations

import math

from ifckit.geometry import Vec
from ifckit.spatial.program import ProgramSpace, RoomProgram

_TOL = 1e-9


def _rect_of(points: list[Vec]) -> tuple[float, float, float, float] | None:
    """Return (x0, y0, x1, y1) als *points* een as-uitgelijnde rechthoek is."""
    xs = sorted({round(p.x, 9) for p in points})
    ys = sorted({round(p.y, 9) for p in points})
    if len(xs) == 2 and len(ys) == 2 and len(points) >= 4:
        return (xs[0], ys[0], xs[1], ys[1])
    return None


def _rect_points(x0: float, y0: float, x1: float, y1: float) -> list[Vec]:
    """Rechthoekvoet als CCW Vec-lijst."""
    return [Vec(x0, y0, 0.0), Vec(x1, y0, 0.0), Vec(x1, y1, 0.0), Vec(x0, y1, 0.0)]


def place_space(
    program: RoomProgram,
    key: str,
    x0: float,
    y0: float,
    w: float | None = None,
    d: float | None = None,
) -> list[Vec]:
    """Plaats ruimte *key* als rechthoek met oorsprong (x0, y0).

    Afmetingen honoreren ``area_min``/``area_max``: geef beide, of één (de
    ander volgt uit ``area_min``), of geen (vierkant uit ``area_min``).
    """
    if key not in program.nodes:
        raise KeyError(f"place_space: onbekende knoop {key!r}")
    space = program.nodes[key]
    if space.area_min is None:
        raise ValueError(f"place_space: {key!r} heeft geen area_min")
    lo = space.area_min
    hi = space.area_max
    if w is not None and d is not None:
        if w <= 0 or d <= 0:
            raise ValueError(f"place_space: w en d moeten positief zijn, got {w!r}, {d!r}")
        area = w * d
        if area < lo - _TOL or (hi is not None and area > hi + _TOL):
            raise ValueError(
                f"place_space: {w!r}x{d!r} = {area:.2f} m² buiten [{lo}, {hi}] voor {key!r}"
            )
    elif w is not None:
        if w <= 0:
            raise ValueError(f"place_space: w moet positief zijn, got {w!r}")
        d = lo / w
    elif d is not None:
        if d <= 0:
            raise ValueError(f"place_space: d moet positief zijn, got {d!r}")
        w = lo / d
    else:
        w = d = math.sqrt(lo)
    return _rect_points(x0, y0, x0 + w, y0 + d)


def split_footprint(points: list[Vec], axis: str, at: float) -> tuple[list[Vec], list[Vec]]:
    """Splits een rechthoekige footprint langs ``x=at`` of ``y=at``."""
    rect = _rect_of(points)
    if rect is None:
        raise ValueError("split_footprint: alleen as-uitgelijnde rechthoeken")
    x0, y0, x1, y1 = rect
    if axis == "x":
        if not (x0 < at < x1):
            raise ValueError(f"split_footprint: at={at!r} buiten ({x0}, {x1})")
        return (_rect_points(x0, y0, at, y1), _rect_points(at, y0, x1, y1))
    if axis == "y":
        if not (y0 < at < y1):
            raise ValueError(f"split_footprint: at={at!r} buiten ({y0}, {y1})")
        return (_rect_points(x0, y0, x1, at), _rect_points(x0, at, x1, y1))
    raise ValueError(f"split_footprint: axis moet 'x' of 'y' zijn, got {axis!r}")


def mirror_footprint(points: list[Vec], axis: str, coord: float) -> list[Vec]:
    """Spiegel een footprint over de lijn ``x=coord`` of ``y=coord``.

    De winding blijft behouden (volgorde wordt omgekeerd).
    """
    if axis == "x":
        mirrored = [Vec(2.0 * coord - p.x, p.y, p.z) for p in points]
    elif axis == "y":
        mirrored = [Vec(p.x, 2.0 * coord - p.y, p.z) for p in points]
    else:
        raise ValueError(f"mirror_footprint: axis moet 'x' of 'y' zijn, got {axis!r}")
    return list(reversed(mirrored))


def add_room(program: RoomProgram, key: str, space: ProgramSpace) -> RoomProgram:
    """Voeg een knoop toe (GADG-additie). Faalt bij een bestaande sleutel."""
    if key in program.nodes:
        raise KeyError(f"add_room: {key!r} bestaat al")
    program.nodes[key] = space
    return program


def remove_room(program: RoomProgram, key: str) -> RoomProgram:
    """Verwijder een knoop plus alle kanten ernaartoe (GADG-subtractie)."""
    if key not in program.nodes:
        raise KeyError(f"remove_room: onbekende knoop {key!r}")
    del program.nodes[key]
    program.edges = [e for e in program.edges if e.a != key and e.b != key]
    return program


def layout_row(
    program: RoomProgram,
    keys: list[str],
    x0: float,
    y0: float,
    depth: float,
    gap: float = 0.0,
) -> dict[str, list[Vec]]:
    """Leg ruimten naast elkaar in een rij met vaste diepte.

    Elke ruimte krijgt breedte ``area_min / depth``. Deterministisch;
    samengesteld uit :func:`place_space`.
    """
    if depth <= 0:
        raise ValueError(f"layout_row: depth moet positief zijn, got {depth!r}")
    out: dict[str, list[Vec]] = {}
    x = x0
    for key in keys:
        if key not in program.nodes:
            raise KeyError(f"layout_row: onbekende knoop {key!r}")
        space = program.nodes[key]
        if space.area_min is None:
            raise ValueError(f"layout_row: {key!r} heeft geen area_min")
        w = space.area_min / depth
        out[key] = place_space(program, key, x, y0, w=w, d=depth)
        x += w + gap
    return out
