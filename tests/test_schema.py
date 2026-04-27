"""Tests for ifckit.schema"""
import pytest
from ifckit.schema import IfcSchema, LengthUnit, get_schema_name, unit_scale_to_metres


class TestIfcSchema:
    def test_values(self):
        assert IfcSchema.IFC4.value == "IFC4"
        assert IfcSchema.IFC4X3.value == "IFC4X3"

    def test_get_schema_name_ifc4(self):
        assert get_schema_name(IfcSchema.IFC4) == "IFC4"

    def test_get_schema_name_ifc4x3(self):
        assert get_schema_name(IfcSchema.IFC4X3) == "IFC4X3"


class TestLengthUnit:
    def test_metre_scale(self):
        assert unit_scale_to_metres(LengthUnit.METRE) == pytest.approx(1.0)

    def test_millimetre_scale(self):
        assert unit_scale_to_metres(LengthUnit.MILLIMETRE) == pytest.approx(0.001)

    def test_foot_scale(self):
        assert unit_scale_to_metres(LengthUnit.FOOT) == pytest.approx(0.3048)

    def test_inch_scale(self):
        assert unit_scale_to_metres(LengthUnit.INCH) == pytest.approx(0.0254)

    def test_all_units_covered(self):
        for unit in LengthUnit:
            val = unit_scale_to_metres(unit)
            assert val > 0
