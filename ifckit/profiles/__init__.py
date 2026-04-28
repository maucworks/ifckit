"""
ifckit.profiles
===============

Steel section profiles for use with PendingBeam and PendingColumn.

    from ifckit.profiles import IBeamProfile, LBeamProfile
"""

from ifckit.profiles.i_beam import IBeamProfile
from ifckit.profiles.l_beam import LBeamProfile

__all__ = ["IBeamProfile", "LBeamProfile"]
