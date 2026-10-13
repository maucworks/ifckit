#!/usr/bin/env python3
"""Interactive preview session demo (PLAN-interactive-preview, I-7).

Holds one ModelSession across 3 slider ticks: only the changed wall is
rebuilt and re-tessellated per tick (coarse interactive preset), while
the full model stays intact. Final exact export via model.save().

Usage:
    python examples/preview_session.py
"""

from ifckit import ModelSession, PendingWall
from ifckit.geometry import Plane, Vec


def wall_element(height):
    return {
        **PendingWall(
            footprint=[Vec(0, 0, 0), Vec(5, 0, 0), Vec(5, 0.2, 0), Vec(0, 0.2, 0)],
            plane=Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
            height=height,
            name="W1",
        ).to_dict(),
        "id": "w1",
    }


def main():
    session = ModelSession()
    for i, height in enumerate((2.6, 3.0, 3.5), start=1):
        changed, payload = session.tick([wall_element(height)])
        (chunk,) = payload
        print(
            f"tick {i}: height={height:.1f} changed={len(changed)} "
            f"guid={chunk['guid']} verts={chunk['vertex_count']}"
        )
    out = "examples/output/preview_session.ifc"
    session.model.save(out)
    print(f"Saved exact model to {out}")


if __name__ == "__main__":
    main()
