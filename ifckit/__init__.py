"""
ifckit
======

Framework-agnostic IFC builder library.

Quick start::

    from ifckit import IfcModel, IfcSchema, PendingWall
    from ifckit.geometry import Vec3, Plane

    model = IfcModel(name="My Project", schema=IfcSchema.IFC4)
    site  = model.add_site("Site A")
    bldg  = model.add_building(site, "Building 1")
    floor = model.add_storey(bldg, "Ground Floor", elevation=0.0)

    wall = PendingWall(
        footprint=[Vec3(0,0,0), Vec3(10,0,0), Vec3(10,0.3,0), Vec3(0,0.3,0)],
        plane=Plane.world_xy(),
        height=3.0,
        name="North Facade",
    )
    model.add_element(floor, wall)
    model.save("/output/project.ifc")
"""

# Geometry primitives
from ifckit.geometry import (  # noqa: F401
    Arc,
    Line,
    Path,
    Plane,
    Polyline,
    Vec,
    parallel_transport_frames,
)

__version__ = "0.1.0"
__all__ = [
    # geometry
    "Vec",
    "Plane",
    "Line",
    "Arc",
    "Polyline",
    "Path",
    "parallel_transport_frames",
    # schema (added in M3)
    "IfcSchema",
    # model (added in M3)
    "IfcModel",
    # elements (added in M2)
    "PendingWall",
    "PendingSlab",
    "PendingBeam",
    "PendingColumn",
    "PendingRevolvedBeam",
    "PendingBridge",
    "PendingBridgePart",
    "PendingAlignment",
]
