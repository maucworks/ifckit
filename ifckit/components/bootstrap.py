#!/usr/bin/env python3
"""Bootstrap a new Python generative component.

Usage:
    python ifckit/components/bootstrap.py
    python ifckit/components/bootstrap.py folding_door
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHONIC_DIR = os.path.join(HERE, "pythonic")

TEMPLATE = '''\
"""
{name} — Python generative component for {ifc_class}.
"""
from ifckit.builders._geom import axis2placement3d, extrude_profile, profile_from_points
from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.components import EvaluatedComponent, FillComponent
from ifckit.geometry import Path, Plane, Vec
from ifckit.profiles import RectangleProfile


ALUMINUM = {{
    "color": {{"r": 0.8, "g": 0.8, "b": 0.8}},
    "transparency": 0.0,
    "name": "Aluminum frame",
}}

GLASS = {{
    "color": {{"r": 0.9, "g": 0.95, "b": 1.0}},
    "transparency": 0.5,
    "name": "Clear glass",
}}

VOID = {{
    "color": {{"r": 0.5, "g": 0.5, "b": 0.5}},
    "transparency": 1.0,
    "name": "Opening void",
}}


class {class_name}(FillComponent):
    """Generative component for {ifc_class}."""

    ifc_class = "{ifc_class}"

    def build(self, ifc_file, plane, w, h, params):
        lt = float(params.get("lining_thickness", 55))
        ld = float(params.get("lining_depth", 70))
        gd = float(params.get("panel_depth", 6))
        wt = float(params.get("wall_thickness", 200))
        wx = float(w)
        wy = float(h)

        comps = []

        # ── Opening ───────────────────────────────────────────────────
        opening = profile_from_points(
            ifc_file, [(0.0, 0.0), (wx, 0.0), (wx, wy), (0.0, wy)]
        )
        opening_solid = extrude_profile(
            ifc_file, opening, depth=wt * 2, extrude_direction=(0, 0, -1),
        )
        comps.append(EvaluatedComponent(solid=opening_solid, role="Opening", material=VOID))

        # ── Lining ────────────────────────────────────────────────────
        if lt > 0 and ld > 0:
            spine = Path.from_pts(
                [Vec(0, 0, 0), Vec(wx, 0, 0), Vec(wx, wy, 0), Vec(0, wy, 0)],
                plane=Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
                closed=True,
            )
            spine.fillet([0, 1, 2, 3], wx / 2.1)

            starter = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
            profile = RectangleProfile(ld, lt)
            profile.anchor = "w"

            lining_solid = SectionedSpineBuilder().tessellate_spine(
                ifc_file,
                spine=spine,
                profile=profile,
                starter_plane=starter,
                angle_step_deg=float(params.get("angle_step_deg", 3.0)),
                profile_segments=int(params.get("profile_segments", 16)),
            )
            comps.append(
                EvaluatedComponent(solid=lining_solid, role="Lining", material=ALUMINUM)
            )

        # ── Glazing ──────────────────────────────────────────────────
        if wx > 2 * lt and wy > 2 * lt and gd > 0:
            glass = profile_from_points(
                ifc_file,
                [(lt, lt), (wx - lt, lt), (wx - lt, wy - lt), (lt, wy - lt)],
            )
            z_off = -(ld / 2 - gd / 2)
            pos = axis2placement3d(ifc_file, Vec(0, 0, z_off), Vec(0, 0, 1), Vec(1, 0, 0))
            glass_solid = extrude_profile(
                ifc_file, glass, depth=gd, position=pos, extrude_direction=(0, 0, -1),
            )
            comps.append(EvaluatedComponent(solid=glass_solid, role="Glazing", material=GLASS))

        return comps
'''


IFC_CLASSES = [
    "IfcWindow",
    "IfcDoor",
    "IfcPlate",
    "IfcShadingDevice",
    "IfcCurtainWall",
    "IfcRailing",
]


def to_pascal(snake: str) -> str:
    return "".join(word.capitalize() for word in snake.split("_"))


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else ""

    if not raw:
        raw = input("Component name (e.g. folding_door): ").strip()

    raw = raw.replace("-", "_")
    if raw.endswith("_component"):
        raw = raw[: -len("_component")]

    component_name = raw
    class_name = to_pascal(raw) + "Component"
    filename = f"{raw}_component.py"
    filepath = os.path.join(PYTHONIC_DIR, filename)

    if os.path.exists(filepath):
        print(f"  ERROR: {filepath} already exists.")
        sys.exit(1)

    print("\nIFC classes:")
    for i, c in enumerate(IFC_CLASSES):
        print(f"  [{i}] {c}")
    class_idx = input("  Choose [0]: ").strip()
    ifc_class = (
        IFC_CLASSES[int(class_idx)]
        if class_idx.isdigit() and int(class_idx) < len(IFC_CLASSES)
        else "IfcWindow"
    )

    display_name = input(f"  Display name [{component_name.replace('_', ' ').title()}]: ").strip()
    if not display_name:
        display_name = component_name.replace("_", " ").title()

    rendered = TEMPLATE.format(
        name=display_name,
        ifc_class=ifc_class,
        class_name=class_name,
    )
    with open(filepath, "w") as f:
        f.write(rendered)
    print(f"\n  Created {filepath}")
    print("\nJSON usage:")
    print(f'  {{"component_graph": "{component_name}", "parameters": {{}}}}')
    print(f"  Registered with keys: '{component_name}' and '{component_name}_component'")


if __name__ == "__main__":
    main()
