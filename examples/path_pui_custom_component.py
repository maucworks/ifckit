"""
Example: Using Custom PathPui Component

Demonstrates how to load and use a custom PathPui component from
examples/components/pythonic/ instead of the built-in version.

This allows you to:
  - Customize component behavior
  - Extend the component for project-specific needs
  - Keep local copies of components for version control
"""

import sys
from pathlib import Path as PathlibPath

# Add examples/components to path so we can import custom components
project_root = PathlibPath(__file__).parent
sys.path.insert(0, str(project_root / "components"))

from ifckit import IfcModel, PendingWindow
from ifckit.geometry import Vec, Plane, Path
from ifckit.schema import IfcSchema

# Import custom PathPui component
from pythonic.path_pui import PathPui as CustomPathPui


def main():
    """Build a simple rectangular window using custom PathPui component."""

    # =========================================================================
    # Setup
    # =========================================================================

    model = IfcModel(
        name="Custom PathPui Component Example",
        schema=IfcSchema.IFC4,
        author="ifckit",
    )
    site = model.add_site("Site")
    bldg = site.add_building("Building")
    storey = bldg.add_storey("Ground", elevation=0.0)

    # Create a simple rectangular wall
    from ifckit import PendingWall

    wall = PendingWall(
        footprint=[
            Vec(0, 0, 0),
            Vec(5, 0, 0),
            Vec(5, 0.3, 0),
            Vec(0, 0.3, 0),
        ],
        plane=Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
        height=3.0,
        name="Simple Wall",
    )
    wall_handle = storey.add(wall)
    print(f"✓ Wall created")

    # =========================================================================
    # Create Custom Rectangular Path
    # =========================================================================

    # Create a simple rectangular path for the window
    window_path = Path.from_pts(
        [
            Vec(0, 0, 0),
            Vec(1.5, 0, 0),
            Vec(1.5, 1.2, 0),
            Vec(0, 1.2, 0),
        ],
        plane=Plane(Vec(1.5, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
        closed=True,
    )

    # =========================================================================
    # Create Window with Custom Component
    # =========================================================================

    window = PendingWindow(
        path=window_path,
        component_graph="path_pui",  # Registered component name
        plane=Plane(Vec(1.5, 0, -0.15), Vec(1, 0, 0), Vec(0, 0, 1)),
        parameters={
            "lining_thickness": 0.08,  # Thicker frame
            "lining_depth": 0.1,
            "glass_depth": 0.01,  # Thicker glass
            "wall_thickness": 0.3,
        },
        name="Custom Window",
    )

    win_handle = model.add(window, wall_handle)
    print(f"✓ Window created with custom PathPui component")

    # =========================================================================
    # Save
    # =========================================================================

    output_path = "examples/output/custom_path_pui.ifc"
    model.save(output_path)
    print(f"\n✓ Model saved: {output_path}")

    print(
        """
Custom Component Usage:
  1. Define your component in examples/components/pythonic/
  2. Import it: from pythonic.path_pui import PathPui
  3. Use it with component_graph="path_pui" in PendingWindow
  
This allows you to maintain project-specific components alongside ifckit.
"""
    )


if __name__ == "__main__":
    main()
