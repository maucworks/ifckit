# This file was generated with the assistance of an AI coding tool.

"""
FillBuilder — Build standalone IFC products from FillComponent presets.

Registered for ``element_type = "fill"`` in the default builder registry.
Each ``PendingFill`` carries a ``component_graph`` key that selects a
registered ``FillComponent``; the builder instantiates the component,
collects its ``EvaluatedComponent`` solids, and wraps them in a standalone
product entity (``IfcCurtainWall``, ``IfcPlate``, etc.) via
:func:`~ifckit.builders.door_window.build_standalone_fill`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import ifcopenshell

from ifckit.builders._geom import axis2placement3d
from ifckit.builders.base import BaseBuilder
from ifckit.builders.door_window import build_standalone_fill
from ifckit.components import get_component as _get_component

if TYPE_CHECKING:
    from ifckit.elements.base import PendingElement


class FillBuilder(BaseBuilder):
    """Build a standalone IFC product from a FillComponent."""

    element_type = "fill"
    entity_type = "fill"
    ifc_class = "IfcBuildingElementProxy"

    def _create_geometry(
        self,
        ifc_file: ifcopenshell.file,
        pending: PendingElement,
        container: ifcopenshell.entity_instance,
        context: ifcopenshell.entity_instance,
    ) -> ifcopenshell.entity_instance:
        comp_cls = _get_component(pending.component_graph)
        if comp_cls is None:
            raise ValueError(f"FillBuilder: unknown component_graph {pending.component_graph!r}")

        component = comp_cls()

        w = float(pending.parameters.get("width", 1000))
        h = float(pending.parameters.get("height", 1000))

        results = component.build(
            ifc_file,
            pending.plane,
            w,
            h,
            params=pending.parameters,
            path=getattr(pending, "path", None),
        )

        if pending.plane is not None:
            pl = pending.plane
            ax = axis2placement3d(ifc_file, pl.origin, pl.z_axis, pl.x_axis)
            placement = ifc_file.create_entity("IfcLocalPlacement", RelativePlacement=ax)
        else:
            placement = None

        return build_standalone_fill(
            ifc_file=ifc_file,
            ifc_class=comp_cls.ifc_class,
            name=pending.name,
            components=results,
            context=context,
            container=container,
            placement=placement,
        )
