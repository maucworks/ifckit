"""
ifckit.schema.ifc_classes
========================

Single source of truth for IFC entity class-name strings used across
the codebase.  Centralises the raw schema names so that version
migrations or schema changes touch one file instead of dozens.

Used as::

    from ifckit.schema.ifc_classes import IFC

    entity = ifc_file.create_entity(IFC.IfcWall, name="My Wall")
"""

from __future__ import annotations


class IFC:
    """IFC entity class-name constants."""

    # ── Geometry ──────────────────────────────────────────────────
    IfcCartesianPoint: str = "IfcCartesianPoint"
    IfcDirection: str = "IfcDirection"
    IfcPolyline: str = "IfcPolyline"
    IfcCircle: str = "IfcCircle"
    IfcTrimmedCurve: str = "IfcTrimmedCurve"
    IfcCompositeCurve: str = "IfcCompositeCurve"
    IfcCompositeCurveSegment: str = "IfcCompositeCurveSegment"
    IfcParameterValue: str = "IfcParameterValue"

    # ── Profile definitions ───────────────────────────────────────
    IfcIShapeProfileDef: str = "IfcIShapeProfileDef"
    IfcLShapeProfileDef: str = "IfcLShapeProfileDef"
    IfcTShapeProfileDef: str = "IfcTShapeProfileDef"
    IfcZShapeProfileDef: str = "IfcZShapeProfileDef"
    IfcCShapeProfileDef: str = "IfcCShapeProfileDef"
    IfcTrapeziumProfileDef: str = "IfcTrapeziumProfileDef"
    IfcCompositeProfileDef: str = "IfcCompositeProfileDef"
    IfcRectangleProfileDef: str = "IfcRectangleProfileDef"
    IfcCircleProfileDef: str = "IfcCircleProfileDef"
    IfcCircleHollowProfileDef: str = "IfcCircleHollowProfileDef"
    IfcDerivedProfileDef: str = "IfcDerivedProfileDef"

    # ── Placement & Shape ─────────────────────────────────────────
    IfcAxis2Placement3D: str = "IfcAxis2Placement3D"
    IfcAxis2Placement2D: str = "IfcAxis2Placement2D"
    IfcLocalPlacement: str = "IfcLocalPlacement"
    IfcExtrudedAreaSolid: str = "IfcExtrudedAreaSolid"
    IfcShapeRepresentation: str = "IfcShapeRepresentation"
    IfcProductDefinitionShape: str = "IfcProductDefinitionShape"
    IfcBooleanClippingResult: str = "IfcBooleanClippingResult"
    IfcMappedItem: str = "IfcMappedItem"
    IfcRepresentationMap: str = "IfcRepresentationMap"

    # ── Building elements ─────────────────────────────────────────
    IfcProject: str = "IfcProject"
    IfcSite: str = "IfcSite"
    IfcBuilding: str = "IfcBuilding"
    IfcBuildingStorey: str = "IfcBuildingStorey"
    IfcWall: str = "IfcWall"
    IfcWallStandardCase: str = "IfcWallStandardCase"
    IfcSlab: str = "IfcSlab"
    IfcBeam: str = "IfcBeam"
    IfcColumn: str = "IfcColumn"
    IfcDoor: str = "IfcDoor"
    IfcWindow: str = "IfcWindow"
    IfcSpace: str = "IfcSpace"
    IfcOpeningElement: str = "IfcOpeningElement"
    IfcRoof: str = "IfcRoof"
    IfcPlate: str = "IfcPlate"

    # ── Relationships ─────────────────────────────────────────────
    IfcRelContainedInSpatialStructure: str = "IfcRelContainedInSpatialStructure"
    IfcRelAggregates: str = "IfcRelAggregates"
    IfcRelVoidsElement: str = "IfcRelVoidsElement"
    IfcRelFillsElement: str = "IfcRelFillsElement"
    IfcRelDefinesByProperties: str = "IfcRelDefinesByProperties"
    IfcRelDefinesByType: str = "IfcRelDefinesByType"

    # ── Contexts ──────────────────────────────────────────────────
    IfcGeometricRepresentationContext: str = "IfcGeometricRepresentationContext"
    IfcGeometricRepresentationSubContext: str = "IfcGeometricRepresentationSubContext"

    # ── Style ─────────────────────────────────────────────────────
    IfcStyledItem: str = "IfcStyledItem"
    IfcSurfaceStyle: str = "IfcSurfaceStyle"
    IfcSurfaceStyleRendering: str = "IfcSurfaceStyleRendering"
    IfcSurfaceStyleShading: str = "IfcSurfaceStyleShading"
    IfcPresentationStyleAssignment: str = "IfcPresentationStyleAssignment"

    # ── Curve types ────────────────────────────────────────────────
    IfcBSplineCurveWithKnots: str = "IfcBSplineCurveWithKnots"
    IfcRationalBSplineCurveWithKnots: str = "IfcRationalBSplineCurveWithKnots"
    IfcBSplineSurfaceWithKnots: str = "IfcBSplineSurfaceWithKnots"
    IfcRationalBSplineSurfaceWithKnots: str = "IfcRationalBSplineSurfaceWithKnots"

    # ── Tessellation ───────────────────────────────────────────────
    IfcCartesianPointList3D: str = "IfcCartesianPointList3D"
    IfcTriangulatedFaceSet: str = "IfcTriangulatedFaceSet"

    # ── Door/Window types (IFC2X3) ────────────────────────────────
    IfcDoorStyle: str = "IfcDoorStyle"
    IfcWindowStyle: str = "IfcWindowStyle"

    # ── Door/Window types (IFC4+) ─────────────────────────────────
    IfcDoorType: str = "IfcDoorType"
    IfcWindowType: str = "IfcWindowType"

    # ── Property sets ─────────────────────────────────────────────
    IfcPropertySet: str = "IfcPropertySet"
    IfcPropertySingleValue: str = "IfcPropertySingleValue"
    IfcPropertyEnumeratedValue: str = "IfcPropertyEnumeratedValue"
    IfcPropertyBoundedValue: str = "IfcPropertyBoundedValue"
