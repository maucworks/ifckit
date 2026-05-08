"""
ifckit.profiles.base
====================

Abstract base class for all profile types in ifckit.

``Profile`` inherits from ``Path`` — a Profile IS a planar, closed Path in
the XY plane (Z = 0).  This means every Profile can be used anywhere a Path
is expected (sweep directrix, hole curve, Rhino preview, etc.) without any
conversion step.

Every concrete profile must implement:
  - ``get_profile_points()``  → list of (x, y) tuples (open ring, no closing dup)
  - ``to_ifc(ifc_file)``      → an IfcProfileDef entity
  - ``to_dict()``             → JSON-serializable dict (must include ``"profile_type"``)
  - ``from_dict(d)``          → classmethod reconstructing from that dict

Path segments are built lazily from ``get_profile_points()`` the first time
any Path property (``segments``, ``is_closed``, ``length``, …) is accessed.
This keeps subclass ``__init__`` free of boilerplate while ensuring full
Path compatibility.

Profile transform
-----------------
All profiles support three optional transform parameters that are applied
**on top of** any internal anchor offset:

  rotation  (float, radians, default 0.0)
      CCW rotation of the cross-section around its local origin.

  offset_x  (float, metres, default 0.0)
      Additional translation along the local profile X-axis.

  offset_y  (float, metres, default 0.0)
      Additional translation along the local profile Y-axis.

These map to the two degrees of freedom in ``IfcAxis2Placement2D``:
  - ``Location``     ← anchor_offset + (offset_x, offset_y)
  - ``RefDirection`` ← (cos rotation, sin rotation)

For polyline-based profiles the transform is applied directly to the
(x, y) point coordinates via ``_apply_transform(points)``.

Registration
------------
Subclasses are auto-registered in ``ProfileRegistry`` via the
``RegisterProfileType`` metaclass, using the class-level ``profile_type``
string as the key.

Usage::

    from ifckit.profiles import PolygonProfile, RoundedPolygonProfile

    # Polymorphic round-trip:
    d = profile.to_dict()
    profile2 = Profile.from_dict(d)

    # IFC output:
    ifc_entity = profile.to_ifc(ifc_file)

    # Path usage — works directly, no conversion:
    path = RectangleProfile(100, 50)
    assert path.is_planar
    assert path.is_closed
    for seg in path.segments:
        print(seg)
"""

from __future__ import annotations

import math
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ifckit.geometry import Path, Plane, Vec

if TYPE_CHECKING:
    import ifcopenshell

# XY plane — the canonical plane for all 2D profiles
_XY_PLANE = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))


class RegisterProfileType(type(Path)):
    """Metaclass that auto-registers profile classes by their ``profile_type`` string.

    Inherits from ``type(Path)`` (which is plain ``type``) so it is compatible
    with ``Path`` as a base class without a metaclass conflict.
    """

    _registry: Dict[str, "RegisterProfileType"] = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        key = namespace.get("profile_type")
        if key is not None:
            mcs._registry[key] = cls
        return cls


class Profile(Path, metaclass=RegisterProfileType):
    """
    Abstract base class for all ifckit profile types.

    A Profile IS a Path — it is always planar (XY plane, Z = 0) and always
    closed.  All Path methods (``segments``, ``is_planar``, ``is_closed``,
    ``length``, ``sample()``, ``holes``, ``with_hole()``, …) work directly on
    any Profile instance without conversion.

    Subclasses must set a class-level ``profile_type`` string (used for
    serialization dispatch) and implement the abstract methods below.
    """

    profile_type: Optional[str] = None  # overridden in each concrete subclass

    # Transform defaults — subclasses set these via _init_transform()
    rotation: float = 0.0
    offset_x: float = 0.0
    offset_y: float = 0.0

    def __init__(self) -> None:
        # Initialise Path in the XY plane so is_planar is authoritatively True
        super().__init__(plane=_XY_PLANE)
        # Segment list is populated lazily on first access via _ensure_segments()
        self._segments_built: bool = False

    # ------------------------------------------------------------------
    # Lazy segment population
    # ------------------------------------------------------------------

    def _ensure_segments(self) -> None:
        """Populate Path segments from get_profile_points() if not done yet."""
        if self._segments_built:
            return
        self._segments_built = True
        pts = self.get_profile_points()
        if len(pts) < 2:
            return
        vecs = [Vec(x, y, 0.0) for x, y in pts]
        # Build closed ring of Line segments
        self._segments = []
        for i in range(len(vecs)):
            self._segments.append(
                __import__("ifckit.geometry", fromlist=["Line"]).Line(
                    vecs[i], vecs[(i + 1) % len(vecs)]
                )
            )

    @property
    def segments(self):
        self._ensure_segments()
        return list(self._segments)

    # ------------------------------------------------------------------
    # Path property overrides — enforce planar + closed invariants
    # ------------------------------------------------------------------

    @property
    def is_planar(self) -> bool:
        """Always True — profiles are by definition planar."""
        return True

    @property
    def is_closed(self) -> bool:
        """Always True — profiles are by definition closed."""
        return True

    # ------------------------------------------------------------------
    # to_path — identity (Profile IS a Path)
    # ------------------------------------------------------------------

    def to_path(self) -> "Profile":
        """Return self — Profile already IS a Path."""
        return self

    # ------------------------------------------------------------------
    # Transform helpers (called by subclass __init__ and builders)
    # ------------------------------------------------------------------

    def _init_transform(
        self,
        rotation: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        """Store the three transform parameters. Call from subclass __init__."""
        self.rotation = float(rotation)
        self.offset_x = float(offset_x)
        self.offset_y = float(offset_y)
        # Invalidate cached segments when transform changes
        self._segments_built = False
        self._segments = []

    def _apply_transform(self, points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """
        Apply (rotation, offset_x, offset_y) to a list of (x, y) tuples.

        Used by ``get_profile_points()`` implementations in polyline-based
        profiles so the transform is reflected in the raw point coordinates.

        The order is: rotate first (around origin), then translate.
        """
        if self.rotation == 0.0 and self.offset_x == 0.0 and self.offset_y == 0.0:
            return points
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)
        dx, dy = self.offset_x, self.offset_y
        return [(c * x - s * y + dx, s * x + c * y + dy) for x, y in points]

    def _ifc_placement_2d(
        self,
        ifc_file: "ifcopenshell.file",
        anchor_x: float = 0.0,
        anchor_y: float = 0.0,
    ) -> "ifcopenshell.entity_instance":
        """
        Build an ``IfcAxis2Placement2D`` that combines the subclass anchor
        offset with the user-supplied rotation and offset_x/offset_y.
        """
        loc_x = anchor_x + self.offset_x
        loc_y = anchor_y + self.offset_y

        location = ifc_file.create_entity("IfcCartesianPoint", Coordinates=[loc_x, loc_y])

        if self.rotation != 0.0:
            c = math.cos(self.rotation)
            s = math.sin(self.rotation)
            ref_dir = ifc_file.create_entity("IfcDirection", DirectionRatios=[c, s])
            return ifc_file.create_entity(
                "IfcAxis2Placement2D", Location=location, RefDirection=ref_dir
            )

        return ifc_file.create_entity("IfcAxis2Placement2D", Location=location)

    # ------------------------------------------------------------------
    # Transform serialization helpers
    # ------------------------------------------------------------------

    def _transform_dict(self) -> Dict[str, float]:
        """Return {rotation, offset_x, offset_y} — include in to_dict()."""
        return {
            "rotation": self.rotation,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
        }

    @staticmethod
    def _transform_from_dict(d: Dict[str, Any]) -> Tuple[float, float, float]:
        """Extract (rotation, offset_x, offset_y) from a dict, with defaults."""
        return (
            float(d.get("rotation", 0.0)),
            float(d.get("offset_x", 0.0)),
            float(d.get("offset_y", 0.0)),
        )

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def get_profile_points(self) -> List[Tuple[float, float]]:
        """Return profile outline as (x, y) tuples (open ring, no closing duplicate).

        This is the single source of truth for the 2D outline used by both
        the Path segment builder and the IFC tessellation pipeline.
        Subclasses must implement this.
        """
        raise NotImplementedError(f"{type(self).__name__} does not implement get_profile_points().")

    @abstractmethod
    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        """Return an IfcProfileDef entity for this profile."""
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict. Must include ``"profile_type"``."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Profile":
        """Reconstruct a profile from a dict produced by ``to_dict()``."""
        raise NotImplementedError

    @property
    def area(self) -> Optional[float]:
        """
        Return the cross-sectional area (same units as profile dimensions).
        Returns ``None`` if not overridden by the subclass.
        """
        return None

    # ------------------------------------------------------------------
    # Polymorphic entry-point
    # ------------------------------------------------------------------

    @classmethod
    def dispatch_from_dict(cls, d: Dict[str, Any]) -> "Profile":
        """
        Reconstruct any registered profile from a dict.

        Looks up ``d["profile_type"]`` in the profile registry and delegates
        to the matching subclass ``from_dict()``.
        """
        key = d["profile_type"]
        registry = RegisterProfileType._registry
        if key not in registry:
            raise ValueError(
                f"Unknown profile_type {key!r}. Registered types: {sorted(registry.keys())}"
            )
        return registry[key].from_dict(d)
