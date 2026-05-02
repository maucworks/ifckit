"""
tests/test_add_drawing.py
=========================

Tests for IfcModel.add_drawing() — M1.
Drawings are section planes defined by origin, x_axis, z_axis (view direction).
"""
import pytest
import ifcopenshell
import ifcopenshell.util.element as ifc_util

from ifckit.model import IfcModel
from ifckit.schema import IfcSchema, LengthUnit


@pytest.fixture()
def model():
    return IfcModel(name="DrawingTest", schema=IfcSchema.IFC4, unit=LengthUnit.MILLIMETRE)


def test_add_drawing_creates_annotation(model):
    ann = model.add_drawing("Ground Floor Plan")
    assert ann is not None
    assert ann.is_a("IfcAnnotation")
    assert ann.Name == "Ground Floor Plan"
    assert ann.ObjectType == "DRAWING"


def test_add_drawing_object_type_is_drawing():
    """ObjectType='DRAWING' is the Bonsai convention, not PredefinedType."""
    m = IfcModel(name="Test", schema=IfcSchema.IFC4X3, unit=LengthUnit.MILLIMETRE)
    ann = m.add_drawing("Ground Floor Plan")
    assert ann.ObjectType == "DRAWING"
    # PredefinedType on IFC4X3 IfcAnnotation only accepts infrastructure enums,
    # not "DRAWING" — Bonsai uses ObjectType for this, so PredefinedType stays None.
    assert ann.PredefinedType is None


def test_add_drawing_placement(model):
    ann = model.add_drawing("Level 1", position=(0.0, 0.0, 4200.0))
    placement = ann.ObjectPlacement
    assert placement is not None
    assert placement.is_a("IfcLocalPlacement")
    rel = placement.RelativePlacement
    assert rel.is_a("IfcAxis2Placement3D")
    loc = rel.Location
    assert abs(loc.Coordinates[2] - 4200.0) < 1e-3


def test_add_drawing_placement_z_axis_default_down(model):
    """Default z_axis=(0,0,-1) — plan looking down.
    IFC placement Axis is negated (camera outward normal): (0,0,+1)."""
    ann = model.add_drawing("Plan", position=(0.0, 0.0, 1200.0))
    rel = ann.ObjectPlacement.RelativePlacement
    axis = rel.Axis
    assert axis is not None
    assert abs(axis.DirectionRatios[0]) < 1e-9
    assert abs(axis.DirectionRatios[1]) < 1e-9
    assert abs(axis.DirectionRatios[2] - 1.0) < 1e-9   # negated: +1


def test_add_drawing_explicit_z_axis_section(model):
    """Section facing north: z_axis=(0,-1,0) → IFC Axis=(0,+1,0)."""
    ann = model.add_drawing(
        "Section A-A",
        target_view="SECTION_VIEW",
        position=(0.0, 5000.0, 0.0),
        z_axis=(0.0, -1.0, 0.0),
        x_axis=(1.0, 0.0, 0.0),
    )
    rel = ann.ObjectPlacement.RelativePlacement
    axis = rel.Axis
    assert abs(axis.DirectionRatios[0]) < 1e-9
    assert abs(axis.DirectionRatios[1] - 1.0) < 1e-9   # negated: +1
    assert abs(axis.DirectionRatios[2]) < 1e-9


def test_add_drawing_explicit_x_axis(model):
    """Custom x_axis is stored in RefDirection."""
    ann = model.add_drawing(
        "Section B-B",
        position=(3000.0, 0.0, 0.0),
        z_axis=(-1.0, 0.0, 0.0),
        x_axis=(0.0, 1.0, 0.0),
    )
    rel = ann.ObjectPlacement.RelativePlacement
    ref = rel.RefDirection
    assert ref is not None
    assert abs(ref.DirectionRatios[0]) < 1e-9
    assert abs(ref.DirectionRatios[1] - 1.0) < 1e-9
    assert abs(ref.DirectionRatios[2]) < 1e-9


def test_add_drawing_epset_drawing(model):
    ann = model.add_drawing("Ground Floor Plan", target_view="PLAN_VIEW")
    psets = ifc_util.get_psets(ann)
    assert "EPset_Drawing" in psets, f"EPset_Drawing not found in {list(psets.keys())}"
    epset = psets["EPset_Drawing"]
    assert epset["TargetView"] == "PLAN_VIEW"
    assert epset["HasLinework"] is True
    assert epset["HasUnderlay"] is False
    assert epset["Scale"] == "1/100"
    assert epset["HumanScale"] == "1:100"


def test_add_drawing_group_created(model):
    model.add_drawing("Ground Floor Plan")
    groups = model.ifc_file.by_type("IfcGroup")
    drawing_groups = [g for g in groups if g.ObjectType == "DRAWING"]
    assert len(drawing_groups) == 1
    assert drawing_groups[0].Name == "Ground Floor Plan"


def test_add_drawing_annotation_in_group(model):
    ann = model.add_drawing("Ground Floor Plan")
    groups = [
        rel.RelatingGroup
        for rel in model.ifc_file.by_type("IfcRelAssignsToGroup")
        if ann in rel.RelatedObjects
    ]
    assert len(groups) == 1
    assert groups[0].ObjectType == "DRAWING"
    assert groups[0].Name == "Ground Floor Plan"


def test_add_multiple_drawings(model):
    ann1 = model.add_drawing("Ground Floor Plan", position=(0.0, 0.0, 1200.0))
    ann2 = model.add_drawing("Level 1 Plan", position=(0.0, 0.0, 4200.0))
    annotations = model.ifc_file.by_type("IfcAnnotation")
    drawing_anns = [a for a in annotations if a.ObjectType == "DRAWING"]
    assert len(drawing_anns) == 2
    groups = [g for g in model.ifc_file.by_type("IfcGroup") if g.ObjectType == "DRAWING"]
    assert len(groups) == 2


def test_add_drawing_ifc2x3(model):
    """IFC2X3 has no PredefinedType on IfcAnnotation — should not raise."""
    m = IfcModel(name="Test", schema=IfcSchema.IFC2X3, unit=LengthUnit.MILLIMETRE)
    ann = m.add_drawing("Ground Floor Plan")
    assert ann.is_a("IfcAnnotation")
    assert ann.ObjectType == "DRAWING"


def test_add_drawing_has_representation(model):
    """Annotation must have an IfcCsgSolid (Bonsai convention) so the SVG
    serializer can match it via GUID and extract the section plane."""
    ann = model.add_drawing("Plan")
    assert ann.Representation is not None
    reps = ann.Representation.Representations
    assert len(reps) == 1
    items = list(reps[0].Items)
    assert any(i.is_a("IfcCsgSolid") for i in items)


def test_add_drawing_representation_box_dimensions(model):
    """Camera box: 50 m × 50 m × 10 m (Bonsai default), centred on origin."""
    ann = model.add_drawing("Plan")
    csg = next(i for i in ann.Representation.Representations[0].Items
               if i.is_a("IfcCsgSolid"))
    block = csg.TreeRootExpression
    assert block.is_a("IfcBlock")
    assert abs(block.XLength - 50000.0) < 1e-3
    assert abs(block.YLength - 50000.0) < 1e-3
    assert abs(block.ZLength - 10000.0) < 1e-3
    loc = block.Position.Location.Coordinates
    assert abs(loc[0] - (-25000.0)) < 1e-3
    assert abs(loc[1] - (-25000.0)) < 1e-3
    assert abs(loc[2] - (-10000.0)) < 1e-3
