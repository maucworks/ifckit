"""
ifckit.components.pythonic.utils
=================================

Internal utility functions for pythonic component building.
"""

from ifckit.builders._geom import axis2placement3d
from ifckit.builders.sectioned_spine import SectionedSpineBuilder
from ifckit.geometry import Plane, Vec


def _path_to_solid(ifc_file, path, wt, inset):
    x_axis = path.plane.x_axis
    y_axis = path.plane.y_axis
    z_axis = (x_axis**y_axis).normalized()
    opening_solid = ifc_file.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=path.to_ifc_profile(ifc_file),
        Position=axis2placement3d(ifc_file, Vec(0, 0, -inset), z_axis, x_axis),
        ExtrudedDirection=ifc_file.create_entity("IfcDirection", DirectionRatios=[0.0, 0.0, -1.0]),
        Depth=wt,
    )
    return opening_solid


def _path_to_opening_solid(ifc_file, path, wt):
    return _path_to_solid(ifc_file, path, wt * 3, -wt)


def _build_profiled_spine(ifc_file, spine, section, a_step, p_segs):
    """Build lining as a closed sectioned-spine sweep.
    Spine = closed rectangle at the centerline of the frame
    """
    starter = Plane(Vec(0, 0, 0), Vec(0, 0, 1), Vec(0, 1, 0))
    profile = section.to_profile(name="section")

    solid = SectionedSpineBuilder().tessellate_spine(
        ifc_file,
        spine=spine,
        profile=profile,
        # profile_overrides={6: profile_override},
        starter_plane=starter,
        angle_step_deg=a_step,
        profile_segments=p_segs,
    )
    return solid
