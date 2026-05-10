"""
Wall Graph Demo — L, T, U, X, Arc, and closed-path walls.

Edge-mode scenarios (1–4) now use Shapely offset-based geometry:
all edges are buffered as a MultiLineString and merged into a single
closed polygon → one IfcExtrudedAreaSolid per wall, no boolean trees.
T- and X-junctions are handled by Shapely's miter join style.

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
# 1. L-wall (graph mode — offset-based)
# ---------------------------------------------------------------------------

def build_l_wall() -> None:
    verts = [
        Vec(0, 0, 0),
        Vec(5000, 0, 0),
        Vec(3000, 3000, 0),
        Vec(1000, -3000, 0),
    ]
    pending = PendingWallGraph(
        vertices=verts,
        edges=[(0, 1), (1, 2), (1, 3)],
        plane=XY,
        thickness=200,
        height=3000,
        name="L_wall",
    )
    _build_and_save(pending, "L-wall", "wall_graph_L.ifc")


# ---------------------------------------------------------------------------
# 2. T-wall (graph mode — offset-based, T-junction mitered by Shapely)
# ---------------------------------------------------------------------------

def build_t_wall() -> None:
    pending = PendingWallGraph(
        vertices=[Vec(0, 0, 0), Vec(6000, 0, 0), Vec(3000, 0, 0), Vec(3000, -3000, 0)],
        edges=[(0, 1), (2, 3)],
        plane=XY,
        thickness=200,
        height=3000,
        name="T_wall",
    )
    _build_and_save(pending, "T-wall", "wall_graph_T.ifc")


# ---------------------------------------------------------------------------
# 3. U-wall (graph mode — offset-based, open ends capped)
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
# 4. X-wall (graph mode — offset-based, X-junction mitered by Shapely)
# ---------------------------------------------------------------------------

def build_x_wall() -> None:
    """Cross-shaped (X) wall: 4 arms meeting at a central junction."""
    pending = PendingWallGraph(
        vertices=[
            Vec(3000, 0, 0),    # 0 — south end
            Vec(3000, 6000, 0), # 1 — north end
            Vec(0, 3000, 0),    # 2 — west end
            Vec(6000, 3000, 0), # 3 — east end
            Vec(3000, 3000, 0), # 4 — center
        ],
        edges=[(0, 4), (4, 1), (2, 4), (4, 3)],
        plane=XY,
        thickness=200,
        height=3000,
        name="X_wall",
    )
    _build_and_save(pending, "X-wall", "wall_graph_X.ifc")


# ---------------------------------------------------------------------------
# 4. Arc wall (path mode)
# ---------------------------------------------------------------------------

def build_arc_wall() -> None:
    """Curved wall from an open Path with Arc segments."""
    path = Path()
    path.add_line(Vec(0, 0, 0), Vec(2000, 0, 0))
    path.add_arc(Vec(2000, 2000, 0), Vec(0, 0, 1), Vec(2000, 0, 0), math.pi)
    path.add_line(Vec(0, 4000, 0), Vec(-2000, 4000, 0))
    path.add_line(Vec(-2000, 4000, 0), Vec(-2000, 0, 0))

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
    print("1. L-wall (graph mode — offset):")
    build_l_wall()
    print("\n2. T-wall (graph mode — offset, T-junction):")
    build_t_wall()
    print("\n3. U-wall (graph mode — offset, open ends capped):")
    build_u_wall()
    print("\n4. X-wall (graph mode — offset, X-junction):")
    build_x_wall()
    print("\n5. Arc wall (path mode):")
    build_arc_wall()
    print("\n6. Closed rect wall (path mode):")
    build_closed_rect_wall()
    print("\n7. Closed rect with fillet (path mode):")
    build_fillet_rect_wall()
    print("\nDone.")
