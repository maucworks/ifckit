# This file was generated with the assistance of an AI coding tool.
"""
Path PUI Component — Path-based generative window for arbitrary outlines.

Takes a closed ``Path`` as input and produces an ``IfcWindow`` with:

- Opening void matching the path outline
- Perimeter frame (boolean difference of outer minus offset inner)
- Glazing panel inset from the frame

When no *path* is given, falls back to a rectangle from *width* × *height*.
"""

from ifckit.components import EvaluatedComponent, FillComponent
from ifckit.components.materials import ALUMINUM, GLASS, VOID
from ifckit.geometry import Path, Plane, Vec

from .utils import _path_to_solid


class PathPui(FillComponent):
    """Generative window from arbitrary closed path outline with opening void.

    Accepts an optional *path* argument (closed ``Path``).
    When *path* is given, *width* and *height* are ignored and
    the path outline is used as the outer perimeter.
    """

    ifc_class = "IfcWindow"

    def build(self, ifc_file, plane=None, w=None, h=None, params=None, path=None):
        params = params or {}
        lt = float(params.get("lining_thickness", 55))
        ld = float(params.get("lining_depth", 70))
        gd = float(params.get("glass_depth", 6))
        wt = float(params.get("wall_thickness", 200))

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

        # Opening void
        opening_solid = self._path_to_opening_solid(ifc_file, outer, wt)
        comps.append(EvaluatedComponent(solid=opening_solid, role="Opening", material=VOID))

        # Frame: boolean difference outer - inner
        if lt > 0 and ld > 0:
            inner = outer.offset(lt)
            outer_solid = _path_to_solid(ifc_file, outer, ld, 0)
            inner_solid = _path_to_solid(ifc_file, inner, ld, 0)
            frame_solid = ifc_file.create_entity(
                "IfcBooleanResult",
                Operator="DIFFERENCE",
                FirstOperand=outer_solid,
                SecondOperand=inner_solid,
            )
            comps.append(EvaluatedComponent(solid=frame_solid, role="Lining", material=ALUMINUM))

        # Glazing
        if gd > 0:
            glass_inset = (ld - gd) / 2
            glass_path = outer.offset(lt)
            glass_solid = _path_to_solid(ifc_file, glass_path, gd, glass_inset)
            comps.append(EvaluatedComponent(solid=glass_solid, role="Glazing", material=GLASS))

        return comps

    @staticmethod
    def _path_to_opening_solid(ifc_file, path, wt):
        """Create an oversized opening void solid."""
        return _path_to_solid(ifc_file, path, wt * 3, -wt)
