#!/usr/bin/env python3
"""
Polygon Boolean operations on Path (intersection, union, difference).

Requires ``shapely`` (optional dep).  Install with::

    pip install shapely
"""

import sys

from ifckit.geometry import Path, Plane, Vec


def _fmt(path: Path) -> str:
    n = len(path.segments)
    pts = path.sample(5).points
    return f"Path({n} segs, {len(pts)} pts, area≈{_approx_area(pts):.1f})"


def _approx_area(pts) -> float:
    """Shoelace area of sampled polygon points (2D, XY plane)."""
    n = len(pts)
    a = 0.0
    for i in range(n):
        j = (i + 1) % n
        a += pts[i].x * pts[j].y - pts[j].x * pts[i].y
    return abs(a) / 2.0


def main():
    if not Path._shapely_available():
        print("ERROR: shapely not installed.  Run:  pip install shapely")
        sys.exit(1)

    xy = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))

    # Two overlapping rectangles
    a = Path.from_pts(
        [Vec(0, 0, 0), Vec(10, 0, 0), Vec(10, 10, 0), Vec(0, 10, 0)],
        plane=xy, closed=True,
    )
    b = Path.from_pts(
        [Vec(5, 5, 0), Vec(15, 5, 0), Vec(15, 15, 0), Vec(5, 15, 0)],
        plane=xy, closed=True,
    )

    # ── Intersection (AND) ─────────────────────────────────────────
    inter = a.intersect(b)
    print("A ∩ B")
    for p in inter:
        print(f"  {_fmt(p)}")

    # ── Union (OR) ─────────────────────────────────────────────────
    uni = a.union(b)
    print("A ∪ B")
    for p in uni:
        print(f"  {_fmt(p)}")

    # ── Difference (SUBTRACT) ──────────────────────────────────────
    diff = a.difference(b)
    print("A \\ B")
    for p in diff:
        print(f"  {_fmt(p)}")

    # ── Operator sugar ─────────────────────────────────────────────
    same = a & b
    print(f"A & B  (same as intersect): {len(same)} result(s)")

    combined = a | b
    print(f"A | B  (same as union):     {len(combined)} result(s)")

    trimmed = a - b
    print(f"A - B  (same as difference): {len(trimmed)} result(s)")

    # ── Non-overlapping shapes → empty result ─────────────────────
    c = Path.from_pts(
        [Vec(20, 20, 0), Vec(30, 20, 0), Vec(30, 30, 0), Vec(20, 30, 0)],
        plane=xy, closed=True,
    )
    disjoint = a.intersect(c)
    print(f"A ∩ (far away) = empty: {len(disjoint) == 0}")


if __name__ == "__main__":
    main()
