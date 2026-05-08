"""
ifckit.profiles.sections
========================

Additional parametric section profiles:

  TShapeProfile         — T-section               → IfcTShapeProfileDef
  ZShapeProfile         — Z-section               → IfcZShapeProfileDef
  CShapeProfile         — C/channel section       → IfcCShapeProfileDef
  TrapeziumProfile      — general trapezium       → IfcTrapeziumProfileDef
  CompositeProfile      — composition of profiles → IfcCompositeProfileDef

All follow the same pattern as IBeamProfile / LBeamProfile:
  - get_profile_points()  → (x, y) polygon outline
  - to_ifc()              → native IfcXxxProfileDef
  - to_dict() / from_dict()
  - super().__init__() + _init_transform()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from ifckit.profiles.base import Profile

if TYPE_CHECKING:
    import ifcopenshell


# ---------------------------------------------------------------------------
# TShapeProfile
# ---------------------------------------------------------------------------


class TShapeProfile(Profile):
    """
    T-section profile.

    IFC native: ``IfcTShapeProfileDef``.

    Natural origin at bottom-centre of web (the stem tip).

    Args:
        depth:            Total height (flange face to web tip), m.
        flange_width:     Full width of flange, m.
        web_thickness:    Web (stem) thickness, m.
        flange_thickness: Flange thickness, m.
        name:             Optional profile name.
        rotation:         CCW rotation (rad).
        offset_x:         X translation (m).
        offset_y:         Y translation (m).
    """

    profile_type = "t_shape"

    def __init__(
        self,
        depth: float = 0.2,
        flange_width: float = 0.15,
        web_thickness: float = 0.01,
        flange_thickness: float = 0.015,
        name: Optional[str] = None,
        rotation: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        if depth <= 0:
            raise ValueError("depth must be positive")
        if flange_width <= 0:
            raise ValueError("flange_width must be positive")
        if web_thickness <= 0 or web_thickness >= flange_width:
            raise ValueError("web_thickness must be > 0 and < flange_width")
        if flange_thickness <= 0 or flange_thickness >= depth:
            raise ValueError("flange_thickness must be > 0 and < depth")
        self.depth = float(depth)
        self.flange_width = float(flange_width)
        self.web_thickness = float(web_thickness)
        self.flange_thickness = float(flange_thickness)
        self.name = name
        super().__init__()
        self._init_transform(rotation, offset_x, offset_y)

    @property
    def area(self) -> float:
        web_h = self.depth - self.flange_thickness
        return self.flange_width * self.flange_thickness + web_h * self.web_thickness

    def get_profile_points(self) -> List[Tuple[float, float]]:
        hw = self.flange_width / 2
        htw = self.web_thickness / 2
        d = self.depth
        tf = self.flange_thickness
        # origin at bottom-centre; flange at top
        pts = [
            (-htw, 0.0),
            (htw, 0.0),
            (htw, d - tf),
            (hw, d - tf),
            (hw, d),
            (-hw, d),
            (-hw, d - tf),
            (-htw, d - tf),
        ]
        return self._apply_transform(pts)

    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        pos = self._ifc_placement_2d(ifc_file)
        return ifc_file.create_entity(
            "IfcTShapeProfileDef",
            ProfileType="AREA",
            ProfileName=self.name,
            Position=pos,
            Depth=self.depth,
            FlangeWidth=self.flange_width,
            WebThickness=self.web_thickness,
            FlangeThickness=self.flange_thickness,
            FilletRadius=None,
            FlangeEdgeRadius=None,
            WebEdgeRadius=None,
            WebSlope=None,
            FlangeSlope=None,
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "profile_type": self.profile_type,
            "depth": self.depth,
            "flange_width": self.flange_width,
            "web_thickness": self.web_thickness,
            "flange_thickness": self.flange_thickness,
            **self._transform_dict(),
        }
        if self.name is not None:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TShapeProfile":
        r, ox, oy = cls._transform_from_dict(d)
        return cls(
            depth=d["depth"],
            flange_width=d["flange_width"],
            web_thickness=d["web_thickness"],
            flange_thickness=d["flange_thickness"],
            name=d.get("name"),
            rotation=r,
            offset_x=ox,
            offset_y=oy,
        )


# ---------------------------------------------------------------------------
# ZShapeProfile
# ---------------------------------------------------------------------------


class ZShapeProfile(Profile):
    """
    Z-section profile.

    IFC native: ``IfcZShapeProfileDef``.

    Origin at centroid of web.

    Args:
        depth:            Web height (m).
        flange_width:     Length of each flange leg (m).
        web_thickness:    Web thickness (m).
        flange_thickness: Flange thickness (m).
        name:             Optional profile name.
    """

    profile_type = "z_shape"

    def __init__(
        self,
        depth: float = 0.2,
        flange_width: float = 0.08,
        web_thickness: float = 0.008,
        flange_thickness: float = 0.012,
        name: Optional[str] = None,
        rotation: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        if depth <= 0:
            raise ValueError("depth must be positive")
        if flange_width <= 0:
            raise ValueError("flange_width must be positive")
        if web_thickness <= 0 or web_thickness >= flange_width:
            raise ValueError("web_thickness must be > 0 and < flange_width")
        if flange_thickness <= 0 or flange_thickness * 2 >= depth:
            raise ValueError("flange_thickness must be > 0 and < depth/2")
        self.depth = float(depth)
        self.flange_width = float(flange_width)
        self.web_thickness = float(web_thickness)
        self.flange_thickness = float(flange_thickness)
        self.name = name
        super().__init__()
        self._init_transform(rotation, offset_x, offset_y)

    @property
    def area(self) -> float:
        web_h = self.depth - 2 * self.flange_thickness
        return 2 * self.flange_width * self.flange_thickness + web_h * self.web_thickness

    def get_profile_points(self) -> List[Tuple[float, float]]:
        """Z-shape: bottom flange goes right, top flange goes left."""
        d = self.depth
        fw = self.flange_width
        tw = self.web_thickness
        tf = self.flange_thickness
        htw = tw / 2
        hd = d / 2
        # CCW winding, origin at web centroid
        pts = [
            (-htw, -hd),
            (fw - htw, -hd),
            (fw - htw, -hd + tf),
            (htw, -hd + tf),
            (htw, hd - tf),
            (fw + htw, hd - tf),  # wrong — correct below
        ]
        # Rebuild carefully: Z goes bottom-right, top-left
        pts = [
            (-htw, -hd),  # bottom-left of web
            (fw - htw, -hd),  # bottom-right of bottom flange
            (fw - htw, -hd + tf),  # inner-right of bottom flange
            (htw, -hd + tf),  # inner-right of web (bottom)
            (htw, hd - tf),  # inner-left of web (top)
            (htw - fw, hd - tf),  # inner-left of top flange
            (htw - fw, hd),  # outer-left of top flange
            (-htw, hd),  # top-left of web
        ]
        return self._apply_transform(pts)

    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        pos = self._ifc_placement_2d(ifc_file)
        return ifc_file.create_entity(
            "IfcZShapeProfileDef",
            ProfileType="AREA",
            ProfileName=self.name,
            Position=pos,
            Depth=self.depth,
            FlangeWidth=self.flange_width,
            WebThickness=self.web_thickness,
            FlangeThickness=self.flange_thickness,
            FilletRadius=None,
            EdgeRadius=None,
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "profile_type": self.profile_type,
            "depth": self.depth,
            "flange_width": self.flange_width,
            "web_thickness": self.web_thickness,
            "flange_thickness": self.flange_thickness,
            **self._transform_dict(),
        }
        if self.name is not None:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ZShapeProfile":
        r, ox, oy = cls._transform_from_dict(d)
        return cls(
            depth=d["depth"],
            flange_width=d["flange_width"],
            web_thickness=d["web_thickness"],
            flange_thickness=d["flange_thickness"],
            name=d.get("name"),
            rotation=r,
            offset_x=ox,
            offset_y=oy,
        )


# ---------------------------------------------------------------------------
# CShapeProfile
# ---------------------------------------------------------------------------


class CShapeProfile(Profile):
    """
    C-section (lipped channel) profile.

    IFC native: ``IfcCShapeProfileDef``.

    Symmetric about Y-axis. Origin at web centroid.

    Args:
        depth:            Overall height (m).
        width:            Overall width (flange + lip, outer-to-outer) (m).
        wall_thickness:   Uniform wall thickness (m).
        girth:            Lip length (m). Default 0 = no lip.
        name:             Optional profile name.
    """

    profile_type = "c_shape"

    def __init__(
        self,
        depth: float = 0.2,
        width: float = 0.08,
        wall_thickness: float = 0.003,
        girth: float = 0.0,
        name: Optional[str] = None,
        rotation: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        if depth <= 0:
            raise ValueError("depth must be positive")
        if width <= 0:
            raise ValueError("width must be positive")
        if wall_thickness <= 0 or wall_thickness >= width / 2 or wall_thickness >= depth / 2:
            raise ValueError("wall_thickness out of range")
        if girth < 0:
            raise ValueError("girth must be >= 0")
        self.depth = float(depth)
        self.width = float(width)
        self.wall_thickness = float(wall_thickness)
        self.girth = float(girth)
        self.name = name
        super().__init__()
        self._init_transform(rotation, offset_x, offset_y)

    @property
    def area(self) -> float:
        t = self.wall_thickness
        d = self.depth
        w = self.width
        g = self.girth
        web = (d - 2 * t) * t
        flanges = 2 * (w - t) * t
        lips = 2 * g * t
        return web + flanges + lips

    def get_profile_points(self) -> List[Tuple[float, float]]:
        d = self.depth
        w = self.width
        t = self.wall_thickness
        g = self.girth
        hd = d / 2
        # Outer closed profile (simplified — no inner void for get_profile_points)
        # Build as a solid outline going around the C shape outer/inner boundary
        # Outer face: left side going up, top flange right, right lip down, etc.
        if g > 0:
            pts = [
                (0.0, -hd),  # bottom inner-left
                (w, -hd),  # bottom outer-right
                (w, -hd + g),  # bottom lip end
                (w - t, -hd + g),  # bottom lip inner
                (w - t, -hd + t),  # bottom flange inner corner
                (t, -hd + t),  # web bottom-inner-right
                (t, hd - t),  # web top-inner-right
                (w - t, hd - t),  # top flange inner corner
                (w - t, hd - g),  # top lip inner
                (w, hd - g),  # top lip outer
                (w, hd),  # top outer-right
                (0.0, hd),  # top outer-left
            ]
        else:
            pts = [
                (0.0, -hd),
                (w, -hd),
                (w - t, -hd + t) if False else (w, -hd),  # placeholder
            ]
            # Simple C without lip
            pts = [
                (0.0, -hd),
                (w, -hd),
                (w, -hd + t),
                (t, -hd + t),
                (t, hd - t),
                (w, hd - t),
                (w, hd),
                (0.0, hd),
            ]
        return self._apply_transform(pts)

    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        pos = self._ifc_placement_2d(ifc_file)
        return ifc_file.create_entity(
            "IfcCShapeProfileDef",
            ProfileType="AREA",
            ProfileName=self.name,
            Position=pos,
            Depth=self.depth,
            Width=self.width,
            WallThickness=self.wall_thickness,
            Girth=self.girth if self.girth > 0 else None,
            InternalFilletRadius=None,
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "profile_type": self.profile_type,
            "depth": self.depth,
            "width": self.width,
            "wall_thickness": self.wall_thickness,
            "girth": self.girth,
            **self._transform_dict(),
        }
        if self.name is not None:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CShapeProfile":
        r, ox, oy = cls._transform_from_dict(d)
        return cls(
            depth=d["depth"],
            width=d["width"],
            wall_thickness=d["wall_thickness"],
            girth=d.get("girth", 0.0),
            name=d.get("name"),
            rotation=r,
            offset_x=ox,
            offset_y=oy,
        )


# ---------------------------------------------------------------------------
# TrapeziumProfile
# ---------------------------------------------------------------------------


class TrapeziumProfile(Profile):
    """
    General trapezium (quadrilateral with one pair of parallel sides) profile.

    IFC native: ``IfcTrapeziumProfileDef``.

    Bottom edge centred on X-axis.

    Args:
        bottom_x_dim:   Width of bottom edge (m).
        top_x_dim:      Width of top edge (m).
        y_dim:          Height (m).
        top_x_offset:   Horizontal offset of top edge midpoint from bottom
                        edge midpoint (m).  0 = symmetric trapezium.
        name:           Optional profile name.
    """

    profile_type = "trapezium"

    def __init__(
        self,
        bottom_x_dim: float = 0.3,
        top_x_dim: float = 0.15,
        y_dim: float = 0.2,
        top_x_offset: float = 0.0,
        name: Optional[str] = None,
        rotation: float = 0.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        if bottom_x_dim <= 0:
            raise ValueError("bottom_x_dim must be positive")
        if top_x_dim <= 0:
            raise ValueError("top_x_dim must be positive")
        if y_dim <= 0:
            raise ValueError("y_dim must be positive")
        self.bottom_x_dim = float(bottom_x_dim)
        self.top_x_dim = float(top_x_dim)
        self.y_dim = float(y_dim)
        self.top_x_offset = float(top_x_offset)
        self.name = name
        super().__init__()
        self._init_transform(rotation, offset_x, offset_y)

    @property
    def area(self) -> float:
        return (self.bottom_x_dim + self.top_x_dim) / 2 * self.y_dim

    def get_profile_points(self) -> List[Tuple[float, float]]:
        hb = self.bottom_x_dim / 2
        ht = self.top_x_dim / 2
        ox = self.top_x_offset
        pts = [
            (-hb, 0.0),
            (hb, 0.0),
            (ox + ht, self.y_dim),
            (ox - ht, self.y_dim),
        ]
        return self._apply_transform(pts)

    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        pos = self._ifc_placement_2d(ifc_file)
        return ifc_file.create_entity(
            "IfcTrapeziumProfileDef",
            ProfileType="AREA",
            ProfileName=self.name,
            Position=pos,
            BottomXDim=self.bottom_x_dim,
            TopXDim=self.top_x_dim,
            YDim=self.y_dim,
            TopXOffset=self.top_x_offset,
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "profile_type": self.profile_type,
            "bottom_x_dim": self.bottom_x_dim,
            "top_x_dim": self.top_x_dim,
            "y_dim": self.y_dim,
            "top_x_offset": self.top_x_offset,
            **self._transform_dict(),
        }
        if self.name is not None:
            d["name"] = self.name
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TrapeziumProfile":
        r, ox, oy = cls._transform_from_dict(d)
        return cls(
            bottom_x_dim=d["bottom_x_dim"],
            top_x_dim=d["top_x_dim"],
            y_dim=d["y_dim"],
            top_x_offset=d.get("top_x_offset", 0.0),
            name=d.get("name"),
            rotation=r,
            offset_x=ox,
            offset_y=oy,
        )


# ---------------------------------------------------------------------------
# CompositeProfile
# ---------------------------------------------------------------------------


class CompositeProfile(Profile):
    """
    Composition of multiple profiles into one compound section.

    IFC native: ``IfcCompositeProfileDef``.

    Each sub-profile contributes its own outline to get_profile_points()
    (the outlines are concatenated — correct for display/tessellation).
    For IFC the native IfcCompositeProfileDef is used so viewers handle
    the semantics correctly.

    Args:
        profiles:  List of Profile instances.
        label:     Optional label for the composite.
        name:      Optional profile name.
    """

    profile_type = "composite"

    def __init__(
        self,
        profiles: List[Profile],
        label: Optional[str] = None,
        name: Optional[str] = None,
    ) -> None:
        if len(profiles) < 2:
            raise ValueError("CompositeProfile requires at least 2 sub-profiles")
        self.profiles = list(profiles)
        self.label = label
        self.name = name
        super().__init__()
        # No transform on composite itself — each child carries its own

    def get_profile_points(self) -> List[Tuple[float, float]]:
        """Concatenate all child outlines (for tessellation / Path segments)."""
        pts: List[Tuple[float, float]] = []
        for p in self.profiles:
            pts.extend(p.get_profile_points())
        return pts

    @property
    def area(self) -> Optional[float]:
        areas = [p.area for p in self.profiles]
        if any(a is None for a in areas):
            return None
        return sum(areas)  # type: ignore[arg-type]

    def to_ifc(self, ifc_file: "ifcopenshell.file") -> "ifcopenshell.entity_instance":
        child_entities = [p.to_ifc(ifc_file) for p in self.profiles]
        return ifc_file.create_entity(
            "IfcCompositeProfileDef",
            ProfileType="AREA",
            ProfileName=self.name,
            Profiles=child_entities,
            Label=self.label,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_type": self.profile_type,
            "profiles": [p.to_dict() for p in self.profiles],
            "label": self.label,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CompositeProfile":
        children = [Profile.dispatch_from_dict(pd) for pd in d["profiles"]]
        return cls(profiles=children, label=d.get("label"), name=d.get("name"))
