"""
Simple Door Component — Python Generative Door

A single-swing door with 3-sided lining (left, right, top) and
a flush panel.  Supports ``SINGLE_SWING_LEFT`` and
``SINGLE_SWING_RIGHT`` operation types.

The component also provides a ``footprint()`` method returning
2D plan-view symbol curves (swing arc + leaf rectangle) via
``Footprint.door_swing()``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from ifckit.components import EvaluatedComponent, FillComponent
from ifckit.components.materials import ALUMINUM, DOOR_PANEL, VOID
from ifckit.geometry import Arc, Line, Path, Plane, Vec
from ifckit.types.footprint import Footprint

from .utils import _build_profiled_spine, _path_to_opening_solid, _path_to_solid

_CURVE = Union[Line, Arc]


class SimpleDoorComponent(FillComponent):
    """Single-swing flush door with 3-sided frame and optional top glazing.
    w and h are actual free opening. Wall opening is w+2*lining thickness
    """

    ifc_class = "IfcDoor"

    def build(
        self,
        ifc_file,
        plane: Plane,
        w: float,
        h: float,
        params: Dict[str, Any],
    ) -> List[EvaluatedComponent]:
        lt = float(params.get("lining_thickness", 50))
        ld = float(params.get("lining_depth", 100))
        dt = float(params.get("door_thickness", 50))
        do = float(params.get("door_overlap", 20))
        di = float(params.get("door_inset", 10))
        wt = float(params.get("wall_thickness", 300))

        wx = float(w) + 2 * lt
        wy = float(h) + lt
        leaf_w = w + 2 * do
        leaf_h = h + do

        comps: List[EvaluatedComponent] = []
        opening_path = Path.from_pts(
            [
                Vec(0, 0, 0),
                Vec(wx, 0, 0),
                Vec(wx, wy, 0),
                Vec(0, wy, 0),
            ],
            Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
            closed=True,
        )
        opening_solid = _path_to_opening_solid(ifc_file, opening_path, wt)
        comps.append(EvaluatedComponent(solid=opening_solid, role="Opening", material=VOID))

        if lt > 0:
            spine = Path.from_pts(
                [
                    Vec(0, 0, 0),
                    Vec(0, wy, 0),
                    Vec(wx, wy, 0),
                    Vec(wx, 0, 0),
                ],
                Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
                closed=False,
            )

            section = Path.from_pts(
                [
                    Vec(0, 0, 0),
                    Vec(ld, 0, 0),
                    Vec(ld, lt, 0),
                    Vec(dt + di, lt, 0),
                    Vec(dt + di, lt - do, 0),
                    Vec(0, lt - do, 0),
                ],
                Plane(Vec(0, 0, 0), Vec(0, -1, 0), Vec(-1, 0, 0)),
                closed=True,
            )
            a_step = 45
            p_segs = 12
            lining_solid = _build_profiled_spine(ifc_file, spine, section, a_step, p_segs)
            comps.append(
                EvaluatedComponent(
                    solid=lining_solid,
                    role="Lining",
                    node_id="lining",
                    material=ALUMINUM,
                )
            )

        if leaf_w > 0 and leaf_h > 0:
            door_outline = Path.from_pts(
                [
                    Vec(lt - do, 0.0, 0),
                    Vec(lt - do + leaf_w, 0.0, 0),
                    Vec(lt - do + leaf_w, leaf_h, 0),
                    Vec(lt - do, leaf_h, 0),
                ],
                Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
                closed=True,
            )
            door_solid = _path_to_solid(ifc_file, door_outline, dt, di)
            comps.append(EvaluatedComponent(solid=door_solid, role="Panel", material=DOOR_PANEL))

        return comps

    @staticmethod
    def footprint(
        plane: Plane, w: float, h: float, params: Dict[str, Any]
    ) -> Optional[List[_CURVE]]:
        """Return door swing arc + leaf rectangle, or ``None``.

        *plane* origin is the insertion point (bottom-left of the opening).
        The returned curves are in the component's local frame — no additional
        transforms needed.
        """
        if not params.get("lining_thickness", 50):
            return None
        lt = float(params["lining_thickness"])
        leaf_w = w + 2 * lt
        door_thickness = float(params.get("door_thickness", 50))
        if leaf_w <= 0 or door_thickness <= 0:
            return None
        op = params.get("operation_type", "SINGLE_SWING_LEFT")

        if "LEFT" in op:
            hinge_plane = Plane(plane.origin, plane.x_axis, plane.z_axis)
        elif "RIGHT" in op:
            hinge_plane = Plane(
                plane.origin + plane.x_axis * leaf_w,
                -plane.x_axis,
                plane.z_axis,
            )
        else:
            return list(
                Footprint.leaf_rect(
                    Plane(plane.origin, plane.x_axis, plane.z_axis),
                    leaf_w,
                    door_thickness,
                )
            )

        leaf_plane = Plane(plane.origin, plane.x_axis, plane.z_axis)
        curves = Footprint.door_swing(hinge_plane, leaf_w)
        curves.extend(Footprint.leaf_rect(leaf_plane, leaf_w, door_thickness))
        return curves
