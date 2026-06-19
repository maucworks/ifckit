# This file was generated with the assistance of an AI coding tool.

"""
PendingFill — Generic standalone fill element.

A ``PendingFill`` carries a ``component_graph`` key that selects any
registered ``FillComponent`` and wraps its output in a standalone IFC
product (``IfcCurtainWall``, ``IfcPlate``, etc.) without requiring a
host wall or opening.

Usage in model.py::

    res.append(PendingFill(
        component_graph="facade_spine",
        path=my_closed_path,
        parameters={"profile_width": 0.5},
        name="Facade",
    ))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from ifckit.elements.base import PendingElement

if TYPE_CHECKING:
    from ifckit.geometry import Path, Plane


class PendingFill(PendingElement):
    """Generic standalone fill — any FillComponent without a host opening."""

    element_type = "fill"

    def __init__(
        self,
        *,
        component_graph: str,
        plane: Optional[Plane] = None,
        path: Optional[Path] = None,
        name: str = "",
        style: Any = None,
        properties: Any = None,
        parameters: Optional[Dict[str, float]] = None,
        material_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(name=name, style=style, properties=properties)
        self.component_graph = component_graph
        self.plane = plane
        self.path = path
        self.parameters = parameters or {}
        self.material_overrides = material_overrides or {}

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d["component_graph"] = self.component_graph
        if self.plane is not None:
            d["plane"] = self.plane.to_dict()
        if self.path is not None:
            d["path"] = self.path.to_dict()
        if self.parameters:
            d["parameters"] = self.parameters
        if self.material_overrides:
            d["material_overrides"] = self.material_overrides
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingFill":
        from ifckit.geometry import Path as IFCPath
        from ifckit.geometry import Plane

        path_data = d.get("path")
        path = IFCPath.from_dict(path_data) if path_data is not None else None

        return cls(
            component_graph=cls._require(d, "component_graph"),
            plane=Plane.from_dict(d["plane"]) if "plane" in d else None,
            path=path,
            name=d.get("name", ""),
            style=cls._style_from_dict(d),
            properties=cls._properties_from_dict(d),
            parameters=d.get("parameters"),
            material_overrides=d.get("material_overrides"),
        )
