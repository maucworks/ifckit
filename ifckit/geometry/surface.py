"""
ifckit.geometry.surface
=======================

Surface — a NURBS / BSpline surface with IFC serialisation and optional
OCC (``pythonocc-core``) evaluation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence

from ifckit.geometry.primitives import Vec

if TYPE_CHECKING:
    import ifcopenshell

    from ifckit.geometry.curve import Curve  # noqa: F401
    from ifckit.geometry.primitives import Plane  # noqa: F401
    from ifckit.schema import TessellationDetail  # noqa: F401

# ---------------------------------------------------------------------------
# Optional OCC detection
# ---------------------------------------------------------------------------

_HAS_OCC = False
try:
    from OCC.Core.Geom import Geom_BSplineSurface
    from OCC.Core.gp import gp_Dir, gp_Pln, gp_Pnt
    from OCC.Core.TColgp import TColgp_Array2OfPnt
    from OCC.Core.TColStd import (
        TColStd_Array1OfInteger,
        TColStd_Array1OfReal,
        TColStd_Array2OfReal,
    )

    _HAS_OCC = True
except ImportError:
    pass


def require_occ():
    if not _HAS_OCC:
        raise ImportError("pythonocc-core is required. Install with: pip install pythonocc-core")


# ---------------------------------------------------------------------------
# Surface
# ---------------------------------------------------------------------------


class Surface:
    """A NURBS / BSpline surface (tensor product).

    Data + IFC serialisation in pure Python.  Evaluation and
    surface‑plane intersection require ``pythonocc-core`` (optional).
    """

    def __init__(
        self,
        control_points: Sequence[Sequence[Vec]],
        uknots: Sequence[float],
        vknots: Sequence[float],
        umults: Sequence[int],
        vmults: Sequence[int],
        udegree: int,
        vdegree: int,
        weights: Optional[Sequence[Sequence[float]]] = None,
        uclosed: bool = False,
        vclosed: bool = False,
    ) -> None:
        self.control_points = [
            [Vec(*p) if not isinstance(p, Vec) else p for p in row] for row in control_points
        ]
        self.uknots = [float(k) for k in uknots]
        self.vknots = [float(k) for k in vknots]
        self.umults = [int(m) for m in umults]
        self.vmults = [int(m) for m in vmults]
        self.udegree = udegree
        self.vdegree = vdegree
        self._weights = [list(w) for w in weights] if weights is not None else None
        self.uclosed = uclosed
        self.vclosed = vclosed

    # ── properties ──────────────────────────────────────────────────

    @property
    def rational(self) -> bool:
        return self._weights is not None

    @property
    def nu(self) -> int:
        return len(self.control_points)

    @property
    def nv(self) -> int:
        return len(self.control_points[0]) if self.control_points else 0

    # ── evaluation (via OCC) ───────────────────────────────────────

    def point_at(self, u: float, v: float) -> Vec:
        """Evaluate surface point at ``(u, v)`` — both in ``[0, 1]``.

        Requires ``pythonocc-core``.
        """
        from ifckit.geometry.surface import occ_eval_point

        return occ_eval_point(self, u, v)

    def to_mesh_dict(
        self,
        nu: int = 20,
        nv: int = 20,
        label: str = "",
        material: "dict | None" = None,
        deflection: "float | object" = 0.01,
    ) -> dict:
        """Triangulate the surface via OCC and return a dict for 3D viewer.

        Uses OCC ``BRepMesh_IncrementalMesh`` (requires ``pythonocc-core``).

        Args:
            nu:         Ignored (OCC adaptive mesh).
            nv:         Ignored (OCC adaptive mesh).
            label:      Display name.
            material:   Visual properties (color, opacity, …).
            deflection: Mesh deflection / ``TessellationDetail``.

        Returns:
            A dict with ``primitive="triangles"``, ``positions``,
            ``indices``, and optional ``label``, ``material``.
        """
        from ifckit.geometry.surface import occ_tessellate, require_occ

        require_occ()
        verts, tris = occ_tessellate(self, deflection)
        positions = [c for v in verts for c in v]
        indices = [i - 1 for tri in tris for i in tri]

        d: dict = {
            "primitive": "triangles",
            "positions": positions,
            "indices": indices,
            "label": label or "Surface",
        }
        if material is not None:
            d["material"] = material
        return d

    # ── IFC serialisation ──────────────────────────────────────────

    def _to_ifc_pt(self, ifc_file, v: Vec):
        return ifc_file.create_entity("IfcCartesianPoint", Coordinates=(v.x, v.y, v.z))

    def _ifc_points(self, ifc_file) -> List[List]:
        return [[self._to_ifc_pt(ifc_file, p) for p in row] for row in self.control_points]

    def _set_common(self, e, ifc_file) -> None:
        e.UDegree = self.udegree
        e.VDegree = self.vdegree
        e.ControlPointsList = self._ifc_points(ifc_file)
        e.SurfaceForm = "UNSPECIFIED"
        e.UClosed = self.uclosed
        e.VClosed = self.vclosed
        e.SelfIntersect = False
        e.UMultiplicities = self.umults
        e.VMultiplicities = self.vmults
        e.UKnots = self.uknots
        e.VKnots = self.vknots
        e.KnotSpec = "UNSPECIFIED"

    def to_ifc_bspline(self, ifc_file) -> "ifcopenshell.entity_instance":
        if self.rational:
            raise ValueError("Use to_ifc_rational() for rational surfaces")
        e = ifc_file.create_entity("IfcBSplineSurfaceWithKnots")
        self._set_common(e, ifc_file)
        return e

    def to_ifc_rational(self, ifc_file) -> "ifcopenshell.entity_instance":
        if not self.rational:
            raise ValueError("Use to_ifc_bspline() for non‑rational surfaces")
        e = ifc_file.create_entity("IfcRationalBSplineSurfaceWithKnots")
        self._set_common(e, ifc_file)
        e.WeightsData = self._weights
        return e

    # ── dict serialisation ─────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "udegree": self.udegree,
            "vdegree": self.vdegree,
            "control_points": [[v.to_dict() for v in row] for row in self.control_points],
            "uknots": self.uknots,
            "vknots": self.vknots,
            "umults": self.umults,
            "vmults": self.vmults,
            "uclosed": self.uclosed,
            "vclosed": self.vclosed,
        }
        if self._weights is not None:
            d["weights"] = self._weights
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Surface":
        return cls(
            control_points=[[Vec.from_dict(v) for v in row] for row in d["control_points"]],
            uknots=d["uknots"],
            vknots=d["vknots"],
            umults=d["umults"],
            vmults=d["vmults"],
            udegree=d["udegree"],
            vdegree=d["vdegree"],
            weights=d.get("weights"),
            uclosed=d.get("uclosed", False),
            vclosed=d.get("vclosed", False),
        )

    def __repr__(self) -> str:
        w_str = ", rational" if self.rational else ""
        return f"Surface({self.nu}×{self.nv} pts, U{self.udegree}/V{self.vdegree}{w_str})"

    # ── OCC bridge ─────────────────────────────────────────────────

    @classmethod
    def from_occ_surface(cls, occ_surface) -> "Surface":
        require_occ()
        udeg = occ_surface.UDegree()
        vdeg = occ_surface.VDegree()
        nu = occ_surface.NbUPoles()
        nv = occ_surface.NbVPoles()

        poles = []
        for i in range(nu):
            row = []
            for j in range(nv):
                p = occ_surface.Pole(i + 1, j + 1)
                row.append(Vec(p.X(), p.Y(), p.Z()))
            poles.append(row)

        uknots = [occ_surface.UKnot(i + 1) for i in range(occ_surface.NbUKnots())]
        vknots = [occ_surface.VKnot(i + 1) for i in range(occ_surface.NbVKnots())]
        umults = [occ_surface.UMultiplicity(i + 1) for i in range(occ_surface.NbUKnots())]
        vmults = [occ_surface.VMultiplicity(i + 1) for i in range(occ_surface.NbVKnots())]

        rational = occ_surface.IsURational() or occ_surface.IsVRational()
        weights = None
        if rational:
            weights = [[occ_surface.Weight(i + 1, j + 1) for j in range(nv)] for i in range(nu)]

        return cls(
            control_points=poles,
            uknots=uknots,
            vknots=vknots,
            umults=umults,
            vmults=vmults,
            udegree=udeg,
            vdegree=vdeg,
            weights=weights,
            uclosed=occ_surface.IsUPeriodic(),
            vclosed=occ_surface.IsVPeriodic(),
        )

    # ── loft & fill ────────────────────────────────────────────────

    @classmethod
    def loft(cls, curves: "Sequence[Curve]", degree: int = 3) -> "Surface":
        """Create a surface through a series of curves (loft).

        Args:
            curves:  Cross‑section curves (ordered).
            degree:  Target degree in the loft direction.

        Returns:
            A new Surface.
        """
        require_occ()
        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeWire
        from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_ThruSections
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopExp import TopExp_Explorer

        lofter = BRepOffsetAPI_ThruSections(False)
        for cv in curves:
            edge = _build_occ_edge(cv)
            wire = BRepBuilderAPI_MakeWire(edge).Wire()
            lofter.AddWire(wire)
        lofter.Build()

        exp = TopExp_Explorer(lofter.Shape(), TopAbs_FACE)
        if not exp.More():
            raise RuntimeError("Loft produced no faces")
        face = exp.Current()
        adaptor = BRepAdaptor_Surface(face)
        geom = adaptor.Surface().Surface()
        bspline = Geom_BSplineSurface.DownCast(geom)
        if bspline is None:
            raise RuntimeError("Loft result is not a BSpline surface")

        return cls.from_occ_surface(bspline)

    @classmethod
    def fill(cls, curves, degree=3, n_samples=10, constraints=None, supports=None):
        """Create a surface bounded by 3‑4 curves (Coons‑like fill).

        By default the interior is estimated via bilinear Coons blending
        from the boundary curves, then a BSpline surface is fit through
        the resulting point grid.  When *constraints* are specified the
        OCC ``BRepOffsetAPI_MakeFilling`` algorithm is used instead,
        which supports per‑edge **G1** (tangent) continuity against
        optional support surfaces.

        Args:
            curves:      Boundary curves (3 or 4).
            degree:      Target degree.
            n_samples:   Number of subdivisions (Coons fallback only).
            constraints: Per‑edge continuity ``["C0", "G1", …]``.
                         ``None`` → Coons blending (no tangents).
            supports:    Per‑edge support ``Surface`` for G1 edges
                         (``None`` = no support). Ignored for C0 edges.

        Returns:
            A new Surface.
        """
        n = len(curves)
        if n not in (3, 4):
            raise ValueError("fill() requires 3 or 4 boundary curves")

        # ── Backward‑compatible Coons path ──────────────────────────
        if constraints is None:
            require_occ()
            from OCC.Core.GeomAbs import GeomAbs_C2
            from OCC.Core.GeomAPI import GeomAPI_PointsToBSplineSurface
            from OCC.Core.gp import gp_Pnt
            from OCC.Core.TColgp import TColgp_Array2OfPnt

            ns = n_samples
            c0, c1, c2 = curves[0], curves[1], curves[2]
            c3 = curves[3] if n == 4 else None

            grid = TColgp_Array2OfPnt(1, ns + 1, 1, ns + 1)
            for i in range(ns + 1):
                u = i / ns
                for j in range(ns + 1):
                    v = j / ns
                    pu = c0.point_at(v) * (1.0 - u) + c2.point_at(v) * u
                    pv = c1.point_at(u) * (1.0 - v) + (c3 or c1).point_at(u) * v
                    corners = (
                        c0.point_at(0) * (1.0 - u) * (1.0 - v)
                        + c0.point_at(1) * (1.0 - u) * v
                        + c2.point_at(0) * u * (1.0 - v)
                        + c2.point_at(1) * u * v
                    )
                    p = pu + pv - corners
                    grid.SetValue(i + 1, j + 1, gp_Pnt(p.x, p.y, p.z))

            dg = degree
            if dg > ns:
                dg = ns
            occ_surf = GeomAPI_PointsToBSplineSurface(
                grid,
                3,
                max(3, dg + 2),
                GeomAbs_C2,
                1e-3,
            )
            return cls.from_occ_surface(occ_surf.Surface())

        # ── BRepOffsetAPI_MakeFilling path (supports G1) ───────────
        require_occ()
        import warnings as _w

        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        from OCC.Core.BRepOffsetAPI import BRepOffsetAPI_MakeFilling
        from OCC.Core.GeomAbs import GeomAbs_C0, GeomAbs_G1
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Core.TopExp import TopExp_Explorer

        # Default constraint = C0
        _CONST_MAP = {"C0": GeomAbs_C0, "G1": GeomAbs_G1}
        full_constraints = [
            _CONST_MAP.get(c.upper(), GeomAbs_C0) if c else GeomAbs_C0
            for c in (constraints or ["C0"] * n)
        ]
        # Pad if shorter than curves
        while len(full_constraints) < n:
            full_constraints.append(GeomAbs_C0)

        filler = BRepOffsetAPI_MakeFilling()
        filler.SetConstrParam(1e-3, 1e-3, 0.1, 0.1)

        for i, curve in enumerate(curves):
            edge = _build_occ_edge(curve)
            gc = full_constraints[i]
            supp = supports[i] if supports and i < len(supports) else None
            if supp is not None:
                occ_face = _build_occ_face(supp)
                filler.Add(edge, occ_face, gc)
            else:
                filler.Add(edge, gc)

        try:
            filler.Build()
        except RuntimeError:
            _w.warn(
                "Surface.fill() with constraints failed — falling back to C0 Coons blending.",
                stacklevel=3,
            )
            return cls.fill(curves, degree=degree, n_samples=n_samples)

        if not filler.IsDone():
            _w.warn(
                "Surface.fill() MakeFilling returned IsDone=False — "
                "falling back to C0 Coons blending.",
                stacklevel=3,
            )
            return cls.fill(curves, degree=degree, n_samples=n_samples)

        exp = TopExp_Explorer(filler.Shape(), TopAbs_FACE)
        if not exp.More():
            raise RuntimeError("MakeFilling produced no face")
        face = exp.Current()
        adaptor = BRepAdaptor_Surface(face)
        geom = adaptor.Surface().Surface()
        from OCC.Core.Geom import Geom_BSplineSurface

        bspline = Geom_BSplineSurface.DownCast(geom)
        if bspline is None:
            raise RuntimeError("MakeFilling result is not a BSpline surface")

        return cls.from_occ_surface(bspline)


def _build_occ_edge(curve: "Curve") -> object:
    """Build an OCC ``TopoDS_Edge`` from an ifckit *Curve*."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
    from OCC.Core.Geom import Geom_BSplineCurve
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.TColgp import TColgp_Array1OfPnt
    from OCC.Core.TColStd import TColStd_Array1OfInteger, TColStd_Array1OfReal

    n = len(curve.points)
    poles = TColgp_Array1OfPnt(1, n)
    for i, p in enumerate(curve.points):
        poles.SetValue(i + 1, gp_Pnt(p.x, p.y, p.z))

    ukn = TColStd_Array1OfReal(1, len(curve.knots))
    for i, k in enumerate(curve.knots):
        ukn.SetValue(i + 1, k)
    mul = TColStd_Array1OfInteger(1, len(curve.multiplicities))
    for i, m in enumerate(curve.multiplicities):
        mul.SetValue(i + 1, m)

    if curve.rational:
        wgt = TColStd_Array1OfReal(1, n)
        for i, w in enumerate(curve._weights):
            wgt.SetValue(i + 1, w)
        geom = Geom_BSplineCurve(poles, wgt, ukn, mul, curve.degree, curve.closed)
    else:
        geom = Geom_BSplineCurve(poles, ukn, mul, curve.degree, curve.closed)

    return BRepBuilderAPI_MakeEdge(geom, 0.0, 1.0).Edge()


# ---------------------------------------------------------------------------
# OCC evaluation helpers
# ---------------------------------------------------------------------------


def _build_occ_surface(surf: Surface):
    """Rebuild an OCC ``Geom_BSplineSurface`` from an ifckit Surface."""
    from OCC.Core.gp import gp_Pnt

    nu, nv = surf.nu, surf.nv
    poles = TColgp_Array2OfPnt(1, nu, 1, nv)
    for i in range(nu):
        for j in range(nv):
            p = surf.control_points[i][j]
            poles.SetValue(i + 1, j + 1, gp_Pnt(p.x, p.y, p.z))

    ukn = TColStd_Array1OfReal(1, len(surf.uknots))
    for i, k in enumerate(surf.uknots):
        ukn.SetValue(i + 1, k)
    vkn = TColStd_Array1OfReal(1, len(surf.vknots))
    for i, k in enumerate(surf.vknots):
        vkn.SetValue(i + 1, k)

    um = TColStd_Array1OfInteger(1, len(surf.umults))
    for i, m in enumerate(surf.umults):
        um.SetValue(i + 1, m)
    vm = TColStd_Array1OfInteger(1, len(surf.vmults))
    for i, m in enumerate(surf.vmults):
        vm.SetValue(i + 1, m)

    if surf.rational:
        wgt = TColStd_Array2OfReal(1, nu, 1, nv)
        for i in range(nu):
            for j in range(nv):
                wgt.SetValue(i + 1, j + 1, surf._weights[i][j])
        args = (
            poles,
            wgt,
            ukn,
            vkn,
            um,
            vm,
            surf.udegree,
            surf.vdegree,
            surf.uclosed,
            surf.vclosed,
        )
        return Geom_BSplineSurface(*args)

    args = (poles, ukn, vkn, um, vm, surf.udegree, surf.vdegree, surf.uclosed, surf.vclosed)
    return Geom_BSplineSurface(*args)


def occ_eval_point(surf: Surface, u: float, v: float) -> Vec:
    """Evaluate surface point at ``(u, v)`` — both in ``[0, 1]``."""
    require_occ()
    pt = _build_occ_surface(surf).Value(u, v)
    return Vec(pt.X(), pt.Y(), pt.Z())


def occ_eval_tangents(surf: Surface, u: float, v: float) -> "tuple[Vec, Vec]":
    require_occ()
    occ = _build_occ_surface(surf)
    _, d1u, d1v = occ.D1(u, v)
    return Vec(d1u.X(), d1u.Y(), d1u.Z()), Vec(d1v.X(), d1v.Y(), d1v.Z())


def occ_intersect_plane(surf: Surface, plane: "Plane") -> List["Curve"]:
    """Intersect a surface with a plane → list of ``Curve``.

    Uses OCC ``BRepAlgoAPI_Section``.  Requires ``pythonocc-core``.
    """
    require_occ()
    from OCC.Core.BRepAdaptor import BRepAdaptor_Curve
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Section
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCC.Core.GeomAbs import GeomAbs_BSplineCurve

    from ifckit.geometry.curve import Curve as _Curve

    occ_surf = _build_occ_surface(surf)
    face = BRepBuilderAPI_MakeFace(occ_surf, 1e-6).Face()

    pl = plane
    occ_plane = gp_Pln(
        gp_Pnt(pl.origin.x, pl.origin.y, pl.origin.z), gp_Dir(pl.z_axis.x, pl.z_axis.y, pl.z_axis.z)
    )

    section = BRepAlgoAPI_Section(face, occ_plane)
    section.Build()
    shape = section.Shape()

    from OCC.Core.TopAbs import TopAbs_EDGE
    from OCC.Core.TopExp import TopExp_Explorer

    result: List = []
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    while exp.More():
        edge = exp.Current()
        adaptor = BRepAdaptor_Curve(edge)
        if adaptor.GetType() == GeomAbs_BSplineCurve:
            result.append(_Curve.from_occ_edge(edge))
        exp.Next()
    return result


# ---------------------------------------------------------------------------
# Tessellation
# ---------------------------------------------------------------------------


def _build_occ_face(surf: Surface) -> object:
    """Build an OCC ``TopoDS_Face`` from an ifckit Surface."""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace

    return BRepBuilderAPI_MakeFace(_build_occ_surface(surf), 1e-6).Face()


def occ_tessellate(
    surf: Surface, deflection: float | TessellationDetail = 0.01
) -> "tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]":
    """Triangulate a surface → ``(vertices, triangles)``.

    *vertices* is a list of ``(x, y, z)`` tuples.
    *triangles* is a list of 1‑based index triples for
    ``IfcTriangulatedFaceSet.CoordIndex``.

    Requires ``pythonocc-core``.
    """
    require_occ()
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.TopAbs import TopAbs_FACE
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopLoc import TopLoc_Location

    # Accept TessellationDetail as deflection shorthand
    try:
        from ifckit.schema import TessellationDetail as _TD

        _TESS_DETAIL_MAP = {
            _TD.COARSE: 0.05,
            _TD.MEDIUM: 0.02,
            _TD.FINE: 0.01,
            _TD.ULTRA: 0.005,
        }
        if isinstance(deflection, _TD):
            deflection = _TESS_DETAIL_MAP[deflection]
    except ImportError:
        pass

    deflection = float(deflection)

    face = _build_occ_face(surf)
    mesh = BRepMesh_IncrementalMesh(face, deflection)
    mesh.Perform()

    vertices: "list[tuple[float, float, float]]" = []
    triangles: "list[tuple[int, int, int]]" = []
    offset = 0

    exp = TopExp_Explorer(face, TopAbs_FACE)
    while exp.More():
        f = exp.Current()
        loc = TopLoc_Location()
        T = BRep_Tool.Triangulation(f, loc)
        if T is not None:
            nb_nodes = T.NbNodes()
            for i in range(1, nb_nodes + 1):
                p = T.Node(i)
                vertices.append((p.X(), p.Y(), p.Z()))

            nb_tri = T.NbTriangles()
            for i in range(1, nb_tri + 1):
                t = T.Triangle(i)
                i1, i2, i3 = t.Get()
                triangles.append((offset + i1, offset + i2, offset + i3))

            offset += nb_nodes

        exp.Next()

    return vertices, triangles


def occ_tessellate_to_ifc(
    surf: Surface,
    ifc_file: "ifcopenshell.file",
    deflection: "float | object" = 0.01,
) -> "ifcopenshell.entity_instance":
    """Triangulate a surface and wrap in ``IfcTriangulatedFaceSet``.

    Accepts the same *deflection* options as :func:`occ_tessellate`
    (float or ``TessellationDetail``).

    Requires ``pythonocc-core``.
    """
    verts, tris = occ_tessellate(surf, deflection)
    coord_list = ifc_file.create_entity("IfcCartesianPointList3D", CoordList=verts)
    return ifc_file.create_entity(
        "IfcTriangulatedFaceSet",
        Coordinates=coord_list,
        CoordIndex=tris,
    )
