"""
Fixed Casement Component — Python Generative Window

Alternative to fixed_casement.json. Creates a simple
window with sectioned-spine lining and glazing panel.
"""

from ifckit.builders._geom import (
    axis2placement3d,
    extrude_profile,
    profile_from_points,
)
from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.components import EvaluatedComponent, WindowComponent, component
from ifckit.geometry import Path, Plane, Vec
from ifckit.profiles import RectangleProfile

ALUMINUM_FRAME = {
    "color": {"r": 0.8, "g": 0.8, "b": 0.8},
    "transparency": 0.0,
    "name": "Aluminum frame",
}

CLEAR_GLASS = {
    "color": {"r": 0.9, "g": 0.95, "b": 1.0},
    "transparency": 0.5,
    "name": "Clear glass",
}

OPENING_VOID = {
    "color": {"r": 0.5, "g": 0.5, "b": 0.5},
    "transparency": 1.0,
    "name": "Opening void",
}


@component("fixed_casement_component")
class FixedCasementComponent(WindowComponent):
    """Generative window: sectioned-spine frame with fixed glazing."""

    name = "fixed_casement_component"

    def build(self, ifc_file, plane, w, h, params):
        lt = float(params.get("lining_thickness", 55))
        ld = float(params.get("lining_depth", 70))
        gd = float(params.get("panel_depth", 6))
        wt = float(params.get("wall_thickness", 200))
        wx = float(w)
        wy = float(h)

        comps = []

        # ── Opening void ──────────────────────────────────────────────
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

        # ── Lining: closed sectioned-spine with rectangular profile ───
        if lt > 0 and ld > 0:
            a_step = float(params.get("angle_step_deg", 5.0))
            p_segs = int(params.get("profile_segments", 16))
            lining_solid = self._build_lining(
                ifc_file,
                wx,
                wy,
                lt,
                ld,
                angle_step_deg=a_step,
                profile_segments=p_segs,
            )
            comps.append(
                EvaluatedComponent(
                    solid=lining_solid,
                    role="Lining",
                    node_id="lining",
                    material=ALUMINUM_FRAME,
                )
            )

        # ── Glazing ───────────────────────────────────────────────────
        glass_x0 = lt
        glass_y0 = lt
        glass_x1 = wx - lt
        glass_y1 = wy - lt

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
            z_offset = -(ld / 2 - gd / 2)
            glass_position = axis2placement3d(
                ifc_file,
                Vec(0, 0, z_offset),
                Vec(0, 0, 1),
                Vec(1, 0, 0),
            )
            glass_solid = extrude_profile(
                ifc_file,
                glass_profile,
                depth=gd,
                position=glass_position,
                extrude_direction=(0, 0, -1),
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

    # ── Lining via closed sectioned-spine ─────────────────────────

    @staticmethod
    def _build_lining(
        ifc_file, wx, wy, lt, ld, angle_step_deg: float = 3.0, profile_segments: int = 16
    ):
        """Build lining as a closed sectioned-spine sweep.

        Spine = closed rectangle at the centerline of the frame
        (offset *lt/2* inward from the outer boundary).
        Profile = Rectangle(lt × ld): frame cross-section.
        """
        off = lt / 2
        spine = Path.from_pts(
            [
                Vec(off, off, 0),
                Vec(wx - off, off, 0),
                Vec(wx - off, wy - off, 0),
                Vec(off, wy - off, 0),
            ],
            closed=True,
        )
        # spine.fillet(1, 5 * lt)  # uncomment to round corners
        starter = Plane(Vec(off, off, 0), Vec(1, 0, 0), Vec(0, 0, 1))
        profile = RectangleProfile(lt, ld)
        return SectionedSpineBuilder().tessellate_spine(
            ifc_file,
            spine=spine,
            profile=profile,
            starter_plane=starter,
            angle_step_deg=angle_step_deg,
            profile_segments=profile_segments,
        )


FixedCasementComponent.register()
