"""
Fixed Casement Component — Python Generative Window

Alternative to fixed_casement.json. Creates a simple
window with aluminum frame and glazing panel.
"""

from ifckit.builders._geom import extrude_profile, profile_from_points
from ifckit.components import EvaluatedComponent, WindowComponent, component

ALUMINUM_FRAME = {
    "color": {"r": 0.8, "g": 0.8, "b": 0.8},
    "transparency": 0.0,
    "name": "Aluminum frame",
}

CLEAR_GLASS = {
    "color": {"r": 0.9, "g": 0.95, "b": 1.0},
    "transparency": 0.8,
    "name": "Clear glass",
}

OPENING_VOID = {
    "color": {"r": 0.5, "g": 0.5, "b": 0.5},
    "transparency": 1.0,
    "name": "Opening void",
}


@component("fixed_casement_component")
class FixedCasementComponent(WindowComponent):
    """Generative window: frame with fixed glazing."""

    name = "fixed_casement_component"

    def build(self, ifc_file, plane, w, h, params):
        lt = params.get("lining_thickness", 55)
        ld = params.get("lining_depth", 70)
        gd = params.get("panel_depth", 6)
        wt = params.get("wall_thickness", 200)

        comps = []

        wx = float(w)
        wy = float(h)
        ltx = float(lt)

        # Opening void (creates hole in wall)
        opening_profile = profile_from_points(
            ifc_file, [(0.0, 0.0), (wx, 0.0), (wx, wy), (0.0, wy)]
        )
        opening_solid = extrude_profile(
            ifc_file,
            opening_profile,
            depth=wt * 2,
            extrude_direction=(0, 0, -1),
        )
        comps.append(
            EvaluatedComponent(
                solid=opening_solid,
                role="Opening",
                node_id="opening_void",
                material=OPENING_VOID,
            )
        )

        # Lining (frame around opening) - simplified: just outer rect
        outer_pts = [(0.0, 0.0), (wx, 0.0), (wx, wy), (0.0, wy)]
        lining_profile = profile_from_points(ifc_file, outer_pts)
        lining_solid = extrude_profile(
            ifc_file, lining_profile, depth=ld, extrude_direction=(0, 0, -1)
        )
        comps.append(
            EvaluatedComponent(
                solid=lining_solid,
                role="Lining",
                node_id="lining",
                material=ALUMINUM_FRAME,
            )
        )

        # Glazing
        glass_x0 = ltx
        glass_y0 = ltx
        glass_x1 = wx - ltx
        glass_y1 = wy - ltx

        if glass_x1 > glass_x0 and glass_y1 > glass_y0:
            glass_profile = profile_from_points(
                ifc_file,
                [
                    (glass_x0, glass_y0),
                    (glass_x1, glass_y0),
                    (glass_x1, glass_y1),
                    (glass_x0, glass_y1),
                ],
            )
            glass_solid = extrude_profile(
                ifc_file, glass_profile, depth=gd, extrude_direction=(0, 0, -1)
            )
            comps.append(
                EvaluatedComponent(
                    solid=glass_solid,
                    role="Glazing",
                    node_id="glazing",
                    material=CLEAR_GLASS,
                )
            )

        return comps


FixedCasementComponent.register()
