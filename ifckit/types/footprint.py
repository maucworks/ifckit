"""
ifckit.types.footprint — 2D drawing symbol primitives.

Centralised library of plan-view drawing symbols for doors, windows,
and other building elements.  Each method is a pure-geometry function
that takes a ``Plane`` + dimensions and returns a list of ``Line`` and
``Arc`` curves.  No IFC, no ifcopenshell — just vectors.

Conventions for the plane frame used by each method are documented
in its docstring.  Components position and orient the plane; the
``Footprint`` class does the math.

Usage::

    from ifckit.types.footprint import Footprint
    from ifckit.geometry import Plane, Vec

    # Door swing: hinge at origin, leaf extends along +X,
    # swing arc sweeps into +Y half-plane.
    plane = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    curves = Footprint.door_swing(plane, leaf_width=900)
"""

from __future__ import annotations

import math
from typing import List, Union

from ifckit.geometry import Arc, Line, Plane


class Footprint:
    """Centralised library of 2D drawing symbols for plan views.

    Each static method returns ``list[Line | Arc]`` in the frame of
    the supplied ``Plane``.
    """

    @staticmethod
    def door_swing(plane: Plane, leaf_width: float) -> List[Union[Line, Arc]]:
        """Swing arc + closed leaf edge.

        Conventions:

            plane.origin  = hinge point
            plane.x_axis  = direction of the closed leaf (along wall)
            plane.y_axis  = swing direction (into room, perpendicular to leaf)
            plane.z_axis  = normal of the drawing plane (x ** y)

        Returns:
            Line:  from hinge to leaf tip (closed position).
            Arc:   quarter circle (CCW) from leaf tip curving toward
                   the swing direction — from ``(leaf_width, 0)`` in
                   local coordinates to ``(0, leaf_width)``.
        """
        hinge = plane.origin
        closed_tip = plane.origin + plane.x_axis * leaf_width
        return [
            Line(hinge, closed_tip),
            Arc(
                center=hinge,
                normal=plane.z_axis,
                start=closed_tip,
                angle=math.pi / 2,
            ),
        ]

    @staticmethod
    def leaf_rect(plane: Plane, width: float, height: float) -> List[Line]:
        """Rectangle outline of a door leaf, window sash, or panel.

        Conventions:

            plane.origin  = bottom-left corner
            plane.x_axis  = width direction
            plane.y_axis  = height direction

        Returns:
            Four ``Line`` segments forming the closed rectangle perimeter.
        """
        o = plane.origin
        x = plane.x_axis * width
        y = plane.y_axis * height
        return [
            Line(o, o + x),
            Line(o + x, o + x + y),
            Line(o + x + y, o + y),
            Line(o + y, o),
        ]

    @staticmethod
    def window_opening(plane: Plane, width: float, height: float) -> List[Line]:
        """Fixed-window opening symbol: perimeter + diagonal cross.

        Conventions:

            plane.origin  = bottom-left corner of the opening
            plane.x_axis  = width direction
            plane.y_axis  = height direction

        Returns:
            Four perimeter lines + two diagonal lines.
        """
        o = plane.origin
        x = plane.x_axis * width
        y = plane.y_axis * height
        tl = o + y
        tr = o + x + y
        br = o + x
        return [
            Line(o, br),
            Line(br, tr),
            Line(tr, tl),
            Line(tl, o),
            Line(o, tr),
            Line(br, tl),
        ]

    @staticmethod
    def sliding_arrow(plane: Plane, width: float) -> List[Line]:
        """Sliding door/window arrow pair.

        Conventions:

            plane.origin  = start of the sliding direction
            plane.x_axis  = sliding direction

        Returns:
            Two parallel lines with arrow heads pointing along ``+x``.
        """
        o = plane.origin
        x_hat = plane.x_axis
        half_width = width * 0.5

        y_off = (plane.x_axis**plane.z_axis).normalized() * (width * 0.15)
        p1 = o + y_off
        p2 = o + x_hat * width + y_off
        p3 = o - y_off
        p4 = o + x_hat * width - y_off

        shaft_len = max(half_width * 0.15, 50.0)
        arrow_rear = o + x_hat * (width - shaft_len)

        return [
            Line(p1, p2),
            Line(arrow_rear + y_off, p2),
            Line(p2, p2 - x_hat * shaft_len + y_off),
            Line(p3, p4),
            Line(arrow_rear - y_off, p4),
            Line(p4, p4 - x_hat * shaft_len - y_off),
        ]

    @staticmethod
    def diagonal(plane: Plane, width: float, height: float) -> List[Line]:
        """Simple diagonal cross within a rectangle.

        Conventions:

            plane.origin  = bottom-left corner
            plane.x_axis  = width direction
            plane.y_axis  = height direction

        Returns:
            Two diagonal lines from corner to corner.
        """
        o = plane.origin
        x = plane.x_axis * width
        y = plane.y_axis * height
        return [
            Line(o, o + x + y),
            Line(o + x, o + y),
        ]
