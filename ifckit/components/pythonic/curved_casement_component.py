"""
Curved Casement Component — Windows met IfcSectionedSpine

Voorbeeld component dat IfcSectionedSpine gebruikt voor het maken
van complexe kozijnen langs een 3D curve (boog/hellend).

NB: Dit is een proof-of-concept. De Arc support in Path moet nog
worden uitgebreid voor echte gebogen kozijnen.
"""

from ifckit.builders._geom import (
    axis2placement3d,
    directrix_from_path,
    profile_from_points,
    sectioned_spine,
)
from ifckit.components import EvaluatedComponent, FillComponent
from ifckit.geometry import Vec

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


class CurvedCasementComponent(FillComponent):
    """Boogkozijn met IfcSectionedSpine.

    Dit is een proof-of-concept. Gebruikt een rechte lijn als spine.
    Kan worden uitgebreid met echte bogen via directrix_from_path().
    """

    ifc_class = "IfcWindow"

    def build(self, ifc_file, plane, w, h, params):
        lt = params.get("lining_thickness", 55)
        ld = params.get("lining_depth", 70)
        gd = params.get("panel_depth", 6)
        wt = params.get("wall_thickness", 200)

        comps = []

        wx = float(w)
        wy = float(h)
        ltx = float(lt)

        # Opening void - rechte extrusie (standaard)
        opening_profile = profile_from_points(
            ifc_file,
            [
                (0.0, 0.0),
                (wx, 0.0),
                (wx, wy),
                (0.0, wy),
            ],
        )
        opening_solid = ifc_file.create_entity(
            "IfcExtrudedAreaSolid",
            SweptArea=opening_profile,
            Position=axis2placement3d(ifc_file, Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0)),
            ExtrudedDirection=ifc_file.create_entity(
                "IfcDirection", DirectionRatios=[0.0, 0.0, -1.0]
            ),
            Depth=wt * 2,
        )
        comps.append(
            EvaluatedComponent(
                solid=opening_solid,
                role="Opening",
                node_id="opening_void",
                material=OPENING_VOID,
            )
        )

        # Lining met SectionedSpine
        # NB: Dit is een voorbeeld met rechte lijn.
        # Voor echte boog: gebruik directrix_from_path() met boog-segmenten.
        lining_solid = self._build_sectioned_spine(
            ifc_file,
            wx=wx,
            wy=wy,
            ltx=ltx,
            ld=ld,
        )
        comps.append(
            EvaluatedComponent(
                solid=lining_solid,
                role="Lining",
                node_id="lining",
                material=ALUMINUM_FRAME,
            )
        )

        # Glazing - standaard recht kozijn (rechthoekig glas)
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
            z_offset = -(ld / 2 - gd / 2)
            glass_solid = ifc_file.create_entity(
                "IfcExtrudedAreaSolid",
                SweptArea=glass_profile,
                Position=axis2placement3d(
                    ifc_file,
                    Vec(0, 0, z_offset),
                    Vec(0, 0, 1),
                    Vec(1, 0, 0),
                ),
                ExtrudedDirection=ifc_file.create_entity(
                    "IfcDirection", DirectionRatios=[0.0, 0.0, -1.0]
                ),
                Depth=gd,
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

    def _build_sectioned_spine(self, ifc_file, wx, wy, ltx, ld):
        """Build lining using IfcSectionedSpine.

        NB: Dit voorbeeld gebruikt een recht lijn-pad (geen boog).
        Voor een echte boog moet de geometry module Arc segments
        ondersteunen die naar directrix_from_path() kunnen.
        """

        # Spine curve - rechte lijn langs de breedte
        # Dit zou een boog worden via Path met Arc segments
        spine_pts = [
            Vec(0, 0, 0),
            Vec(wx, 0, 0),
        ]
        from ifckit.geometry import Path

        spine_path = Path.from_pts(spine_pts)
        spine_curve = directrix_from_path(ifc_file, spine_path)

        # Profiel - rechthoekig kozijnprofiel
        # Dit is hetzelfde profiel op elke positie langs de spine
        lining_w = ltx
        lining_h = ld
        profile = profile_from_points(
            ifc_file,
            [
                (0.0, 0.0),
                (lining_w, 0.0),
                (lining_w, lining_h),
                (0.0, lining_h),
            ],
        )

        # Posities langs de spine (begin en einde)
        # NB: Voor een echte boog moeten we tangenten berekenen
        pos_start = axis2placement3d(
            ifc_file,
            Vec(0, 0, 0),
            Vec(0, 0, -1),  # Z richting: naar binnen
            Vec(1, 0, 0),
        )
        pos_end = axis2placement3d(
            ifc_file,
            Vec(wx, 0, 0),
            Vec(0, 0, -1),  # Z richting: naar binnen
            Vec(1, 0, 0),
        )

        # Maak SectionedSpine met 2 identieke profielen
        # (Dit is de basis voor complexe vormen - profielen kunnen varieren langs de curve)
        spine = sectioned_spine(
            ifc_file,
            spine_curve,
            cross_sections=[profile, profile],
            positions=[pos_start, pos_end],
        )

        return spine
