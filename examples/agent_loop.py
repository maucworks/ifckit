#!/usr/bin/env python3
# This file was generated with the assistance of an AI coding tool.
"""
Agent-loop voorbeeld: programma-graaf → IFC, grof naar fijn.

Demonstreert de lus met een *gestubde* LLM. In plaats van code te genereren,
bouwen ``_build_spaces`` en ``_build_walls`` de geometrie deterministisch.
Vervang die functies door een echte LLM-aanroep om de lus live te maken.

De lus: S0 (ruimten) → poort → S1 (wanden) → poort → S2 (openingen).
Elke ronde produceert een plan-SVG en een gestructureerd rapport; de poort is
``conform(model, program)`` tegen de gerealiseerde graaf.

Usage:
    python examples/agent_loop.py
"""

from pathlib import Path

from ifckit import IfcModel, PendingWall
from ifckit.geometry import Plane, Vec
from ifckit.inspect import report
from ifckit.render import snapshot
from ifckit.spatial import ProgramEdge, ProgramSpace, RoomProgram, conform

OUT = Path(__file__).parent / "output"
DEPTH = 4.0  # kamerdiepte


def make_program() -> RoomProgram:
    """Het programma van eisen als getypeerde graaf."""
    return RoomProgram(
        nodes={
            "k": ProgramSpace(name="1.01", long_name="Keuken", area_min=8, area_max=15),
            "w": ProgramSpace(name="1.02", long_name="Woonkamer", area_min=20, area_max=30),
            "buiten": ProgramSpace(name="buiten", exterior=True),
        },
        edges=[
            ProgramEdge("k", "buiten", kind="facade"),
            ProgramEdge("w", "buiten", kind="facade"),
            ProgramEdge("k", "w", kind="wall", required=False),
        ],
    )


def _rooms(program: RoomProgram) -> list[tuple[str, str, float]]:
    """(naam, omschrijving, breedte) per te realiseren ruimte."""
    rooms = []
    for space in program.nodes.values():
        if space.name in ("", "buiten"):
            continue
        target = space.area_min if space.area_min else (space.area_max or 12.0)
        rooms.append((space.name, space.long_name, max(target, 3.0) / DEPTH))
    return rooms


def _build_spaces(storey, program: RoomProgram) -> None:
    """STUB (LLM): leg ruimten naast elkaar neer op S0."""
    x = 0.0
    for name, long_name, width in _rooms(program):
        storey.add_space(
            [Vec(x, 0, 0), Vec(x + width, 0, 0), Vec(x + width, DEPTH, 0), Vec(x, DEPTH, 0)],
            height=2.7,
            name=name,
            long_name=long_name,
        )
        x += width


def _build_walls(storey, program: RoomProgram) -> None:
    """STUB (LLM): voeg twee verbonden wanden toe op S1."""
    total = sum(w for _, _, w in _rooms(program))
    plane = Plane.world_xy()
    storey.add(
        PendingWall(
            [Vec(0, 0, 0), Vec(total, 0, 0), Vec(total, 0.2, 0), Vec(0, 0.2, 0)],
            plane=plane,
            height=2.7,
            name="W-bodem",
        )
    )
    storey.add(
        PendingWall(
            [
                Vec(total, 0, 0),
                Vec(total + 0.2, 0, 0),
                Vec(total + 0.2, DEPTH, 0),
                Vec(total, DEPTH, 0),
            ],
            plane=plane,
            height=2.7,
            name="W-rechts",
        )
    )


def main() -> None:
    program = make_program()
    model = IfcModel(name="AgentLoop")
    site = model.add_site("S")
    building = model.add_building(site, "B")
    storey = model.add_storey(building, "00", elevation=0.0)
    OUT.mkdir(exist_ok=True)

    # ── S0: ruimten ────────────────────────────────────────────────────────
    _build_spaces(storey, program)
    snap = snapshot(model, stage="S0")
    (OUT / "s0.svg").write_bytes(snap.svgs["plan"])
    rep = report(model, stage="S0")
    con = conform(model, program)
    total_area = sum(s["area"] or 0.0 for s in rep.spaces)
    print(f"[S0] {len(rep.spaces)} ruimten, {total_area:.1f} m²")
    print(
        f"[S0] conform ok={con.ok} satisfied={len(con.satisfied)} "
        f"violated={len(con.violated)} missing={len(con.missing)}"
    )
    if not con.ok:
        print("      poort faalt — LLM moet bijsturen")
        return

    # ── S1: wanden ─────────────────────────────────────────────────────────
    _build_walls(storey, program)
    snap = snapshot(model, stage="S1")
    (OUT / "s1.svg").write_bytes(snap.svgs["plan"])
    rep = report(model, stage="S1")
    print(
        f"[S1] {rep.elements.get('Wall', 0)} wanden, "
        f"{rep.elements.get('isolated_walls', 0)} geïsoleerd"
    )
    for w in rep.warnings:
        print(f"      waarschuwing: {w}")

    # ── S2: openingen (stub: nog geen openingen) ───────────────────────────
    rep = report(model, stage="S2")
    print(
        f"[S2] {rep.elements.get('Door', 0)} deuren, "
        f"{rep.elements.get('Window', 0)} ramen, "
        f"{rep.elements.get('OpeningElement', 0)} openingen"
    )
    snap = snapshot(model, stage="S2")
    (OUT / "s2.svg").write_bytes(snap.svgs["plan"])

    print(f"Klaar. SVG's in {OUT}/")


if __name__ == "__main__":
    main()
