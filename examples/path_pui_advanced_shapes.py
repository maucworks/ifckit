"""
Example: PathPui with Various Window Outlines

Demonstrates creating windows with different outline shapes using PathPui:
  - Large rectangular opening
  - Smaller square opening
  - Tall narrow opening (like a panel)

PathPui can work with any closed Path, enabling various window geometries.
Advanced shapes (circular, octagonal, etc.) can be created by defining
custom Path objects with appropriate geometry primitives (Arc, Line, etc.).
"""

from ifckit import IfcModel, PendingWindow
from ifckit import PendingWall
from ifckit.geometry import Vec, Plane, Path
from ifckit.schema import IfcSchema


def create_large_rectangular_path(center_x: float, center_y: float) -> Path:
    """Create a large rectangular path."""
    return Path.from_pts(
        [
            Vec(center_x - 0.75, center_y - 0.6, 0),
            Vec(center_x + 0.75, center_y - 0.6, 0),
            Vec(center_x + 0.75, center_y + 0.6, 0),
            Vec(center_x, center_y + 1, 0),
            Vec(center_x - 0.75, center_y + 0.6, 0),
        ],
        plane=Plane.world_xy(),
        closed=True,
    )


def create_square_path(center_x: float, center_y: float, size: float) -> Path:
    """Create a square path."""
    half = size / 2
    return Path.from_pts(
        [
            Vec(center_x - half, center_y - half, 0),
            Vec(center_x + half, center_y - half, 0),
            Vec(center_x + half, center_y + half, 0),
            Vec(center_x, center_y + 2 * half, 0),
            Vec(center_x - half, center_y + half, 0),
        ],
        plane=Plane.world_xy(),
        closed=True,
    )


def create_tall_narrow_path(center_x: float, center_y: float) -> Path:
    """Create a tall narrow rectangular path (like a panel)."""
    return Path.from_pts(
        [
            Vec(center_x - 0.3, center_y - 0.8, 0),
            Vec(center_x + 0.3, center_y - 0.8, 0),
            Vec(center_x + 0.3, center_y + 0.8, 0),
            Vec(center_x, center_y + 1.2, 0),
            Vec(center_x - 0.3, center_y + 0.8, 0),
        ],
        plane=Plane.world_xy(),
        closed=True,
    )


def main():
    # =========================================================================
    # Setup
    # =========================================================================

    model = IfcModel(
        name="PathPui Advanced Shapes Example",
        schema=IfcSchema.IFC4,
        author="ifckit",
    )
    site = model.add_site("Site")
    bldg = site.add_building("Building")
    storey = bldg.add_storey("Ground", elevation=0.0)

    # =========================================================================
    # Wall 1: Large Rectangular Window
    # =========================================================================

    wall1 = PendingWall(
        footprint=[
            Vec(0, 0, 0),
            Vec(4, 0, 0),
            Vec(4, 0.3, 0),
            Vec(0, 0.3, 0),
        ],
        plane=Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
        height=3.0,
        name="Wall with Large Rectangular Window",
    )
    wall1_handle = storey.add(wall1)

    # Create large rectangular window
    large_rect_path = create_large_rectangular_path(0, 0)
    large_rect_window = PendingWindow(
        path=large_rect_path,
        component_graph="path_pui",
        plane=Plane(Vec(2, 0, 1), Vec(1, 0, 0), Vec(0, 0, 1)),
        parameters={
            "lining_thickness": 0.06,
            "lining_depth": 0.08,
            "glass_depth": 0.006,
            "wall_thickness": 0.3,
        },
        name="Large Rectangular Window",
    )
    model.add(large_rect_window, wall1_handle)
    print("✓ Wall 1 with large rectangular window created")

    # =========================================================================
    # Wall 2: Square Window
    # =========================================================================

    wall2 = PendingWall(
        footprint=[
            Vec(0, 0.0, 0),
            Vec(4, 0.0, 0),
            Vec(4, 0.3, 0),
            Vec(0, 0.3, 0),
        ],
        plane=Plane(Vec(0, 2, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
        height=3.0,
        name="Wall with Square Window",
    )
    wall2_handle = storey.add(wall2)

    # Create square window
    square_path = create_square_path(0, 0, 1.0)
    square_window = PendingWindow(
        path=square_path,
        component_graph="path_pui",
        plane=Plane(Vec(4, 0.0, 1), Vec(1, 0, 0), Vec(0, 0, 1)),
        parameters={
            "lining_thickness": 0.05,
            "lining_depth": 0.07,
            "glass_depth": 0.008,
            "wall_thickness": 0.3,
        },
        name="Square Window",
    )
    model.add(square_window, wall2_handle)
    print("✓ Wall 2 with square window created")

    # =========================================================================
    # Wall 3: Tall Narrow Window (Panel)
    # =========================================================================

    wall3 = PendingWall(
        footprint=[
            Vec(0, 2.0, 0),
            Vec(4, 2.0, 0),
            Vec(4, 2.3, 0),
            Vec(0, 2.3, 0),
        ],
        plane=Plane(Vec(4, 0.0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
        height=3.0,
        name="Wall with Tall Narrow Window",
    )
    wall3_handle = storey.add(wall3)

    # Create tall narrow window (panel style)
    tall_path = create_tall_narrow_path(0, 0)

    tall_window = PendingWindow(
        path=tall_path,
        component_graph="path_pui",
        plane=Plane(Vec(2, 2.0, -0.15), Vec(1, 0, 0), Vec(0, 0, 1)),
        parameters={
            "lining_thickness": 0.055,
            "lining_depth": 0.07,
            "glass_depth": 0.006,
            "wall_thickness": 0.3,
        },
        name="Tall Narrow Window (Panel)",
    )
    model.add(tall_window, wall3_handle)
    print("✓ Wall 3 with tall narrow window created")

    # =========================================================================
    # Save
    # =========================================================================

    output_path = "./output/path_pui_advanced_shapes.ifc"
    model.save(output_path)
    print(f"\n✓ Model saved: {output_path}")

    print(
        """
Window Outlines with PathPui:
  - Large Rectangular: 1.5m × 1.2m opening
  - Square: 1.0m × 1.0m opening
  - Tall Narrow Panel: 0.6m × 1.6m opening (portrait style)
  
All windows share the same PathPui component logic but with different
outline geometries. This demonstrates how PathPui adapts to any closed Path.

You can create even more complex shapes by defining custom Path objects
with Arc and Line segments for circular, octagonal, or other geometries.
"""
    )


if __name__ == "__main__":
    main()
