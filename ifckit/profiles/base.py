"""
ifckit.profiles.base
====================

Abstract base class for all profile types in ifckit.

Every concrete profile must implement:
  - ``to_ifc(ifc_file)``   → an IfcProfileDef entity
  - ``to_dict()``           → JSON-serializable dict (must include ``"profile_type"``)
  - ``from_dict(d)``        → classmethod reconstructing from that dict

Registration
------------
Subclasses are auto-registered in ``ProfileRegistry`` via the ``RegisterProfileType``
metaclass, using the class-level ``profile_type`` string as the key.

Usage::

    from ifckit.profiles import PolygonProfile, RoundedPolygonProfile

    # Polymorphic round-trip:
    d = profile.to_dict()
    profile2 = Profile.from_dict(d)

    # IFC output:
    ifc_entity = profile.to_ifc(ifc_file)
"""

from __future__ import annotations

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
    """

    profile_type: Optional[str] = None  # overridden in each concrete subclass

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
