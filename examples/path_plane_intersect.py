#!/usr/bin/env python3
"""
Path / Plane intersection example.

Shows how to find where a 3D Path crosses an arbitrary Plane.
"""

from ifckit.geometry import Path, Plane, Vec


def main():
    # ── Example 1: open line crossing a plane ───────────────────────

    line = Path()
    line.add_line(Vec(0, 0, 0), Vec(10, 20, 30))

    plane = Plane(Vec(0, 0, 15), Vec(1, 0, 0), Vec(0, 1, 0))  # z = 15

    hits = line.intersect_plane(plane)
    print("Example 1 — line (0,0,0)→(10,20,30) ∩ z=15")
    for t, pt in hits:
        print(f"  t={t:.4f}  point=({pt.x:.2f}, {pt.y:.2f}, {pt.z:.2f})")
    print()

    # ── Example 2: closed polygon with a sloped cut ────────────────

    pts = [
        Vec(0, 0, 0),
        Vec(10, 0, 0),
        Vec(10, 10, 10),
        Vec(0, 10, 10),
    ]
    ramp = Path.from_pts(pts, closed=True)

    cut = Plane(Vec(0, 0, 5), Vec(1, 0, 0), Vec(0, 1, 0))  # z = 5

    hits = ramp.intersect_plane(cut)
    print("Example 2 — closed ramp ∩ z=5")
    for t, pt in hits:
        print(f"  t={t:.4f}  point=({pt.x:.2f}, {pt.y:.2f}, {pt.z:.2f})")
    print(f"  → {len(hits)} intersection(s) — enter & exit")
    print()

    # ── Example 3: mixed line + arc crossing a plane ───────────────

    curve = Path()
    curve.add_line(Vec(0, 0, 0), Vec(5, 5, 5))  # line to sphere surface
    curve.add_arc(
        Vec(5, 5, 5),        # center
        Vec(0, 0, 1),        # normal (z)
        Vec(10, 0, 5),       # start
        -3.14159,            # -180° (CW half-circle back to start)
    )

    mid = Plane(Vec(0, 4, 0), Vec(1, 0, 0), Vec(0, 0, 1))  # y = 4

    hits = curve.intersect_plane(mid)
    print("Example 3 — line + arc ∩ y=4")
    for t, pt in hits:
        print(f"  t={t:.4f}  point=({pt.x:.2f}, {pt.y:.2f}, {pt.z:.2f})")
    print()


if __name__ == "__main__":
    main()
