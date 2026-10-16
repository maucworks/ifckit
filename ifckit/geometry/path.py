# This file was generated with the assistance of an AI coding tool.
"""ifckit.geometry.path — re-export facade over geometrykit.

Paths live in geometrykit, whose implementation matches the code this
module carried except for one deliberate factoring: IFC serialisation
(``Path.directrix``) delegates to the installed IFC bridge instead of
calling ``ifckit.geometry.ifc_geom`` directly. ifckit installs its own
``ifc_geom`` module as that bridge on package import (see
``ifckit.geometry.__init__``), so behavior is unchanged. Import
through ``ifckit.geometry`` unchanged.
"""

from geometrykit.geometry.path import (
    Path,
    PathPoint,
    PathReport,
    _line_line_intersect_2d,  # noqa: F401  (re-exported for ifckit internals)
    assemble_path,
)

__all__ = [
    "Path",
    "PathPoint",
    "PathReport",
    "assemble_path",
]
