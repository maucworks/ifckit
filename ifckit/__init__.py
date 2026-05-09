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
    DOOR_OPERATION_TYPES,
    OPENING_HOST_IFC_CLASSES,
    WINDOW_TYPES,
    AlignmentSegment,
    BridgePartType,
    PendingAlignment,
    PendingBeam,
    PendingBridge,
    PendingBridgePart,
    PendingColumn,
    PendingDoor,
    PendingDoorType,
    PendingExtrudedElement,
    PendingOpening,
    PendingRevolvedBeam,
    PendingSlab,
    PendingTypeObject,
    PendingWall,
    PendingWindow,
    PendingWindowType,
)
from ifckit.elements.registry import ElementRegistry
from ifckit.geometry import (
    Arc,
    FrameField,
    Line,
    Path,
    Plane,
    Polyline,
    Vec,
    fixed_ref_frames,
    transport_frames,
    upvector_frames,
)
from ifckit.json_build import build, build_from_json, validate_json
from ifckit.model import IfcModel


def __getattr__(name):
    if name == "rk":
        import ifckit.rhinokit as rk

        return rk
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


from ifckit.handles import (  # noqa: E402
    AlignmentHandle,
    BridgeHandle,
    BridgePartHandle,
    BuildingHandle,
    EntityHandle,
    SiteHandle,
    StoreyHandle,
)
from ifckit.profiles import IBeamProfile, LBeamProfile  # noqa: E402
from ifckit.schema import IfcSchema, LengthUnit, TessellationDetail  # noqa: E402
from ifckit.validator import ValidationResult, validate  # noqa: E402

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
    "FrameField",
    "transport_frames",
    "fixed_ref_frames",
    "upvector_frames",
    "IfcSchema",
    "LengthUnit",
    "TessellationDetail",
    "IfcModel",
    "PendingWall",
    "PendingSlab",
    "PendingOpening",
    "PendingDoor",
    "PendingWindow",
    "DOOR_OPERATION_TYPES",
    "WINDOW_TYPES",
    "OPENING_HOST_IFC_CLASSES",
    "PendingTypeObject",
    "PendingDoorType",
    "PendingWindowType",
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
]
