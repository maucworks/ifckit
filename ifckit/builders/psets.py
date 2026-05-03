"""
ifckit.builders.psets
=====================

Helpers to write IFC property sets on any element.

Two psets are written per element:

``EPset_IfcKit_Geometry``
    Auto-computed geometry metadata.  Always written; never user-overridable.

    All elements
    ------------
    Name              IfcLabel

    PendingBeam / PendingColumn (straight extrusion)
    -------------------------------------------------
    Length            IfcLengthMeasure   (metres)
    CrossSectionArea  IfcAreaMeasure     (m²)   — if profile.area() is not None
    SteelSectionName  IfcLabel           — if profile carries a known steel name

    PendingRevolvedBeam
    -------------------
    ArcLength         IfcLengthMeasure   (metres)
    ArcAngle_rad      IfcReal            (radians)
    ArcAngle_deg      IfcReal            (degrees)
    CrossSectionArea  IfcAreaMeasure     (m²)   — if profile.area() is not None
    SteelSectionName  IfcLabel           — if profile carries a known steel name

    PendingWall
    -----------
    Length            IfcLengthMeasure   (metres, longest footprint edge)
    Height            IfcLengthMeasure   (metres)

``EPset_IfcKit``
    User-supplied free dict (``pending.properties``).  Written only when
    ``pending.properties`` is non-empty.  Values are type-inferred:
      bool  → IfcBoolean
      int   → IfcInteger
      float → IfcReal
      str   → IfcLabel
      other → IfcLabel (str coercion)
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Sequence

import ifcopenshell
import ifcopenshell.api

from ifckit.elements.base import PendingElement

# ---------------------------------------------------------------------------
# Known steel section names (used to detect SteelSectionName on a profile)
# ---------------------------------------------------------------------------


def _steel_section_name(profile_source) -> Optional[str]:
    """Return the steel section name if the profile source is a known steel section."""
    if profile_source is None:
        return None
    try:
        from ifckit.profiles.steel import SteelProfile

        available_flat = {name for names in SteelProfile.available().values() for name in names}
        pname = getattr(profile_source, "name", None) or ""
        if pname.strip().upper() in available_flat:
            return pname
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# IFC value helpers
# ---------------------------------------------------------------------------


def _ifc_value(ifc_file: ifcopenshell.file, value: Any):
    """Wrap a Python value in the appropriate IfcValue type."""
    if isinstance(value, bool):
        return ifc_file.create_entity("IfcBoolean", value)
    if isinstance(value, int):
        return ifc_file.create_entity("IfcInteger", value)
    if isinstance(value, float):
        return ifc_file.create_entity("IfcReal", value)
    return ifc_file.create_entity("IfcLabel", str(value))


def _prop(ifc_file: ifcopenshell.file, name: str, value: Any):
    """Create an IfcPropertySingleValue."""
    return ifc_file.create_entity(
        "IfcPropertySingleValue",
        Name=name,
        NominalValue=_ifc_value(ifc_file, value),
    )


def _length_prop(ifc_file: ifcopenshell.file, name: str, value: float):
    return ifc_file.create_entity(
        "IfcPropertySingleValue",
        Name=name,
        NominalValue=ifc_file.create_entity("IfcLengthMeasure", value),
    )


def _area_prop(ifc_file: ifcopenshell.file, name: str, value: float):
    return ifc_file.create_entity(
        "IfcPropertySingleValue",
        Name=name,
        NominalValue=ifc_file.create_entity("IfcAreaMeasure", value),
    )


def _label_prop(ifc_file: ifcopenshell.file, name: str, value: str):
    return ifc_file.create_entity(
        "IfcPropertySingleValue",
        Name=name,
        NominalValue=ifc_file.create_entity("IfcLabel", value),
    )


def _real_prop(ifc_file: ifcopenshell.file, name: str, value: float):
    return ifc_file.create_entity(
        "IfcPropertySingleValue",
        Name=name,
        NominalValue=ifc_file.create_entity("IfcReal", value),
    )


# ---------------------------------------------------------------------------
# Pset writer
# ---------------------------------------------------------------------------


def _write_pset(
    ifc_file: ifcopenshell.file,
    element: ifcopenshell.entity_instance,
    pset_name: str,
    props: Sequence,
) -> None:
    """Create an IfcPropertySet and relate it to element."""
    if not props:
        return
    pset = ifc_file.create_entity(
        "IfcPropertySet",
        GlobalId=ifcopenshell.guid.new(),
        Name=pset_name,
        HasProperties=list(props),
    )
    ifc_file.create_entity(
        "IfcRelDefinesByProperties",
        GlobalId=ifcopenshell.guid.new(),
        RelatedObjects=[element],
        RelatingPropertyDefinition=pset,
    )


# ---------------------------------------------------------------------------
# Geometry pset builders per element type
# ---------------------------------------------------------------------------


def _geometry_props_extruded(ifc_file, pending) -> list:
    """Properties for PendingBeam / PendingColumn (straight extrusion)."""
    props = []
    if pending.name:
        props.append(_label_prop(ifc_file, "Name", pending.name))

    # Length from axis
    try:
        props.append(_length_prop(ifc_file, "Length", pending.axis.length))
    except Exception:
        pass

    # Cross-section area
    profile_source = getattr(pending, "_profile_source", None)
    if profile_source is not None:
        try:
            area = profile_source.area
            if area is not None:
                props.append(_area_prop(ifc_file, "CrossSectionArea", area))
        except Exception:
            pass

    # Steel section name
    steel_name = _steel_section_name(profile_source)
    if steel_name:
        props.append(_label_prop(ifc_file, "SteelSectionName", steel_name))

    return props


def _geometry_props_revolved(ifc_file, pending) -> list:
    """Properties for PendingRevolvedBeam."""
    props = []
    if pending.name:
        props.append(_label_prop(ifc_file, "Name", pending.name))

    arc = pending.arc
    try:
        # Arc radius is the distance from center to start
        radius = (arc.start - arc.center).length()
        arc_length = radius * abs(arc.angle)
        props.append(_length_prop(ifc_file, "ArcLength", arc_length))
        props.append(_real_prop(ifc_file, "ArcAngle_rad", arc.angle))
        props.append(_real_prop(ifc_file, "ArcAngle_deg", math.degrees(arc.angle)))
    except Exception:
        pass

    # Cross-section area
    profile_source = getattr(pending, "_profile_source", None)
    if profile_source is not None:
        try:
            area = profile_source.area
            if area is not None:
                props.append(_area_prop(ifc_file, "CrossSectionArea", area))
        except Exception:
            pass

    # Steel section name
    steel_name = _steel_section_name(profile_source)
    if steel_name:
        props.append(_label_prop(ifc_file, "SteelSectionName", steel_name))

    return props


def _geometry_props_wall(ifc_file, pending) -> list:
    """Properties for PendingWall."""
    props = []
    if pending.name:
        props.append(_label_prop(ifc_file, "Name", pending.name))
    try:
        # Length = longest edge of the footprint
        pts = pending.footprint
        if len(pts) >= 2:
            edges = [(pts[i] - pts[i - 1]).length() for i in range(1, len(pts))]
            props.append(_length_prop(ifc_file, "Length", max(edges)))
    except Exception:
        pass
    try:
        props.append(_length_prop(ifc_file, "Height", pending.height))
    except Exception:
        pass
    return props


def _geometry_props_generic(ifc_file, pending) -> list:
    """Fallback: just the name."""
    props = []
    if pending.name:
        props.append(_label_prop(ifc_file, "Name", pending.name))
    return props


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def write_psets(
    ifc_file: ifcopenshell.file,
    element: ifcopenshell.entity_instance,
    pending: PendingElement,
) -> None:
    """
    Write ``EPset_IfcKit_Geometry`` and (if non-empty) ``EPset_IfcKit``
    property sets onto *element*.

    Call this immediately after creating the IFC element entity.
    """
    # --- geometry pset ---
    etype = getattr(pending, "element_type", "")
    if etype in ("basic_beam", "basic_column"):
        geo_props = _geometry_props_extruded(ifc_file, pending)
    elif etype == "revolved_beam":
        geo_props = _geometry_props_revolved(ifc_file, pending)
    elif etype == "basic_wall":
        geo_props = _geometry_props_wall(ifc_file, pending)
    else:
        geo_props = _geometry_props_generic(ifc_file, pending)

    _write_pset(ifc_file, element, "EPset_IfcKit_Geometry", geo_props)

    # --- user pset ---
    user_props_dict: Dict[str, Any] = getattr(pending, "properties", {}) or {}
    if user_props_dict:
        user_props = [_prop(ifc_file, k, v) for k, v in user_props_dict.items()]
        _write_pset(ifc_file, element, "EPset_IfcKit", user_props)


__all__ = ["write_psets"]
