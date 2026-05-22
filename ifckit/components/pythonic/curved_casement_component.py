"""
Fixed Casement Component — Python Generative Window

Alternative to fixed_casement.json. Creates a simple
window with sectioned-spine lining and glazing panel.
"""

from ifckit.components import EvaluatedComponent, FillComponent
from ifckit.components.materials import ALUMINUM, GLASS, VOID
from ifckit.geometry import Path, Plane, Vec

from .utils import _build_profiled_spine, _path_to_opening_solid, _path_to_solid


class FixedCasementComponent(FillComponent):
    """Generative window: sectioned-spine frame with fixed glazing."""

    ifc_class = "IfcWindow"

    def build(self, ifc_file, plane, w, h, params):
        lt = float(params.get("lining_thickness", 55))
        ld = float(params.get("lining_depth", 70))
        gd = float(params.get("panel_depth", 24))
        gi = float(params.get("panel_inset", 50))
        wt = float(params.get("wall_thickness", 200))
        a_step = float(params.get("angle_step_deg", 5.0))
        p_segs = int(params.get("profile_segments", 16))

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
        dist = min(wx / 2.1, wy / 2.1)
        spine.fillet([0, 1, 2, 3], dist)

        comps.append(
            EvaluatedComponent(
                solid=_path_to_opening_solid(ifc_file, spine.tessellate(a_step), wt),
                role="Opening",
                node_id="opening_void",
                material=VOID,
            )
        )
        # ── Lining: closed sectioned-spine with rectangular profile ───
        min_lt = lt / 5
        padding = 0
        if lt > 0 and ld > 0:
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
            section.fillet(3, gd)
            lining_solid = _build_profiled_spine(ifc_file, spine, section, a_step, p_segs)
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
            glass_spine = spine.offset(lt - padding).tessellate(a_step)
            comps.append(
                EvaluatedComponent(
                    solid=_path_to_solid(ifc_file, glass_spine, gd, gi),
                    role="Glazing",
                    node_id="glazing",
                    material=GLASS,
                )
            )

        return comps

    # ── Lining via closed sectioned-spine ─────────────────────────
