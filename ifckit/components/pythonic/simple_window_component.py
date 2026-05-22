"""
Simple Window Component — Python Generative Window

A side-hung or fixed window with 4-sided lining and a glazed sash.
Supports ``FIXED_CASEMENT``, ``SIDE_HUNG_LEFT_HAND``, and
``SIDE_HUNG_RIGHT_HAND`` window types.

The component also provides a ``footprint()`` method returning
2D plan-view symbol curves (swing arc for opening sashes, diagonal
cross for fixed).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from ifckit.builders._geom import axis2placement3d, extrude_profile, profile_from_points
from ifckit.components import EvaluatedComponent, FillComponent
from ifckit.components.materials import ALUMINUM, GLASS, VOID
from ifckit.geometry import Arc, Line, Plane, Vec
from ifckit.types.footprint import Footprint

_CURVE = Union[Line, Arc]


class SimpleWindowComponent(FillComponent):
    """Simple window with 4-sided lining and a single glazed sash."""

    ifc_class = "IfcWindow"

    def build(
        self,
        ifc_file,
        plane: Plane,
        w: float,
        h: float,
        params: Dict[str, Any],
    ) -> List[EvaluatedComponent]:
        lt = float(params.get("lining_thickness", 55))
        ld = float(params.get("lining_depth", 70))
        sd = float(params.get("sash_depth", 40))
        gd = float(params.get("glass_depth", 6))
        wt = float(params.get("wall_thickness", 200))

        wx = float(w)
        wy = float(h)
        ltx = float(lt)
        sash_w = wx - 2 * ltx
        sash_h = wy - 2 * ltx

        comps: List[EvaluatedComponent] = []

        opening_profile = profile_from_points(
            ifc_file, [(0.0, 0.0), (wx, 0.0), (wx, wy), (0.0, wy)]
        )
        opening_solid = extrude_profile(
            ifc_file,
            opening_profile,
            depth=wt * 2,
            extrude_direction=(0, 0, -1),
        )
        comps.append(EvaluatedComponent(solid=opening_solid, role="Opening", material=VOID))

        if lt > 0:
            left = profile_from_points(ifc_file, [(0.0, 0.0), (ltx, 0.0), (ltx, wy), (0.0, wy)])
            left_hollow = extrude_profile(ifc_file, left, depth=ld, extrude_direction=(0, 0, -1))
            comps.append(EvaluatedComponent(solid=left_hollow, role="Lining", material=ALUMINUM))

            right = profile_from_points(
                ifc_file, [(wx - ltx, 0.0), (wx, 0.0), (wx, wy), (wx - ltx, wy)]
            )
            right_hollow = extrude_profile(ifc_file, right, depth=ld, extrude_direction=(0, 0, -1))
            comps.append(EvaluatedComponent(solid=right_hollow, role="Lining", material=ALUMINUM))

            top = profile_from_points(
                ifc_file,
                [(ltx, wy - ltx), (wx - ltx, wy - ltx), (wx - ltx, wy), (ltx, wy)],
            )
            top_hollow = extrude_profile(ifc_file, top, depth=ld, extrude_direction=(0, 0, -1))
            comps.append(EvaluatedComponent(solid=top_hollow, role="Lining", material=ALUMINUM))

            bot = profile_from_points(
                ifc_file,
                [(ltx, 0.0), (wx - ltx, 0.0), (wx - ltx, ltx), (ltx, ltx)],
            )
            bot_hollow = extrude_profile(ifc_file, bot, depth=ld, extrude_direction=(0, 0, -1))
            comps.append(EvaluatedComponent(solid=bot_hollow, role="Lining", material=ALUMINUM))

        if sash_w > 0 and sash_h > 0:
            z_off = (ld - sd) * 0.5
            pos = axis2placement3d(ifc_file, Vec(0, 0, z_off), Vec(0, 0, 1), Vec(1, 0, 0))
            sash_profile = profile_from_points(
                ifc_file,
                [
                    (ltx, ltx),
                    (ltx + sash_w, ltx),
                    (ltx + sash_w, ltx + sash_h),
                    (ltx, ltx + sash_h),
                ],
            )
            sash_solid = extrude_profile(ifc_file, sash_profile, depth=sd, position=pos)
            comps.append(EvaluatedComponent(solid=sash_solid, role="Panel", material=ALUMINUM))

            if gd > 0:
                glass_profile = profile_from_points(
                    ifc_file,
                    [
                        (ltx + gd, ltx + gd),
                        (ltx + sash_w - gd, ltx + gd),
                        (ltx + sash_w - gd, ltx + sash_h - gd),
                        (ltx + gd, ltx + sash_h - gd),
                    ],
                )
                glass_solid = extrude_profile(
                    ifc_file,
                    glass_profile,
                    depth=gd,
                    extrude_direction=(0, 0, -1),
                )
                comps.append(EvaluatedComponent(solid=glass_solid, role="Glazing", material=GLASS))

        return comps

    @staticmethod
    def footprint(
        plane: Plane, w: float, h: float, params: Dict[str, Any]
    ) -> Optional[List[_CURVE]]:
        """Return window opening symbol or swing arc, or ``None``.

        *plane* is the component's build plane.  Swinging sash curves
        lie flat in the horizontal plane.
        """
        if not params.get("lining_thickness", 55):
            return None
        lt = float(params["lining_thickness"])
        pane_w = w - 2 * lt
        pane_h = h - 2 * lt
        if pane_w <= 0 or pane_h <= 0:
            return None
        wt_type = params.get("window_type", "FIXED_CASEMENT")

        pane_o = plane.origin + plane.x_axis * lt + plane.y_axis * lt
        pane_plane = Plane(pane_o, plane.x_axis, plane.z_axis)

        if "LEFT" in wt_type:
            hinge_o = plane.origin + plane.x_axis * lt + plane.y_axis * lt
            hinge_plane = Plane(hinge_o, plane.x_axis, plane.z_axis)
            curves: List[_CURVE] = Footprint.door_swing(hinge_plane, pane_w)
            curves.extend(Footprint.leaf_rect(pane_plane, pane_w, pane_h))
            return curves
        elif "RIGHT" in wt_type:
            hinge_o = plane.origin + plane.x_axis * (w - lt) + plane.y_axis * lt
            hinge_plane = Plane(hinge_o, -plane.x_axis, plane.z_axis)
            curves = Footprint.door_swing(hinge_plane, pane_w)
            curves.extend(Footprint.leaf_rect(pane_plane, pane_w, pane_h))
            return curves
        else:
            return list(Footprint.window_opening(pane_plane, pane_w, pane_h))
