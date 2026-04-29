"""
ifckit.elements.style
=====================

RenderStyle: colour + transparency for IFC elements.

Normalises all input to RGB floats 0–1 internally, matching IFC's
``IfcColourRgb`` convention.

Supported input formats
-----------------------

Hex RGB::

    RenderStyle("#FF8000")         # opaque orange

Int RGB tuple::

    RenderStyle((255, 128, 0))     # opaque orange

Float RGB tuple (IFC native)::

    RenderStyle((1.0, 0.5, 0.0))   # opaque orange

Transparency (IFC ``IfcSurfaceStyleRendering.Transparency``)::

    RenderStyle("#FF8000", transparency=0.5)   # 50 % transparent

Note on transparency
--------------------
IFC supports ``Transparency`` as a scalar (0 = opaque, 1 = invisible) on
``IfcSurfaceStyleRendering``.  Support across authoring tools and viewers is
inconsistent — Revit rarely exports it correctly and many importers ignore it.
It is included here for completeness but should not be relied on for
interoperability.  Hex ``#RRGGBBAA`` is intentionally not supported to avoid
implying that alpha is reliable in IFC.
"""

from __future__ import annotations

import re
from typing import Dict, Any, Tuple, Union

_ColourInput = Union[str, Tuple]


class RenderStyle:
    """Colour and optional transparency for an IFC element.

    Args:
        colour:       Hex string ``"#RRGGBB"`` or RGB tuple of ints 0–255
                      or floats 0–1.
        transparency: 0.0 = fully opaque (default), 1.0 = fully invisible.

    Attributes:
        r, g, b:      Red/green/blue as floats 0–1.
        transparency: Float 0–1.
    """

    __slots__ = ("r", "g", "b", "transparency")

    def __init__(
        self,
        colour: _ColourInput,
        transparency: float = 0.0,
    ) -> None:
        r, g, b = _parse_colour(colour)
        self.r = r
        self.g = g
        self.b = b
        if not 0.0 <= transparency <= 1.0:
            raise ValueError(f"transparency must be 0–1, got {transparency}")
        self.transparency = transparency

    @property
    def rgb(self) -> Tuple[float, float, float]:
        """RGB as float tuple 0–1."""
        return (self.r, self.g, self.b)

    @property
    def rgba_255(self) -> Tuple[int, int, int, int]:
        """RGBA as int tuple 0–255 (alpha derived from transparency)."""
        a = int(round((1.0 - self.transparency) * 255))
        return (
            int(round(self.r * 255)),
            int(round(self.g * 255)),
            int(round(self.b * 255)),
            a,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "r": self.r,
            "g": self.g,
            "b": self.b,
            "transparency": self.transparency,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RenderStyle":
        obj = cls.__new__(cls)
        obj.r = float(d["r"])
        obj.g = float(d["g"])
        obj.b = float(d["b"])
        obj.transparency = float(d.get("transparency", 0.0))
        return obj

    def __repr__(self) -> str:
        return (
            f"RenderStyle(r={self.r:.3f}, g={self.g:.3f}, b={self.b:.3f}, "
            f"transparency={self.transparency:.3f})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RenderStyle):
            return NotImplemented
        return (
            self.r == other.r
            and self.g == other.g
            and self.b == other.b
            and self.transparency == other.transparency
        )


# ------------------------------------------------------------------
# Internal parser
# ------------------------------------------------------------------

def _parse_colour(colour: _ColourInput) -> Tuple[float, float, float]:
    """Return (r, g, b) as floats 0–1."""
    if isinstance(colour, str):
        return _parse_hex(colour)
    if isinstance(colour, (tuple, list)):
        return _parse_tuple(colour)
    raise TypeError(
        f"colour must be a hex string or RGB tuple, got {type(colour).__name__!r}"
    )


def _parse_hex(s: str) -> Tuple[float, float, float]:
    s = s.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", s):
        raise ValueError(
            f"Invalid hex colour {s!r}. Expected #RRGGBB."
        )
    r = int(s[0:2], 16) / 255.0
    g = int(s[2:4], 16) / 255.0
    b = int(s[4:6], 16) / 255.0
    return r, g, b


def _parse_tuple(t: tuple) -> Tuple[float, float, float]:
    if len(t) != 3:
        raise ValueError(f"colour tuple must have 3 elements, got {len(t)}")

    vals = [float(v) for v in t]

    # Detect int vs float format: any value > 1 means int (0–255) format
    if any(v > 1.0 for v in vals):
        r, g, b = vals[0] / 255.0, vals[1] / 255.0, vals[2] / 255.0
    else:
        r, g, b = vals[0], vals[1], vals[2]

    for name, v in (("r", r), ("g", g), ("b", b)):
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"colour component {name!r} out of range: {v}")

    return r, g, b
