"""
Wall Graph Demo — L, T, and U-shaped walls from vertices + edges.
"""

from __future__ import annotations

from ifckit import IfcModel, LengthUnit
from ifckit.builders._geom import get_body_context
from ifckit.elements.wall_graph import PendingWallGraph
from ifckit.geometry import Plane, Vec


def _build_and_save(pending, name, filename):
    model = IfcModel(unit=LengthUnit.MILLIMETRE)
    site = model.add_site(name="Site")
    building = model.add_building(site, name="Building")
    storey = model.add_storey(building, name="Storey", elevation=0.0)
    ctx = get_body_context(model.ifc_file)
    handle = model.add(pending, storey)
    geom = handle.entity.Representation.Representations[0].Items[0]
    geom = handle.entity.Representation.Representations[0].Items[0]
    if hasattr(geom, "Coordinates"):
        verts = len(geom.Coordinates.CoordList)
    else:
        verts = 0
    cls = geom.is_a()
    print(f"  {name}: {cls} (CSG tree, {verts} direct vertices)")
    model.save(f"output/{filename}")
    print(f"  Saved: output/{filename}")


XY = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))


# ---------------------------------------------------------------------------
# 1. L-wall
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
# 2. T-wall
# ---------------------------------------------------------------------------


def build_t_wall() -> None:
    verts = [
        Vec(0, 0, 0),
        Vec(6000, 0, 0),
        Vec(3000, 0, 0),
        Vec(3000, -3000, 0),
    ]
    pending = PendingWallGraph(
        vertices=verts,
        edges=[(0, 1), (2, 3), (1, 2)],
        plane=XY,
        thickness=200,
        height=3000,
        name="T_wall",
    )
    _build_and_save(pending, "T-wall", "wall_graph_T.ifc")


# ---------------------------------------------------------------------------
# 3. U-wall
# ---------------------------------------------------------------------------


def build_u_wall() -> None:
    verts = [
        Vec(0, 0, 0),
        Vec(5000, 0, 0),
        Vec(5000, 4000, 0),
        Vec(0, 4000, 0),
    ]
    pending = PendingWallGraph(
        vertices=verts,
        edges=[(0, 1), (1, 2), (2, 3)],
        plane=XY,
        thickness=200,
        height=3000,
        name="U_wall",
    )
    _build_and_save(pending, "U-wall", "wall_graph_U.ifc")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os

    os.makedirs("output", exist_ok=True)

    print("=== Wall Graph Demo ===\n")

    print("1. L-wall (2 segments, 90° corner):")
    build_l_wall()

    print("\n2. T-wall (3 segments, T-junction):")
    build_t_wall()

    print("\n3. U-wall (3 segments, open U shape):")
    build_u_wall()

    print(
        "\nDone. Open the .ifc files in Bonsai / any IFC viewer."
        "\nCheck junctions for proper boolean union."
    )
