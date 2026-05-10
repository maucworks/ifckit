"""
Wall Graph Demo — L, T, U, Arc, and closed-path walls.

Usage:
    python examples/wall_graph_demo.py
"""
from __future__ import annotations

import math

from ifckit import IfcModel, LengthUnit
from ifckit.builders._geom import get_body_context
from ifckit.elements.wall_graph import PendingWallGraph
from ifckit.geometry import Path, Plane, Vec


def _build_and_save(pending, name, filename):
    model = IfcModel(unit=LengthUnit.MILLIMETRE)
    site = model.add_site(name="Site")
    building = model.add_building(site, name="Building")
    storey = model.add_storey(building, name="Storey", elevation=0.0)
    ctx = get_body_context(model.ifc_file)
    handle = model.add(pending, storey)
    geom = handle.entity.Representation.Representations[0].Items[0]
    if hasattr(geom, "Coordinates"):
        verts = len(geom.Coordinates.CoordList)
    else:
        verts = 0
    cls = geom.is_a()
    print(f"  {name}: {cls} ({verts} direct verts)")
    model.save(f"output/{filename}")
    print(f"  Saved: output/{filename}")


XY = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))


# ---------------------------------------------------------------------------
# 1. L-wall (edge mode)
# ---------------------------------------------------------------------------

def build_l_wall() -> None:
    pending = PendingWallGraph(
        vertices=[Vec(0, 0, 0), Vec(5000, 0, 0), Vec(5000, 3000, 0)],
        edges=[(0, 1), (1, 2)],
        plane=XY,
        thickness=200,
        height=3000,
        name="L_wall",
    )
    _build_and_save(pending, "L-wall", "wall_graph_L.ifc")


# ---------------------------------------------------------------------------
# 2. T-wall (edge mode)
# ---------------------------------------------------------------------------

def build_t_wall() -> None:
    pending = PendingWallGraph(
        vertices=[Vec(0, 0, 0), Vec(6000, 0, 0), Vec(3000, 0, 0), Vec(3000, -3000, 0)],
        edges=[(0, 1), (2, 3), (1, 2)],
        plane=XY,
        thickness=200,
        height=3000,
        name="T_wall",
    )
    _build_and_save(pending, "T-wall", "wall_graph_T.ifc")


# ---------------------------------------------------------------------------
# 3. U-wall (edge mode)
# ---------------------------------------------------------------------------

def build_u_wall() -> None:
    pending = PendingWallGraph(
        vertices=[Vec(0, 0, 0), Vec(5000, 0, 0), Vec(5000, 4000, 0), Vec(0, 4000, 0)],
        edges=[(0, 1), (1, 2), (2, 3)],
        plane=XY,
        thickness=200,
        height=3000,
        name="U_wall",
    )
    _build_and_save(pending, "U-wall", "wall_graph_U.ifc")


# ---------------------------------------------------------------------------
# 4. Arc wall (path mode)
# ---------------------------------------------------------------------------

def build_arc_wall() -> None:
    """Curved wall from a Path with Arc segments."""
    path = Path()
    path.add_line(Vec(0, 0, 0), Vec(2000, 0, 0))
    path.add_arc(Vec(2000, 2000, 0), Vec(0, 0, 1), Vec(2000, 0, 0), math.pi)
    path.add_line(Vec(0, 4000, 0), Vec(-2000, 4000, 0))
    path.add_line(Vec(-2000, 4000, 0), Vec(-2000, 0, 0))
    path.add_line(Vec(-2000, 0, 0), Vec(0, 0, 0))

    pending = PendingWallGraph(
        path=path,
        thickness=200,
        height=3000,
        name="Arc_wall",
        angle_step_deg=5.0,
    )
    _build_and_save(pending, "Arc-wall (Path with arc)", "wall_graph_arc.ifc")


# ---------------------------------------------------------------------------
# 5. Closed rectangle wall (path mode)
# ---------------------------------------------------------------------------

def build_closed_rect_wall() -> None:
    """Closed rectangular perimeter wall from a Path."""
    path = Path.from_pts(
        [Vec(0, 0, 0), Vec(4000, 0, 0), Vec(4000, 3000, 0), Vec(0, 3000, 0)],
        plane=XY,
        closed=True,
    )
    pending = PendingWallGraph(
        path=path,
        thickness=200,
        height=3000,
        name="Closed_rect_wall",
    )
    _build_and_save(pending, "Closed rect (Path)", "wall_graph_closed_rect.ifc")


# ---------------------------------------------------------------------------
# 6. Closed rectangle with fillet on all corners (path mode)
# ---------------------------------------------------------------------------

def build_fillet_rect_wall() -> None:
    """Closed rectangular perimeter wall with rounded corners (R=800)."""
    path = Path.from_pts(
        [Vec(0, 0, 0), Vec(4000, 0, 0), Vec(4000, 3000, 0), Vec(0, 3000, 0)],
        plane=XY,
        closed=True,
    )
    path.fillet([0, 1, 2, 3], 800)

    pending = PendingWallGraph(
        path=path,
        thickness=200,
        height=3000,
        name="Fillet_rect_wall",
    )
    _build_and_save(pending, "Fillet rect (Path + fillet)", "wall_graph_fillet_rect.ifc")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    os.makedirs("output", exist_ok=True)

    print("=== Wall Graph Demo ===\n")
    print("1. L-wall (edge mode):")
    build_l_wall()
    print("\n2. T-wall (edge mode):")
    build_t_wall()
    print("\n3. U-wall (edge mode):")
    build_u_wall()
    print("\n4. Arc wall (path mode):")
    build_arc_wall()
    print("\n5. Closed rect wall (path mode):")
    build_closed_rect_wall()
    print("\n6. Closed rect with fillet (path mode):")
    build_fillet_rect_wall()
    print("\nDone.")
