"""
ifckit.elements.base
====================

Abstract base class for all pending IFC elements.
A pending element is a plain Python data container — no ifcopenshell
dependency. It is converted to a real IFC entity by a Builder.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


ClipData = Dict[str, Any]


class PendingElement(ABC):
    """
    Base class for all pending IFC element data.

    Subclasses carry geometry and metadata as plain Python types
    (Vec, Plane, Line, Arc, float, str) — no Rhino, no ifcopenshell.
    """

    def __init__(
        self,
        name: str = "",
        clip_data: Optional[ClipData] = None,
    ) -> None:
        self.name = name
        self.clip_data = clip_data

    @property
    @abstractmethod
    def element_type(self) -> str:
        """
        Unique type key used by BuilderRegistry dispatch.
        Examples: "basic_wall", "basic_beam", "bridge", "alignment"
        """

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict (useful for JSON transport / debugging)."""
        d: Dict[str, Any] = {"type": self.element_type, "name": self.name}
        if self.clip_data:
            d["clip_data"] = self.clip_data
        return d

    @classmethod
    def _require(cls, d: Dict[str, Any], key: str) -> Any:
        """Helper: extract required key or raise ValueError."""
        if key not in d:
            raise ValueError(f"{cls.__name__}: missing required field '{key}'")
        return d[key]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
