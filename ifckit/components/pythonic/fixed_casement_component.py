"""
Fixed Casement Component — Python Generative Window

Alternative to fixed_casement.json. Creates a simple
window with aluminum frame (with hole) and glazing panel.
"""

from ifckit.builders._geom import extrude_profile, profile_from_points
from ifckit.components import EvaluatedComponent, WindowComponent, component
from ifckit.geometry import Path, Vec

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

        # Opening void (for IfcOpeningElement - creates hole in wall)
        # Depth is 2x wall_thickness to go through the wall
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

        # Lining with hole: outer rect minus inner rect (glazing opening)
        # Using Path class like JSON evaluator does
        outer_pts = [Vec(x, y, 0) for x, y in [(0.0, 0.0), (wx, 0.0), (wx, wy), (0.0, wy)]]
        outer_path = Path.from_pts(outer_pts, closed=True)

        hole_x0 = ltx
        hole_y0 = ltx
        hole_x1 = wx - ltx
        hole_y1 = wy - ltx

        if hole_x1 > hole_x0 and hole_y1 > hole_y0:
            hole_pts = [
                Vec(x, y, 0)
                for x, y in [
                    (hole_x0, hole_y0),
                    (hole_x1, hole_y0),
                    (hole_x1, hole_y1),
                    (hole_x0, hole_y1),
                ]
            ]
            hole_path = Path.from_pts(hole_pts, closed=True)
            outer_path = outer_path.with_hole(hole_path)

        lining_profile = profile_from_points_from_path(ifc_file, outer_path)
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


def profile_from_points_from_path(ifc_file, path: Path):
    """Create IFC profile from Path (supports holes)."""
    curve = ifc_file.createIfcCompositeCurve(
        [
            ifc_file.createIfcPolyline(
                [
                    ifc_file.createIfcCartesianPoint((seg.start.x, seg.start.y, 0.0))
                    for seg in path.segments
                ]
                + [
                    ifc_file.createIfcCartesianPoint(
                        (path.segments[0].start.x, path.segments[0].start.y, 0.0)
                    )
                ]
            )
        ]
    )

    if path.holes:
        # Create IfcArbitraryProfileDefWithVoids
        inner_curves = []
        for hole_path in path.holes:
            hole_curve = ifc_file.createIfcCompositeCurve(
                [
                    ifc_file.createIfcPolyline(
                        [
                            ifc_file.createIfcCartesianPoint((seg.start.x, seg.start.y, 0.0))
                            for seg in hole_path.segments
                        ]
                        + [
                            ifc_file.createIfcCartesianPoint(
                                (hole_path.segments[0].start.x, hole_path.segments[0].start.y, 0.0)
                            )
                        ]
                    )
                ]
            )
            inner_curves.append(hole_curve)

        return ifc_file.createIfcArbitraryProfileDefWithVoids(
            ProfileType="AREA",
            OuterCurve=curve,
            InnerCurves=inner_curves,
        )
    else:
        return ifc_file.createIfcArbitraryClosedProfileDef(OuterCurve=curve)


FixedCasementComponent.register()
