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

CLEAR_GLASS = {"color": {"r": 0.9, "g": 0.95, "b": 1.0}, "transparency": 0.8, "name": "Clear glass"}


@component("fixed_casement_component")
class FixedCasementComponent(WindowComponent):
    """Generative window: frame with fixed glazing."""

    name = "fixed_casement_component"

    def build(self, ifc_file, plane, w, h, params):
        lt = params.get("lining_thickness", 55)
        ld = params.get("lining_depth", 70)
        gd = params.get("panel_depth", 6)

        comps = []

        wx = float(w)
        wy = float(h)
        ltx = float(lt)

        lining_profile = profile_from_points(ifc_file, [(0.0, 0.0), (wx, 0.0), (wx, wy), (0.0, wy)])
        hole_x0 = ltx
        hole_y0 = ltx
        hole_x1 = wx - ltx
        hole_y1 = wy - ltx

        if hole_x1 > hole_x0 and hole_y1 > hole_y0:
            _ = profile_from_points(  # noqa: F841
                ifc_file,
                [
                    (hole_x0, hole_y0),
                    (hole_x1, hole_y0),
                    (hole_x1, hole_y1),
                    (hole_x0, hole_y1),
                ],
            )

        lining_solid = extrude_profile(
            ifc_file, lining_profile, depth=ld, extrude_direction=(0, 0, -1)
        )
        comps.append(EvaluatedComponent(solid=lining_solid, role="Lining", material=ALUMINUM_FRAME))

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
                EvaluatedComponent(solid=glass_solid, role="Glazing", material=CLEAR_GLASS)
            )

        return comps


FixedCasementComponent.register()
