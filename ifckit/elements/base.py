"""
ifckit.elements.base
====================

Abstract base class for all pending IFC elements.
A pending element is a plain Python data container — no ifcopenshell
dependency. It is converted to a real IFC entity by a Builder.
"""

from __future__ import annotations

import json as _json
import warnings as _warnings
from typing import Any, Dict, List, Optional

from ifckit.elements.registry import ElementRegistry, RegisterElementType
from ifckit.elements.style import RenderStyle

ClipData = Dict[str, Any]
UserProperties = Dict[str, Any]


class PendingElement(metaclass=RegisterElementType):
    """
    Base class for all pending IFC element data.

    Subclasses carry geometry and metadata as plain Python types
    (Vec, Plane, Line, Arc, float, str) — no Rhino, no ifcopenshell.

    Each subclass must define ``element_type`` as a class variable (str).
    When the class is defined, it's automatically registered in ElementRegistry.

    ``clips`` is an optional list of ``ifckit.geometry.Plane`` objects used
    for boolean clipping (``IfcBooleanClippingResult``).  Each plane's
    z_axis points toward the material to keep.

    ``properties`` is an optional free-form dict of user-supplied key/value
    pairs written to ``EPset_IfcKit`` in the IFC output.  Values may be
    str, float, int or bool; other types are coerced to str.
    """

    element_type: str  # must be set by each subclass

    def __init__(
        self,
        name: str = "",
        clips: Optional[List[Any]] = None,
        clip_data: Optional[ClipData] = None,  # legacy — ignored
        style: Optional[RenderStyle] = None,
        hatch_pattern: str = "",
        properties: Optional[UserProperties] = None,
    ) -> None:
        if clip_data is not None:
            _warnings.warn(
                "clip_data is deprecated and ignored; use clips instead.",
                DeprecationWarning,
                stacklevel=2,
            )
        self.name = name
        self.clips: List[Any] = list(clips) if clips else []
        self.style = style
        self.hatch_pattern = hatch_pattern
        self.properties: UserProperties = properties or {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (useful for JSON transport / debugging)."""

        d: Dict[str, Any] = {"type": self.element_type, "name": self.name}
        if self.clips:
            d["clips"] = [
                {
                    "origin": c.origin.to_tuple(),
                    "x_axis": c.x_axis.to_tuple(),
                    "y_axis": c.y_axis.to_tuple(),
                }
                for c in self.clips
            ]
        if self.style is not None:
            d["style"] = self.style.to_dict()
        if self.hatch_pattern:
            d["hatch_pattern"] = self.hatch_pattern
        if self.properties:
            d["properties"] = self.properties
        return d

    def to_json(self, **kwargs) -> str:
        """Serialise to a JSON string."""
        return _json.dumps(self.to_dict(), **kwargs)

    @classmethod
    def _clips_from_dict(cls, d: Dict[str, Any]) -> List[Any]:
        """Deserialise clips list from dict."""
        from ifckit.geometry import Plane, Vec

        raw = d.get("clips") or []
        return [Plane(Vec(*c["origin"]), Vec(*c["x_axis"]), Vec(*c["y_axis"])) for c in raw]

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingElement":
        """
        Deserialize from a dict.

        Subclasses must override this method to properly reconstruct
        their specific fields.
        """
        raise NotImplementedError(f"{cls.__name__}.from_dict() not implemented")

    @classmethod
    def from_json(cls, json_str: str) -> "PendingElement":
        """
        Deserialize from a JSON string.

        Uses ElementRegistry to find the correct class based on the 'type' field.
        This means new element types are automatically supported without updating
        this method.

        Args:
            json_str: JSON string containing element data.

        Returns:
            A PendingElement subclass instance.

        Raises:
            ValueError: If JSON is invalid or element type is unknown.
        """
        d = _json.loads(json_str)
        elem_type = d.get("type")
        if not elem_type:
            raise ValueError("JSON missing 'type' field")

        element_cls = ElementRegistry.get(elem_type)
        return element_cls.from_dict(d)

    @classmethod
    def _require(cls, d: Dict[str, Any], key: str) -> Any:
        """Helper: extract required key or raise ValueError."""
        if key not in d:
            raise ValueError(f"{cls.__name__}: missing required field '{key}'")
        return d[key]

    @classmethod
    def _style_from_dict(cls, d: Dict[str, Any]) -> Optional[RenderStyle]:
        """Helper: deserialise optional style from dict."""
        raw = d.get("style")
        return RenderStyle.from_dict(raw) if raw is not None else None

    @classmethod
    def _hatch_pattern_from_dict(cls, d: Dict[str, Any]) -> str:
        """Helper: deserialise optional hatch_pattern from dict."""
        return d.get("hatch_pattern", "")

    @classmethod
    def _properties_from_dict(cls, d: Dict[str, Any]) -> UserProperties:
        """Helper: deserialise optional user properties from dict."""
        return d.get("properties") or {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
