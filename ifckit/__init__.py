"""
ifckit
======

Framework-agnostic IFC builder library.

Quick start::

    from ifckit import IfcModel, IfcSchema, PendingWall
    from ifckit.geometry import Vec, Plane

    model = IfcModel(name="My Project", schema=IfcSchema.IFC4)
    site  = model.add_site("Site A")
    bldg  = model.add_building(site, "Building 1")
    floor = model.add_storey(bldg, "Ground Floor", elevation=0.0)
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

# Schema
from ifckit.schema import IfcSchema, LengthUnit  # noqa: F401

# Model
from ifckit.model import IfcModel  # noqa: F401

# Elements
from ifckit.elements import (  # noqa: F401
    PendingWall,
    PendingSlab,
    PendingBeam,
    PendingColumn,
    PendingRevolvedBeam,
    PendingBridge,
    PendingBridgePart,
    PendingAlignment,
    AlignmentSegment,
    BridgePartType,
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
    # schema
    "IfcSchema",
    "LengthUnit",
    # model
    "IfcModel",
    # elements
    "PendingWall",
    "PendingSlab",
    "PendingBeam",
    "PendingColumn",
    "PendingRevolvedBeam",
    "PendingBridge",
    "PendingBridgePart",
    "PendingAlignment",
    "AlignmentSegment",
    "BridgePartType",
]

