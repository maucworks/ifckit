"""
Fixed Casement Component — Python Generative Window

Alternative to fixed_casement.json. Creates a simple
window with sectioned-spine lining and glazing panel.
"""

from ifckit.builders._geom import (
    axis2placement3d,
    extrude_profile,
    profile_from_points,
    sectioned_spine,
)
from ifckit.components import EvaluatedComponent, WindowComponent, component
from ifckit.geometry import Path, Vec
from ifckit.geometry.frames import upvector_frames
from ifckit.profiles import RectangleProfile
from ifckit.profiles.derived import DerivedProfile

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
            lining_solid = self._build_lining(ifc_file, wx, wy, lt, ld)
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
    def _build_lining(ifc_file, wx, wy, lt, ld):
        """Build lining as a closed sectioned-spine sweep.

        Spine = closed rectangle at the centerline of the frame
        (offset *lt/2* inward from the outer boundary).

        Profile = Rectangle(lt × ld): width = frame thickness in the wall
        plane, height = frame depth along Z (world_up).
        """
        # Centerline vertices: offset = lt/2 inward from outer boundary
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

        base_profile = RectangleProfile(lt, ld)

        # Extract control points (strip trailing duplicate for closed paths)
        segs = spine._segments
        pts = [seg.start for seg in segs]
        last = segs[-1].end
        if not (pts and pts[0].equals(last)):
            pts.append(last)

        # Compute frames with miter detection
        world_up = Vec(0, 0, 1)
        field = upvector_frames(pts, world_up, closed=True)

        # Extract vertex-mitered frames only (midpoints are helpers)
        n_orig = len(pts)
        mit_indices = [4 * i + 2 for i in range(n_orig)]
        vtx_frames = [field.frames[i] for i in mit_indices]
        vtx_scales = [field.scales[i] for i in mit_indices]

        # Build miter-scaled profile copies
        profiles = []
        for scale, axis in vtx_scales:
            if scale == 1.0:
                profiles.append(base_profile)
            elif axis == "x":
                profiles.append(DerivedProfile(base_profile, scale_y=scale))
            else:
                profiles.append(DerivedProfile(base_profile, scale_x=scale))

        # Convert to IFC entities
        profile_defs = [p.to_ifc(ifc_file) for p in profiles]
        pos_entities = [
            axis2placement3d(ifc_file, f.origin, f.z_axis, f.x_axis) for f in vtx_frames
        ]
        spine_curve = spine.directrix(ifc_file)

        return sectioned_spine(
            ifc_file,
            spine_curve,
            profile_defs,
            pos_entities,
            profile_segments=32,
            closed=True,
        )


FixedCasementComponent.register()
