"""
ifckit.profiles.steel
=====================

European structural steel section lookup table.

Supported families:
  HEA, HEB, HEM          — European wide-flange (H-series)
  IPE                    — European I-beam
  UNP                    — European standard channel (U-section)
  CHS                    — Circular Hollow Section  (tube)
  RHS                    — Rectangular Hollow Section
  SHS                    — Square Hollow Section  (special case of RHS)

Usage::

    from ifckit.profiles import SteelProfile

    p = SteelProfile.from_name("HEA200")   # → IBeamProfile
    p = SteelProfile.from_name("IPE300")   # → IBeamProfile
    p = SteelProfile.from_name("CHS168.3x10")  # → HollowCircleProfile
    p = SteelProfile.from_name("RHS200x100x8") # → HollowRectangleProfile (future)

    print(p.area, p.name)
    ifc_entity = p.to_ifc(ifc_file)

All dimensions are in **metres** (ifckit internal unit).

Table data sourced from:
  ArcelorMittal "Sections & Merchant Bars" catalogue (2021)
  and EN 10210 / EN 10219 for hollow sections.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple

from ifckit.profiles.i_beam import IBeamProfile
from ifckit.profiles.shapes import CircleProfile, HollowCircleProfile
from ifckit.schema import LengthUnit


# ---------------------------------------------------------------------------
# I/H-section table
# Entries: name → (height_mm, width_mm, web_thickness_mm, flange_thickness_mm)
# ---------------------------------------------------------------------------

_I_SECTIONS: Dict[str, Tuple[float, float, float, float]] = {
    # HEA
    "HEA100": (96,   100,  5.0,  8.0),
    "HEA120": (114,  120,  5.0,  8.0),
    "HEA140": (133,  140,  5.5,  8.5),
    "HEA160": (152,  160,  6.0,  9.0),
    "HEA180": (171,  180,  6.0,  9.5),
    "HEA200": (190,  200,  6.5, 10.0),
    "HEA220": (210,  220,  7.0, 11.0),
    "HEA240": (230,  240,  7.5, 12.0),
    "HEA260": (250,  260,  7.5, 12.5),
    "HEA280": (270,  280,  8.0, 13.0),
    "HEA300": (290,  300,  8.5, 14.0),
    "HEA320": (310,  300,  9.0, 15.5),
    "HEA340": (330,  300,  9.5, 16.5),
    "HEA360": (350,  300, 10.0, 17.5),
    "HEA400": (390,  300, 11.0, 19.0),
    "HEA450": (440,  300, 11.5, 21.0),
    "HEA500": (490,  300, 12.0, 23.0),
    "HEA550": (540,  300, 12.5, 24.0),
    "HEA600": (590,  300, 13.0, 25.0),
    "HEA650": (640,  300, 13.5, 26.0),
    "HEA700": (690,  300, 14.5, 27.0),
    "HEA800": (790,  300, 15.0, 28.0),
    "HEA900": (890,  300, 16.0, 30.0),
    "HEA1000": (990, 300, 16.5, 31.0),
    # HEB
    "HEB100": (100,  100,  6.0, 10.0),
    "HEB120": (120,  120,  6.5, 11.0),
    "HEB140": (140,  140,  7.0, 12.0),
    "HEB160": (160,  160,  8.0, 13.0),
    "HEB180": (180,  180,  8.5, 14.0),
    "HEB200": (200,  200,  9.0, 15.0),
    "HEB220": (220,  220,  9.5, 16.0),
    "HEB240": (240,  240, 10.0, 17.0),
    "HEB260": (260,  260, 10.0, 17.5),
    "HEB280": (280,  280, 10.5, 18.0),
    "HEB300": (300,  300, 11.0, 19.0),
    "HEB320": (320,  300, 11.5, 20.5),
    "HEB340": (340,  300, 12.0, 21.5),
    "HEB360": (360,  300, 12.5, 22.5),
    "HEB400": (400,  300, 13.5, 24.0),
    "HEB450": (450,  300, 14.0, 26.0),
    "HEB500": (500,  300, 14.5, 28.0),
    "HEB550": (550,  300, 15.0, 29.0),
    "HEB600": (600,  300, 15.5, 30.0),
    "HEB650": (650,  300, 16.0, 31.0),
    "HEB700": (700,  300, 17.0, 32.0),
    "HEB800": (800,  300, 17.5, 33.0),
    "HEB900": (900,  300, 18.5, 35.0),
    "HEB1000": (1000, 300, 19.0, 36.0),
    # HEM
    "HEM100": (120,  106, 12.0, 20.0),
    "HEM120": (140,  126, 12.5, 21.0),
    "HEM140": (160,  146, 13.0, 22.0),
    "HEM160": (180,  166, 14.0, 23.0),
    "HEM180": (200,  186, 14.5, 24.0),
    "HEM200": (220,  206, 15.0, 25.0),
    "HEM220": (240,  226, 15.5, 26.0),
    "HEM240": (270,  248, 18.0, 32.0),
    "HEM260": (290,  268, 18.0, 32.5),
    "HEM280": (310,  288, 18.5, 33.0),
    "HEM300": (340,  310, 21.0, 39.0),
    "HEM320": (359,  309, 21.0, 40.0),
    "HEM340": (377,  309, 21.0, 40.0),
    "HEM360": (395,  308, 21.0, 40.0),
    "HEM400": (432,  307, 21.0, 40.0),
    "HEM450": (478,  307, 21.0, 40.0),
    "HEM500": (524,  306, 21.0, 40.0),
    "HEM550": (572,  306, 21.0, 40.0),
    "HEM600": (620,  305, 21.0, 40.0),
    "HEM650": (668,  305, 21.0, 40.0),
    "HEM700": (716,  304, 21.0, 40.0),
    "HEM800": (814,  303, 21.0, 40.0),
    "HEM900": (910,  302, 21.0, 40.0),
    "HEM1000": (1008, 302, 21.0, 40.0),
    # IPE
    "IPE80":  ( 80,  46,  3.8,  5.2),
    "IPE100": (100,  55,  4.1,  5.7),
    "IPE120": (120,  64,  4.4,  6.3),
    "IPE140": (140,  73,  4.7,  6.9),
    "IPE160": (160,  82,  5.0,  7.4),
    "IPE180": (180,  91,  5.3,  8.0),
    "IPE200": (200, 100,  5.6,  8.5),
    "IPE220": (220, 110,  5.9,  9.2),
    "IPE240": (240, 120,  6.2,  9.8),
    "IPE270": (270, 135,  6.6, 10.2),
    "IPE300": (300, 150,  7.1, 10.7),
    "IPE330": (330, 160,  7.5, 11.5),
    "IPE360": (360, 170,  8.0, 12.7),
    "IPE400": (400, 180,  8.6, 13.5),
    "IPE450": (450, 190,  9.4, 14.6),
    "IPE500": (500, 200, 10.2, 16.0),
    "IPE550": (550, 210, 11.1, 17.2),
    "IPE600": (600, 220, 12.0, 19.0),
}

# ---------------------------------------------------------------------------
# CHS table: name → (outer_diameter_mm, wall_thickness_mm)
# Representative EN 10210 sizes
# ---------------------------------------------------------------------------

_CHS_SECTIONS: Dict[str, Tuple[float, float]] = {
    "CHS21.3x2":    (21.3,  2.0),
    "CHS26.9x2":    (26.9,  2.0),
    "CHS33.7x2":    (33.7,  2.0),
    "CHS33.7x3":    (33.7,  3.0),
    "CHS42.4x2":    (42.4,  2.0),
    "CHS42.4x3":    (42.4,  3.0),
    "CHS48.3x3":    (48.3,  3.0),
    "CHS48.3x4":    (48.3,  4.0),
    "CHS60.3x3":    (60.3,  3.0),
    "CHS60.3x4":    (60.3,  4.0),
    "CHS76.1x3":    (76.1,  3.0),
    "CHS76.1x5":    (76.1,  5.0),
    "CHS88.9x3":    (88.9,  3.0),
    "CHS88.9x5":    (88.9,  5.0),
    "CHS101.6x4":   (101.6, 4.0),
    "CHS114.3x4":   (114.3, 4.0),
    "CHS114.3x6":   (114.3, 6.0),
    "CHS139.7x5":   (139.7, 5.0),
    "CHS139.7x8":   (139.7, 8.0),
    "CHS168.3x5":   (168.3, 5.0),
    "CHS168.3x8":   (168.3, 8.0),
    "CHS168.3x10":  (168.3, 10.0),
    "CHS193.7x6":   (193.7, 6.0),
    "CHS193.7x10":  (193.7, 10.0),
    "CHS219.1x6":   (219.1, 6.0),
    "CHS219.1x10":  (219.1, 10.0),
    "CHS244.5x6":   (244.5, 6.0),
    "CHS244.5x10":  (244.5, 10.0),
    "CHS273x6":     (273.0, 6.0),
    "CHS273x10":    (273.0, 10.0),
    "CHS323.9x8":   (323.9, 8.0),
    "CHS323.9x12":  (323.9, 12.0),
    "CHS355.6x8":   (355.6, 8.0),
    "CHS355.6x12":  (355.6, 12.0),
    "CHS406.4x10":  (406.4, 10.0),
    "CHS406.4x16":  (406.4, 16.0),
    "CHS457x10":    (457.0, 10.0),
    "CHS457x16":    (457.0, 16.0),
    "CHS508x10":    (508.0, 10.0),
    "CHS508x16":    (508.0, 16.0),
}

# ---------------------------------------------------------------------------
# UNP (standard channel) table
# Entries: name → (height_mm, flange_width_mm, web_thickness_mm, flange_thickness_mm)
# NB: UNP is not symmetric — we approximate as a closed polygon profile.
# For simplicity we store it as I-section geometry (flanges on one side only)
# by using the IBeamProfile with half-width semantics, but the correct approach
# would be a dedicated UProfile.  For now we store the data for future use.
# ---------------------------------------------------------------------------

_UNP_SECTIONS: Dict[str, Tuple[float, float, float, float]] = {
    "UNP50":  ( 50,  38, 5.0,  7.0),
    "UNP65":  ( 65,  42, 5.5,  7.5),
    "UNP80":  ( 80,  45, 6.0,  8.0),
    "UNP100": (100,  50, 6.0,  8.5),
    "UNP120": (120,  55, 7.0,  9.0),
    "UNP140": (140,  60, 7.0,  9.5),
    "UNP160": (160,  65, 7.5, 10.0),
    "UNP180": (180,  70, 8.0, 10.5),
    "UNP200": (200,  75, 8.5, 11.5),
    "UNP220": (220,  80, 9.0, 12.5),
    "UNP240": (240,  85, 9.5, 13.0),
    "UNP260": (260,  90, 10.0, 14.0),
    "UNP280": (280,  95, 10.0, 15.0),
    "UNP300": (300, 100, 10.0, 16.0),
    "UNP320": (320, 100, 11.0, 17.0),
    "UNP350": (350, 100, 12.0, 17.0),
    "UNP380": (380, 102, 13.5, 18.0),
    "UNP400": (400, 110, 14.0, 18.0),
}


# ---------------------------------------------------------------------------
# SteelProfile — factory + lookup
# ---------------------------------------------------------------------------

class SteelProfile:
    """
    Factory class for looking up standard European steel sections by name.

    Returns a concrete ``Profile`` subclass instance with the correct
    dimensions pre-filled.

    Supported name formats
    ----------------------
    - ``HEA200``, ``HEB300``, ``HEM400``   → ``IBeamProfile``
    - ``IPE300``, ``IPE500``               → ``IBeamProfile``
    - ``CHS168.3x10``                      → ``HollowCircleProfile``
    - ``CHS273x6``                         → ``HollowCircleProfile``

    UNP sections are in the data table but return ``IBeamProfile`` as a
    temporary approximation.  A dedicated ``UProfile`` will replace this.

    Args:
        name: Section designation, case-insensitive.

    Returns:
        A ``Profile`` subclass instance.

    Raises:
        KeyError: If the section name is not in the lookup table.
    """

    @staticmethod
    def from_name(name: str, anchor: str = "c", unit: LengthUnit = LengthUnit.METRE) -> "object":
        """
        Look up a steel section and return the appropriate ``Profile`` object.

        Args:
            name:   Section designation (e.g. ``"HEA200"``, ``"IPE300"``,
                    ``"CHS168.3x10"``).
            anchor: Anchor point for I/H profiles (default ``"c"`` = centroid).
            unit:   Target length unit for the returned profile dimensions.
                    ``LengthUnit.METRE`` (default) divides table values (mm) by 1000.
                    ``LengthUnit.MILLIMETRE`` returns dimensions in mm as-is.

        Returns:
            ``IBeamProfile``, ``HollowCircleProfile``, or another ``Profile`` subclass.

        Raises:
            KeyError: Unknown section name.
        """
        key = name.strip().upper()
        scale = 1.0 if unit == LengthUnit.MILLIMETRE else 1 / 1000

        # --- I/H sections ---
        if key in _I_SECTIONS:
            h, b, tw, tf = _I_SECTIONS[key]
            return IBeamProfile(
                height=h * scale,
                width=b * scale,
                web_thickness=tw * scale,
                flange_thickness=tf * scale,
                anchor=anchor,
                name=name,
            )

        # --- CHS sections ---
        if key in _CHS_SECTIONS:
            d_mm, t_mm = _CHS_SECTIONS[key]
            return HollowCircleProfile(
                radius=d_mm / 2 * scale,
                wall_thickness=t_mm * scale,
                name=name,
            )

        # --- Parse CHS on-the-fly: CHSddd.dxtt.t ---
        chs_match = re.fullmatch(
            r"CHS(\d+(?:\.\d+)?)X(\d+(?:\.\d+)?)", key
        )
        if chs_match:
            d_mm = float(chs_match.group(1))
            t_mm = float(chs_match.group(2))
            return HollowCircleProfile(
                radius=d_mm / 2 * scale,
                wall_thickness=t_mm * scale,
                name=name,
            )

        # --- UNP sections (approximate) ---
        if key in _UNP_SECTIONS:
            h, b, tw, tf = _UNP_SECTIONS[key]
            return IBeamProfile(
                height=h * scale,
                width=b * scale,
                web_thickness=tw * scale,
                flange_thickness=tf * scale,
                anchor=anchor,
                name=name,
            )

        raise KeyError(
            f"Unknown steel section {name!r}. "
            "Use SteelProfile.available() to list all known sections."
        )

    @staticmethod
    def available() -> Dict[str, list]:
        """
        Return a dict of all registered section names grouped by family.

        Returns:
            ``{"HEA": [...], "HEB": [...], "IPE": [...], "CHS": [...], ...}``
        """
        families: Dict[str, list] = {
            "HEA": [], "HEB": [], "HEM": [], "IPE": [], "UNP": [], "CHS": [],
        }
        for k in _I_SECTIONS:
            for fam in ("HEA", "HEB", "HEM", "IPE", "UNP"):
                if k.startswith(fam):
                    families[fam].append(k)
                    break
        for k in _CHS_SECTIONS:
            families["CHS"].append(k)
        return families
