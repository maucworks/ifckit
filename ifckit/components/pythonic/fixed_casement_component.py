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
from ifckit.components import EvaluatedComponent, FillComponent
from ifckit.components.materials import ALUMINUM, GLASS, VOID
from ifckit.geometry import Path, Plane, Vec


class FixedCasementComponent(FillComponent):
    """Generative window: sectioned-spine frame with fixed glazing."""

    ifc_class = "IfcWindow"

    def build(self, ifc_file, plane, w, h, params):
        lt = float(params.get("lining_thickness", 55))
        ld = float(params.get("lining_depth", 70))
        gd = float(params.get("panel_depth", 6))
        wt = float(params.get("wall_thickness", 200))
        wx = float(w)
        wy = float(h)

        comps = []
        spine = Path.from_pts(
            [
                Vec(0, 0, 0),
                Vec(wx, 0, 0),
                Vec(wx, wy, 0),
                Vec(0, wy, 0),
            ],
            Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
            closed=True,
        )
        dist = min([wx / 2.01, wy / 2.01])
        spine.fillet([0, 1, 2, 3], dist)

        # ── Opening void ──────────────────────────────────────────────
        opening_profile = profile_from_points(ifc_file, spine)

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
                material=VOID,
            )
        )

        # ── Lining: closed sectioned-spine with rectangular profile ───
        if lt > 0 and ld > 0:
            a_step = float(params.get("angle_step_deg", 5.0))
            p_segs = int(params.get("profile_segments", 16))
            lining_solid = self._build_lining(
                ifc_file,
                spine,
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
                    material=ALUMINUM,
                )
            )

        # ── Glazing ───────────────────────────────────────────────────
        glass_x0 = lt
        glass_y0 = lt
        glass_x1 = wx - lt
        glass_y1 = wy - lt

        if glass_x1 > glass_x0 and glass_y1 > glass_y0:
            glass_spine = spine.offset(lt)
            glass_profile = profile_from_points(ifc_file, glass_spine)

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
                    material=GLASS,
                )
            )

        return comps

    # ── Lining via closed sectioned-spine ─────────────────────────

    @staticmethod
    def _build_lining(
        ifc_file,
        spine,
        lt,
        ld,
        angle_step_deg: float = 3.0,
        profile_segments: int = 16,
    ):
        """Build lining as a closed sectioned-spine sweep.

        Spine = closed rectangle at the centerline of the frame
        (offset *lt/2* inward from the outer boundary).
        Profile = Rectangle(lt × ld): frame cross-section.
        """
        starter = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        # profile = RectangleProfile(ld, lt)
        # profile.anchor = "w"
        section = Path.from_pts(
            [
                Vec(-lt, 0, 0),
                Vec(ld, 0, 0),
                Vec(ld, lt / 5, 0),
                Vec(2 * ld / 3, lt / 5, 0),
                Vec(2 * ld / 3, lt, 0),
                Vec(ld / 3, lt, 0),
                Vec(-lt, lt / 5, 0),
            ],
            Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
            closed=True,
        )
        section.fillet(3, 3 * lt / 5)
        profile = section.to_profile(name="section")
        # profile.anchor = "sw"
        # profile.anchor = None

        # section_override = Path.from_pts(
        #     [
        #         Vec(-ld, 0, 0),
        #         Vec(ld, 0, 0),
        #         Vec(ld, lt / 5, 0),
        #         Vec(2 * ld / 3, lt, 0),
        #         Vec(ld / 3, lt, 0),
        #         Vec(-ld, lt / 5, 0),
        #     ],
        #     Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
        #     closed=True,
        # )
        # # section.fillet(1, 5 * lt)
        # profile_override = section_override.to_profile(name="section")
        # profile_override.anchor = "s"

        return SectionedSpineBuilder().tessellate_spine(
            ifc_file,
            spine=spine,
            profile=profile,
            # profile_overrides={6: profile_override},
            starter_plane=starter,
            angle_step_deg=angle_step_deg,
            profile_segments=profile_segments,
        )
