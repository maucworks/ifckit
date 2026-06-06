"""
Example: Path-based Window (PathPui) with Wall Graph

Demonstrates creating a gable wall with filleted corners using PendingWallGraph
and populating it with a path-based window using the PathPui component.

The window geometry is driven by a closed Path, allowing arbitrary outlines
like rounded pentagons, custom shapes, etc.

Features:
  - Gable wall using PendingWallGraph with path outline
  - Filleted corners (radius-based rounding)
  - Path-based window (PathPui) with:
    * Opening void through the wall
    * Perimeter aluminum frame
    * Glazing panel inset from frame
"""

from ifckit import IfcModel, PendingWindow
from ifckit.elements.wall_graph import PendingWallGraph
from ifckit.geometry import Vec, Plane, Path
from ifckit.schema import IfcSchema


def main():
    # =========================================================================
    # Setup: Create IFC Model
    # =========================================================================

    model = IfcModel(
        name="Path-Based Window Example",
        schema=IfcSchema.IFC4,
        author="ifckit",
    )
    site = model.add_site("Site")
    bldg = site.add_building("Building")
    storey = bldg.add_storey("Ground", elevation=0.0)

    # =========================================================================
    # Parameters
    # =========================================================================

    breedte = 4.0  # Width (m)
    diepte = 8.0  # Depth (m)
    radius = 1.0  # Fillet radius (m)
    hoogte = 3.0  # Wall height at eaves (m)
    nok_hoogte = 4.0  # Ridge height (m)
    dikte = 0.3  # Wall thickness (m)

    print(f"Building gable wall: {breedte}m wide × {diepte}m deep × {hoogte}m high (ridge: {nok_hoogte}m)")
    print(f"Wall thickness: {dikte}m, Fillet radius: {radius}m")

    # =========================================================================
    # Gable Wall with Filleted Path
    # =========================================================================

    # Create pentagonal outline (gable profile):
    #  (0, hoogte) -------- (breedte, hoogte)
    #       \              /
    #        \            /
    #         (0.5*breedte, nok_hoogte)   <- Ridge
    #        /            \
    #       /              \
    #  (0, 0) -------- (breedte, 0)

    outer = Path.from_pts(
        [
            Vec(0, 0, 0),
            Vec(breedte, 0, 0),
            Vec(breedte, hoogte, 0),
            Vec(0.5 * breedte, nok_hoogte, 0),
            Vec(0, hoogte, 0),
        ],
        plane=Plane(Vec(0, diepte, 0), Vec(1, 0, 0), Vec(0, 0, 1)),
        closed=True,
    )

    # Apply filleting to all corners
    outer.fillet([0, 1, 2, 3, 4], radius)

    # Create wall using graph-based generation
    muur = PendingWallGraph(
        path=outer,
        offset_right=0,  # No offset on right side
        offset_left=dikte,  # Offset by wall thickness on left side
        height=diepte,  # Extrude depth through the y-axis
        name="Gable Wall",
        angle_step_deg=5.0,  # Smooth tessellation of arcs
    )

    muur_handle = storey.add(muur)
    print(f"✓ Wall created: {muur_handle}")

    # =========================================================================
    # Path-Based Window (PathPui)
    # =========================================================================

    # Create a window using the same path outline as the wall.
    # PathPui will:
    #   1. Create an opening void matching the path
    #   2. Add an aluminum frame (boolean difference of outer - inner)
    #   3. Add a glazing panel inset from the frame

    raam = PendingWindow(
        path=outer,  # Use the same gable path
        component_graph="path_pui",  # Use built-in PathPui component
        plane=Plane(
            Vec(0, diepte, -0.15),  # Insert at wall back face, centered vertically
            Vec(1, 0, 0),  # X-axis = width direction
            Vec(0, 0, 1),  # Z-axis = up
        ),
        parameters={
            "lining_thickness": 0.055,  # 55mm frame inset
            "lining_depth": 0.07,  # 70mm frame depth
            "glass_depth": 0.006,  # 6mm glass thickness
            "wall_thickness": 0.3,  # Opening void depth (wall thickness)
        },
        name="Gable Window",
    )

    win_handle = model.add(raam, muur_handle)
    print(f"✓ Window created: {win_handle}")

    # =========================================================================
    # Save IFC Model
    # =========================================================================

    output_path = "examples/output/path_pui_example.ifc"
    model.save(output_path)
    print(f"\n✓ Model saved: {output_path}")

    # Print summary
    print(
        """
Summary:
  - Gable wall with filleted pentagonal profile
  - Path-based window (PathPui) with matching outline
  - Window includes: opening void, aluminum frame, glazing
  - Ready to open in Revit, Archicad, or other IFC viewers!
"""
    )


if __name__ == "__main__":
    main()
