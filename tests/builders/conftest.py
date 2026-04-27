"""Shared fixtures for builder tests."""
import pytest
import ifcopenshell
import ifcopenshell.api

from ifckit.model import IfcModel
from ifckit.schema import IfcSchema


@pytest.fixture
def ifc4_model():
    return IfcModel(name="BuilderTest", schema=IfcSchema.IFC4, author="pytest")


@pytest.fixture
def ifc4x3_model():
    return IfcModel(name="BridgeBuilderTest", schema=IfcSchema.IFC4X3, author="pytest")


@pytest.fixture
def ifc4_storey(ifc4_model):
    site = ifc4_model.add_site("S")
    building = ifc4_model.add_building(site, "B")
    return ifc4_model.add_storey(building, "L0")


@pytest.fixture
def body_context(ifc4_model):
    from ifckit.builders._geom import get_body_context
    return get_body_context(ifc4_model.ifc_file)
