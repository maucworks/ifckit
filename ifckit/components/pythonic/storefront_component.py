# This file was generated with the assistance of an AI coding tool.
"""
Storefront Component — Path-based generative storefront/pui for IfcWindow.

Takes a closed Path as input (or falls back to rectangular w/h) and produces
a storefront frame with glazing panels.  No opening/host required — omit
``role="Opening"`` from the output.
"""

from ifckit.components import EvaluatedComponent, FillComponent
from ifckit.components.materials import ALUMINUM, GLASS
from ifckit.geometry import Path, Plane, Vec

from .utils import _path_to_solid


class StorefrontComponent(FillComponent):
    """Storefront (pui) — non-rectangular window with perimeter frame and glazing.

    Accepts an optional *path* argument (closed Path).  When *path* is given,
    *width* and *height* are ignored and the path outline is used as the
    outer perimeter of the storefront.
    """

    ifc_class = "IfcWindow"

    def build(self, ifc_file, plane=None, w=None, h=None, params=None, path=None):
        """Build and insert components into the IFC model."""
        params = params or {}
        lt = float(params.get("lining_thickness", 55))
        ld = float(params.get("lining_depth", 70))
        gd = float(params.get("glass_depth", 6))

        if path is not None:
            outer = path.duplicate().assert_ccw()
        else:
            wx = float(w or 1000)
            wy = float(h or 1000)
            pts = [Vec(0, 0, 0), Vec(wx, 0, 0), Vec(wx, wy, 0), Vec(0, wy, 0)]
            outer = Path.from_pts(
                pts,
                plane=Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)),
                closed=True,
            )

        comps = []

        if lt > 0 and ld > 0:
            inner = outer.offset(lt)
            outer_solid = _path_to_solid(ifc_file, outer, ld, 0)
            inner_solid = _path_to_solid(ifc_file, inner, ld, 0)
            lining_solid = ifc_file.create_entity(
                "IfcBooleanResult",
                Operator="DIFFERENCE",
                FirstOperand=outer_solid,
                SecondOperand=inner_solid,
            )
            comps.append(EvaluatedComponent(solid=lining_solid, role="Lining", material=ALUMINUM))

        if gd > 0:
            glass_inset = (ld - gd) / 2
            glass_path = outer.offset(lt)
            glass_solid = _path_to_solid(ifc_file, glass_path, gd, glass_inset)
            comps.append(EvaluatedComponent(solid=glass_solid, role="Glazing", material=GLASS))

        return comps
