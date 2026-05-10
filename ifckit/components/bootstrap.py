#!/usr/bin/env python3
"""Bootstrap a new Python generative component.

Usage:
    python ifckit/components/bootstrap.py rounded_casement

Creates:
    ifckit/components/pythonic/rounded_casement_component.py  (template)
    Updates ifckit/components/pythonic/__init__.py             (import + __all__)

The component is ready to use — build_hello_wall immediately picks it up.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHONIC_DIR = os.path.join(HERE, "pythonic")
INIT_FILE = os.path.join(PYTHONIC_DIR, "__init__.py")

TEMPLATE = '''\
"""
{name} — Python generative window.
"""
from ifckit.builders._geom import (
    axis2placement3d,
    extrude_profile,
    profile_from_points,
)
from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.components import EvaluatedComponent, WindowComponent, component
from ifckit.geometry import Path, Plane, Vec
from ifckit.profiles import RectangleProfile


ALUMINUM = {{
    "color": {{"r": 0.8, "g": 0.8, "b": 0.8}},
    "transparency": 0.0,
    "name": "Aluminum frame",
}}

CLEAR_GLASS = {{
    "color": {{"r": 0.9, "g": 0.95, "b": 1.0}},
    "transparency": 0.5,
    "name": "Clear glass",
}}

OPENING_VOID = {{
    "color": {{"r": 0.5, "g": 0.5, "b": 0.5}},
    "transparency": 1.0,
    "name": "Opening void",
}}


@component("{component_name}")
class {class_name}(WindowComponent):
    name = "{component_name}"

    def build(self, ifc_file, plane, w, h, params):
        lt = float(params.get("lining_thickness", 55))
        ld = float(params.get("lining_depth", 70))
        wx = float(w)
        wy = float(h)

        comps = []

        # ── Opening void ──────────────────────────────────────────────
        opening_profile = profile_from_points(
            ifc_file, [(0.0, 0.0), (wx, 0.0), (wx, wy), (0.0, wy)]
        )
        opening_solid = extrude_profile(
            ifc_file,
            opening_profile,
            depth=float(params.get("wall_thickness", 200)) * 2,
            extrude_direction=(0, 0, -1),
        )
        comps.append(
            EvaluatedComponent(
                solid=opening_solid,
                role="Opening",
                node_id="opening_void",
                material=OPENING_VOID,
            )
        )

        # ── Lining ────────────────────────────────────────────────────
        if lt > 0 and ld > 0:
            a_step = float(params.get("angle_step_deg", 3.0))
            p_segs = int(params.get("profile_segments", 16))

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
                angle_step_deg=a_step,
                profile_segments=p_segs,
            )
            comps.append(
                EvaluatedComponent(
                    solid=lining_solid,
                    role="Lining",
                    node_id="lining",
                    material=ALUMINUM,
                )
            )

        return comps


{class_name}.register()
'''


def to_pascal(snake: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in snake.split("_"))


def ensure_init_imports(init_file: str, snake: str, class_name: str) -> None:
    """Add import + __all__ entry to pythonic/__init__.py."""
    with open(init_file) as f:
        content = f.read()

    module_line = (
        f"from ifckit.components.pythonic.{snake}_component import {class_name} as {class_name}"
    )
    if module_line in content:
        print(f"  Import already in {init_file}, skipping.")
        return

    # Find last "from ifckit.components.pythonic…" line and insert after
    lines = content.splitlines()
    insert_at = None
    for i, line in enumerate(lines):
        if line.startswith("from ifckit.components.pythonic"):
            insert_at = i

    if insert_at is not None:
        lines.insert(insert_at + 1, module_line)
    else:
        lines.insert(0, module_line)

    # Find __all__ list and add entry
    all_start = None
    all_end = None
    for i, line in enumerate(lines):
        if line.strip() == "__all__ = [":
            all_start = i
        if all_start is not None and line.strip() == "]":
            all_end = i
            break

    if all_end is not None:
        # Find last entry and insert before the closing bracket
        lines.insert(all_end, f'    "{class_name}",')

    content = "\n".join(lines) + "\n"
    with open(init_file, "w") as f:
        f.write(content)

    print(f"  Updated {init_file}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python ifckit/components/bootstrap.py <component_name>")
        print("  e.g. python ifckit/components/bootstrap.py folding_door")
        sys.exit(1)

    raw = sys.argv[1].strip()
    snake = raw.replace("-", "_")

    if snake.endswith("_component"):
        name = snake[: -len("_component")]
    else:
        name = snake

    component_name = name
    class_name = to_pascal(name) + "Component"
    filename = f"{name}_component.py"
    filepath = os.path.join(PYTHONIC_DIR, filename)

    if os.path.exists(filepath):
        print(f"  ERROR: {filepath} already exists.")
        sys.exit(1)

    # Write template
    rendered = TEMPLATE.format(
        name=component_name.replace("_", " ").title() + " Component",
        component_name=component_name,
        class_name=class_name,
    )
    with open(filepath, "w") as f:
        f.write(rendered)
    print(f"  Created {filepath}")

    # Update __init__.py
    ensure_init_imports(INIT_FILE, name, class_name)

    print(f"\nComponent '{component_name}' bootstrapped.  Build it:")
    print("")
    print("   json fragment:")
    print("     {")
    print(f'       "component_graph": "{component_name}",')
    print('       "parameters": {}')
    print("     }")
    print("")


if __name__ == "__main__":
    main()
