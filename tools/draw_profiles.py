"""
tools/draw_profiles.py
======================

Render IBeamProfile and LBeamProfile as SVG files for visual inspection.

Usage::

    python tools/draw_profiles.py
    # writes: output/profile_i_beam.svg  output/profile_l_beam.svg

Each SVG shows all 9 anchor variants in a 3×3 grid.
A red dot marks the origin (0,0) for each anchor.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ifckit.profiles import IBeamProfile, LBeamProfile

ANCHORS = ['sw', 's', 'se', 'w', 'c', 'e', 'nw', 'n', 'ne']
COLS = 3


def profile_to_svg_path(points: list) -> str:
    """Convert (x, y) point list to SVG path string. Y is flipped (SVG Y-down)."""
    coords = " ".join(f"{'M' if i == 0 else 'L'}{x:.2f},{-y:.2f}" for i, (x, y) in enumerate(points))
    return coords + " Z"


def draw_profiles(profiles: list, title: str, output_path: str, margin: int = 20) -> None:
    """
    Draw a 3×3 grid of profiles (one per anchor) as SVG.

    Args:
        profiles: list of (anchor_label, points) tuples
        title:    SVG title / filename label
        output_path: where to write the SVG
        margin:   padding around each cell in SVG units
    """
    # Determine bounding box from first profile (all same size)
    all_x = [x for _, pts in profiles for x, y in pts]
    all_y = [y for _, pts in profiles for x, y in pts]
    w = max(all_x) - min(all_x)
    h = max(all_y) - min(all_y)

    cell_w = w + 2 * margin
    cell_h = h + 2 * margin + 20  # extra for label

    rows = (len(profiles) + COLS - 1) // COLS
    svg_w = cell_w * COLS
    svg_h = cell_h * rows + 30  # title bar

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
        f'style="background:#f8f8f8;font-family:monospace">',
        f'<text x="10" y="20" font-size="16" font-weight="bold" fill="#333">{title}</text>',
    ]

    for i, (anchor, pts) in enumerate(profiles):
        col = i % COLS
        row = i // COLS

        # Cell origin in SVG space
        cx = col * cell_w
        cy = row * cell_h + 30

        # Translate so that the bounding box is centred in the cell
        # Profile origin (0,0) maps to (cx + margin - min_x, cy + margin + max_y)
        pts_x = [x for x, y in pts]
        pts_y = [y for x, y in pts]
        tx = cx + margin - min(pts_x)
        ty = cy + cell_h - 20 - margin + max(pts_y)   # Y-flip: SVG origin top-left

        # Cell border only, no fill
        lines.append(
            f'<rect x="{cx}" y="{cy}" width="{cell_w}" height="{cell_h - 20}" '
            f'fill="none" stroke="#ccc" stroke-width="1"/>'
        )

        # Axis lines through origin
        ox = tx
        oy = ty
        lines.append(f'<line x1="{cx}" y1="{oy:.1f}" x2="{cx+cell_w}" y2="{oy:.1f}" stroke="#ddd" stroke-width="0.5"/>')
        lines.append(f'<line x1="{ox:.1f}" y1="{cy}" x2="{ox:.1f}" y2="{cy+cell_h}" stroke="#ddd" stroke-width="0.5"/>')

        # Profile path (transform via translate)
        path_d = " ".join(
            f"{'M' if j == 0 else 'L'}{tx + x:.2f},{ty - y:.2f}"
            for j, (x, y) in enumerate(pts)
        ) + " Z"
        lines.append(
            f'<path d="{path_d}" fill="none" '
            f'stroke="#2060a0" stroke-width="1.5"/>'
        )

        # Origin dot
        lines.append(
            f'<circle cx="{ox:.1f}" cy="{oy:.1f}" r="3" fill="red"/>'
        )

        # Anchor label
        label_y = cy + cell_h - 6
        lines.append(
            f'<text x="{cx + cell_w/2:.1f}" y="{label_y}" '
            f'text-anchor="middle" font-size="11" fill="#555">anchor=\'{anchor}\'</text>'
        )

    lines.append('</svg>')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
    print(f"Saved: {output_path}")


def main():
    # I-beam
    i_profiles = []
    for anchor in ANCHORS:
        p = IBeamProfile(height=60, width=30, web_thickness=2, flange_thickness=2, anchor=anchor)
        i_profiles.append((anchor, p.get_profile_points()))
    draw_profiles(i_profiles, "IBeamProfile — all anchors", "output/profile_i_beam.svg")

    # L-beam
    l_profiles = []
    for anchor in ANCHORS:
        p = LBeamProfile(height=50, width=40, thickness=4, anchor=anchor)
        l_profiles.append((anchor, p.get_profile_points()))
    draw_profiles(l_profiles, "LBeamProfile — all anchors", "output/profile_l_beam.svg")


if __name__ == "__main__":
    main()
