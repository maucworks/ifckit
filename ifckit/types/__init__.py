"""
ifckit.types
============

Type factory modules and 2D footprint/symbol primitives.
"""

from ifckit.types.footprint import Footprint
from ifckit.types.ifc_curves import curves_to_ifc

__all__ = ["Footprint", "curves_to_ifc"]
