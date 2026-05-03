"""
ifckit.profiles.base
====================

Abstract base class for all profile types in ifckit.

Every concrete profile must implement:
  - ``to_ifc(ifc_file)``   → an IfcProfileDef entity
  - ``to_dict()``           → JSON-serializable dict (must include ``"profile_type"``)
  - ``from_dict(d)``        → classmethod reconstructing from that dict

Profile transform
-----------------
All profiles support three optional transform parameters that are applied
**on top of** any internal anchor offset:

  rotation  (float, radians, default 0.0)
      CCW rotation of the cross-section around its local origin.

  offset_x  (float, metres, default 0.0)
      Additional translation along the local profile X-axis (horizontal
      in the cross-section plane, i.e. perpendicular to the beam axis in
      the strong-axis direction).

  offset_y  (float, metres, default 0.0)
      Additional translation along the local profile Y-axis (vertical in
      the cross-section plane, i.e. the weak-axis direction).

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
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    import ifcopenshell


class RegisterProfileType(type(ABC)):
    """Metaclass that auto-registers profile classes by their ``profile_type`` string."""

    _registry: Dict[str, "RegisterProfileType"] = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        key = namespace.get("profile_type")
        if key is not None:
            mcs._registry[key] = cls
        return cls


class Profile(ABC, metaclass=RegisterProfileType):
    """
    Abstract base class for all ifckit profile types.

    Subclasses must set a class-level ``profile_type`` string (used for
    serialization dispatch) and implement the three abstract methods below.

    The optional *rotation*, *offset_x*, *offset_y* transform is applied
    centrally — subclasses do not need to handle it themselves.
    """

    profile_type: Optional[str] = None  # overridden in each concrete subclass

    # Transform defaults — subclasses may set these in __init__ by calling
    # _init_transform(rotation, offset_x, offset_y) or by setting the attrs.
    rotation: float = 0.0
    offset_x: float = 0.0
    offset_y: float = 0.0

    # ------------------------------------------------------------------
    # Transform helpers (called by subclass __init__ and builders)
    # ------------------------------------------------------------------

    def _init_transform(
        self,
        rotation: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        """Store the three transform parameters.  Call from subclass __init__."""
        self.rotation = float(rotation)
        self.offset_x = float(offset_x)
        self.offset_y = float(offset_y)

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

        Args:
            ifc_file:  The IFC file to create entities in.
            anchor_x:  X offset already required by the subclass anchor system
                       (e.g. ``IBeamProfile._origin_offset()``).
            anchor_y:  Y offset already required by the subclass anchor system.

        Returns:
            An ``IfcAxis2Placement2D`` entity.
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
    # Transform serialization helpers (use in to_dict / from_dict)
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
    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        """Return an IfcProfileDef entity for this profile."""
        raise NotImplementedError

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dict.  Must include ``"profile_type"``."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Profile":
        """Reconstruct a profile from a dict produced by ``to_dict()``."""
        raise NotImplementedError

    @property
    def area(self) -> Optional[float]:
        """
        Return the cross-sectional area in m² (or whatever unit the profile uses).

        Returns ``None`` if the profile type does not support area calculation
        (e.g. PolygonProfile without explicit geometry).  Concrete subclasses
        should override this.
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

        Raises:
            KeyError:   if ``"profile_type"`` is missing from ``d``.
            ValueError: if the profile_type is not registered.
        """
        key = d["profile_type"]
        registry = RegisterProfileType._registry
        if key not in registry:
            raise ValueError(
                f"Unknown profile_type {key!r}. Registered types: {sorted(registry.keys())}"
            )
        return registry[key].from_dict(d)

    # ------------------------------------------------------------------
    # Optional: backwards-compat point-list interface
    # ------------------------------------------------------------------

    def get_profile_points(self) -> List[Tuple[float, float]]:
        """
        Return the profile outline as a list of (x, y) tuples.

        Legacy interface consumed by ``_coerce_profile()`` in
        ``ifckit.elements.structural``.  Concrete shape profiles should
        override this so they remain compatible with the existing builder
        pipeline until full IFC-native output is wired through.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement get_profile_points(). Use to_ifc() directly."
        )

    def to_path(self) -> Any:
        """Return the profile outline as a closed ``ifckit.geometry.Path`` in the XY plane (Z=0).

        Converts ``get_profile_points()`` → a ``Path`` of ``Line`` segments,
        closed by connecting the last point back to the first.  The result can
        be passed directly to ``rhinokit.path_to_rhino_curve()``.
        """
        from ifckit.geometry import Path, Vec

        pts = self.get_profile_points()  # [(x, y), ...]
        if not pts:
            raise ValueError(f"{type(self).__name__}.get_profile_points() returned no points")

        vecs = [Vec(x, y, 0.0) for x, y in pts]
        path = Path()
        for i in range(len(vecs)):
            path.add_line(vecs[i], vecs[(i + 1) % len(vecs)])
        return path
