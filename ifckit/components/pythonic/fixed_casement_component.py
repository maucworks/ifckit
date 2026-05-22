"""
Fixed Casement Component — Python Generative Window

Alternative to fixed_casement.json. Creates a simple
window with sectioned-spine lining and glazing panel.
"""

from ifckit.builders._geom import axis2placement3d, extrude_profile
from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.components import EvaluatedComponent, FillComponent
from ifckit.components.materials import ALUMINUM, GLASS
from ifckit.geometry import Path, Plane, Vec

from .utils import _path_to_opening_solid


class FixedCasementComponent(FillComponent):
    """Generative window: sectioned-spine frame with fixed glazing."""

    ifc_class = "IfcWindow"

    def build(self, ifc_file, plane, w, h, params):
        lt = float(params.get("lining_thickness", 55))
        ld = float(params.get("lining_depth", 70))
        gd = float(params.get("panel_depth", 24))
        gi = float(params.get("panel_inset", 50))
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

        # ── Opening void ──────────────────────────────────────────────

        opening_solid = _path_to_opening_solid(ifc_file, spine, wt)
        comps.append(EvaluatedComponent(solid=opening_solid, role="Opening", node_id="opening"))

        # ── Lining: closed sectioned-spine with rectangular profile ───
        if lt > 0 and ld > 0:
            lining_solid = self._build_lining(ifc_file, spine, lt, ld, gd, gi)
            comps.append(
                EvaluatedComponent(
                    solid=lining_solid,
                    role="Lining",
                    node_id="lining",
                    material=ALUMINUM,
                )
            )

        # ── Glazing ───────────────────────────────────────────────────
        glass_x0 = lt / 2
        glass_y0 = lt / 2
        glass_x1 = wx - lt / 2
        glass_y1 = wy - lt / 2

        if glass_x1 > glass_x0 and glass_y1 > glass_y0:
            glass_spine = spine.offset(lt / 2)
            glass_profile = glass_spine.to_ifc_profile(ifc_file)

            z_offset = -gi
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
    def _build_lining(ifc_file, spine, lt, ld, gd, gi):
        """Build lining as a closed sectioned-spine sweep.

        Spine = closed rectangle at the centerline of the frame
        (offset *lt/2* inward from the outer boundary).
        Profile = Rectangle(lt × ld): frame cross-section.
        """
        starter = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
        # profile = RectangleProfile(ld, lt)
        # profile.anchor = "w"
        min_lt = lt / 5
        padding = gd
        section = Path.from_pts(
            [
                Vec(-lt, 0, 0),
                Vec(ld, 0, 0),
                Vec(ld, min_lt, 0),
                Vec(gi + gd + padding, min_lt, 0),
                Vec(gi + gd + padding, lt, 0),
                Vec(gi + gd, lt, 0),
                Vec(gi + gd, lt - padding, 0),
                Vec(gi, lt - padding, 0),
                Vec(gi, lt, 0),
                Vec(-lt, min_lt, 0),
            ],
            Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
            closed=True,
        )
        # section.fillet(3, 3 * lt / 5)
        profile = section.to_profile(name="section")

        return SectionedSpineBuilder().tessellate_spine(
            ifc_file,
            spine=spine,
            profile=profile,
            # profile_overrides={6: profile_override},
            starter_plane=starter,
            angle_step_deg=5,
            profile_segments=16,
        )
