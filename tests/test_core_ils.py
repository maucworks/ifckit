# This file was generated with the assistance of an AI coding tool.
"""Tests voor core ILS-mechanismen: psets, classificatie, zones, georef, quantities."""

import ifcopenshell.api

from ifckit.builders.classification import add_classification, assign_classification
from ifckit.builders.georeference import set_georeference
from ifckit.builders.psets import write_named_pset
from ifckit.builders.quantities import write_quantities
from ifckit.builders.zones import add_zone, group_spaces_by_property
from ifckit.model import IfcModel


def test_write_named_pset():
    m = IfcModel()
    site = m.add_site("S")
    b = m.add_building(site, "B")
    storey = m.add_storey(b, "BG", elevation=0)
    space = ifcopenshell.api.run("root.create_entity", m._file, ifc_class="IfcSpace", name="R")
    ifcopenshell.api.run("aggregate.assign_object", m._file, relating_object=storey.entity, products=[space])
    write_named_pset(m._file, space, "MiniBIM ILS", {"RuimteType": "Slaapkamer", "Goed": 1})
    pset = [p for p in m._file.by_type("IfcPropertySet") if p.Name == "MiniBIM ILS"][0]
    assert {p.Name for p in pset.HasProperties} == {"RuimteType", "Goed"}


def test_classification():
    m = IfcModel()
    site = m.add_site("S")
    b = m.add_building(site, "B")
    storey = m.add_storey(b, "BG", elevation=0)
    space = ifcopenshell.api.run("root.create_entity", m._file, ifc_class="IfcSpace", name="R")
    ifcopenshell.api.run("aggregate.assign_object", m._file, relating_object=storey.entity, products=[space])
    cls = add_classification(m._file, "NL-SfB", edition="2019")
    ref = assign_classification(m._file, [space], cls, "21.12", "spouwwanden")
    assert cls.Name == "NL-SfB"
    assert ref.Name == "spouwwanden"


def test_zones():
    m = IfcModel()
    site = m.add_site("S")
    b = m.add_building(site, "B")
    storey = m.add_storey(b, "BG", elevation=0)
    s1 = ifcopenshell.api.run("root.create_entity", m._file, ifc_class="IfcSpace", name="S1")
    s2 = ifcopenshell.api.run("root.create_entity", m._file, ifc_class="IfcSpace", name="S2")
    ifcopenshell.api.run("aggregate.assign_object", m._file, relating_object=storey.entity, products=[s1, s2])
    zone = add_zone(m._file, "Unit 1", [s1, s2])
    assert zone.Name == "Unit 1"
    rel = [r for r in m._file.by_type("IfcRelAssignsToGroup") if r.RelatingGroup == zone][0]
    assert len(rel.RelatedObjects) == 2


def test_group_by_property():
    m = IfcModel()
    site = m.add_site("S")
    b = m.add_building(site, "B")
    storey = m.add_storey(b, "BG", elevation=0)
    s1 = ifcopenshell.api.run("root.create_entity", m._file, ifc_class="IfcSpace", name="S1")
    s2 = ifcopenshell.api.run("root.create_entity", m._file, ifc_class="IfcSpace", name="S2")
    ifcopenshell.api.run("aggregate.assign_object", m._file, relating_object=storey.entity, products=[s1, s2])
    write_named_pset(m._file, s1, "MiniBIM ILS", {"EenheidNummer": "01.00.01"})
    write_named_pset(m._file, s2, "MiniBIM ILS", {"EenheidNummer": "01.00.01"})
    zones = group_spaces_by_property(m._file, "MiniBIM ILS", "EenheidNummer")
    assert len(zones) == 1
    assert zones[0].Name == "01.00.01"


def test_georeference():
    m = IfcModel()
    set_georeference(m._file, projected_crs={"Name": "EPSG:28992"}, coordinate_operation={"Eastings": 100000, "Northings": 400000})
    assert m._file.by_type("IfcProjectedCRS")[0].Name == "EPSG:28992"
    assert m._file.by_type("IfcMapConversion")[0].Eastings == 100000


def test_quantities():
    m = IfcModel()
    site = m.add_site("S")
    b = m.add_building(site, "B")
    storey = m.add_storey(b, "BG", elevation=0)
    space = ifcopenshell.api.run("root.create_entity", m._file, ifc_class="IfcSpace", name="R")
    ifcopenshell.api.run("aggregate.assign_object", m._file, relating_object=storey.entity, products=[space])
    write_quantities(m._file, space, "Qto_SpaceBaseQuantities", {"NetFloorArea": 10, "NetVolume": 30})
    qset = m._file.by_type("IfcElementQuantity")[0]
    assert qset.Name == "Qto_SpaceBaseQuantities"
