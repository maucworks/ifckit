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

from ifckit.builders import BuilderRegistry, default_registry
from ifckit.elements import (
    AlignmentSegment,
    BridgePartType,
    PendingAlignment,
    PendingBeam,
    PendingBridge,
    PendingBridgePart,
    PendingColumn,
    PendingExtrudedElement,
    PendingRevolvedBeam,
    PendingSlab,
    PendingWall,
)
from ifckit.elements.registry import ElementRegistry
from ifckit.geometry import (
    Arc,
    Line,
    Path,
    Plane,
    Polyline,
    Vec,
    parallel_transport_frames,
)
from ifckit.json_build import build, build_from_json, validate_json
from ifckit.model import IfcModel
import ifckit.rhinokit as rk
from ifckit.handles import (
    SiteHandle,
    BuildingHandle,
    StoreyHandle,
    BridgeHandle,
    BridgePartHandle,
    AlignmentHandle,
    EntityHandle,
)
from ifckit.profiles import IBeamProfile, LBeamProfile
from ifckit.schema import IfcSchema, LengthUnit
from ifckit.validator import ValidationResult, validate

try:
    from ifckit.rhino_import import IfcMeshImporter
    _RHINO_IMPORT_AVAILABLE = True
except ImportError:
    _RHINO_IMPORT_AVAILABLE = False

    class IfcMeshImporter:  # type: ignore[no-redef]
        """Stub raised when Rhino is not available."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "IfcMeshImporter requires Rhino 8+ with ifcopenshell. "
                "Run this code inside Rhino / Grasshopper."
            )

__version__ = "0.1.0"

__all__ = [
    "Vec",
    "Plane",
    "Line",
    "Arc",
    "Polyline",
    "Path",
    "parallel_transport_frames",
    "IfcSchema",
    "LengthUnit",
    "IfcModel",
    "PendingWall",
    "PendingSlab",
    "PendingBeam",
    "PendingColumn",
    "PendingExtrudedElement",
    "PendingRevolvedBeam",
    "PendingBridge",
    "PendingBridgePart",
    "PendingAlignment",
    "AlignmentSegment",
    "BridgePartType",
    "ElementRegistry",
    "validate",
    "ValidationResult",
    "BuilderRegistry",
    "default_registry",
    "IBeamProfile",
    "LBeamProfile",
    "build",
    "build_from_json",
    "validate_json",
    "SiteHandle",
    "BuildingHandle",
    "StoreyHandle",
    "BridgeHandle",
    "BridgePartHandle",
    "AlignmentHandle",
    "EntityHandle",
    "IfcMeshImporter",
    "rk",
]