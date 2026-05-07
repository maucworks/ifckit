"""
DoorFlush Component — Python Generative Door

Alternative to door_flush.json. Creates a 3-sided frame
with door panel and optional glazing.
"""

from ifckit.builders._geom import extrude_profile, profile_from_points
from ifckit.components import EvaluatedComponent, WindowComponent, component

ALUMINUM_FRAME = {
    "color": {"r": 0.8, "g": 0.8, "b": 0.8},
    "transparency": 0.0,
    "name": "Aluminum frame",
}

DOOR_PANEL = {"color": {"r": 0.9, "g": 0.0, "b": 0.0}, "transparency": 0.0, "name": "Door panel"}

CLEAR_GLASS = {"color": {"r": 0.9, "g": 0.95, "b": 1.0}, "transparency": 0.8, "name": "Clear glass"}


@component("door_flush_component")
class DoorFlushComponent(WindowComponent):
    """Generative door: 3-sided frame with panel and glazing."""

    name = "door_flush_component"

    def build(self, ifc_file, plane, w, h, params):
        lt = params.get("lining_thickness", 50)
        ld = params.get("lining_depth", 100)
        dw = params.get("door_width", w - 2 * lt)
        dh = params.get("door_height", h - lt)
        dd = params.get("door_depth", 50)
        pd = params.get("panel_depth", 10)

        comps = []

        # Dimensions in local coords
        wx = float(w)
        wy = float(h)
        ltx = float(lt)
        dwx = float(dw)
        dhy = float(dh)

        # Bottom sill
        sill = profile_from_points(ifc_file, [(0.0, 0.0), (wx, 0.0)])
        sill_solid = extrude_profile(ifc_file, sill, depth=ld, extrude_direction=(0, 0, -1))
        comps.append(EvaluatedComponent(solid=sill_solid, role="Lining", material=ALUMINUM_FRAME))

        # Left side
        left = profile_from_points(ifc_file, [(ltx, 0.0), (ltx, dhy)])
        left_solid = extrude_profile(ifc_file, left, depth=ld, extrude_direction=(0, 0, -1))
        comps.append(EvaluatedComponent(solid=left_solid, role="Lining", material=ALUMINUM_FRAME))

        # Right side
        right_x = ltx + dwx
        right = profile_from_points(ifc_file, [(right_x, 0.0), (right_x, dhy)])
        right_solid = extrude_profile(ifc_file, right, depth=ld, extrude_direction=(0, 0, -1))
        comps.append(EvaluatedComponent(solid=right_solid, role="Lining", material=ALUMINUM_FRAME))

        # Top (above door)
        if h > dh + lt:
            top_y = dhy + lt
            top = profile_from_points(ifc_file, [(0.0, top_y), (wx, top_y)])
            top_solid = extrude_profile(ifc_file, top, depth=ld, extrude_direction=(0, 0, -1))
            comps.append(
                EvaluatedComponent(solid=top_solid, role="Lining", material=ALUMINUM_FRAME)
            )

        # Door panel
        panel_x = ltx
        panel_z = ld - dd
        panel = profile_from_points(
            ifc_file,
            [
                (panel_x, panel_z),
                (panel_x + dwx, panel_z),
                (panel_x + dwx, panel_z + dhy),
                (panel_x, panel_z + dhy),
            ],
        )
        panel_solid = extrude_profile(ifc_file, panel, depth=dd, extrude_direction=(0, 0, 1))
        comps.append(EvaluatedComponent(solid=panel_solid, role="Panel", material=DOOR_PANEL))

        # Top glazing (above door)
        if h > dh + lt + lt:
            glass_bottom = dhy + lt
            glass_top = wy - lt
            glass = profile_from_points(
                ifc_file,
                [
                    (ltx, glass_bottom),
                    (ltx + dwx, glass_bottom),
                    (ltx + dwx, glass_top),
                    (ltx, glass_top),
                ],
            )
            glass_solid = extrude_profile(ifc_file, glass, depth=pd, extrude_direction=(0, 0, -1))
            comps.append(
                EvaluatedComponent(solid=glass_solid, role="Glazing", material=CLEAR_GLASS)
            )

        # Side glazing
        side_space = w - dwx - 2 * lt
        if side_space > lt:
            side_left = ltx + dwx + lt
            side_right = wx - lt
            side = profile_from_points(
                ifc_file,
                [(side_left, lt), (side_right, lt), (side_right, wy - lt), (side_left, wy - lt)],
            )
            side_solid = extrude_profile(ifc_file, side, depth=pd, extrude_direction=(0, 0, -1))
            comps.append(EvaluatedComponent(solid=side_solid, role="Glazing", material=CLEAR_GLASS))

        return comps


DoorFlushComponent.register()
