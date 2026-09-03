# This file was generated with the assistance of an AI coding tool.
"""Tests voor IfcSystem builder (BIM Basis tegel 4.2 proof)."""

import ifcopenshell.api
from ifckit.builders.system import add_distribution_system, add_system
from ifckit.model import IfcModel


def test_add_system():
    m = IfcModel()
    site = m.add_site("S")
    b = m.add_building(site, "B")
    m.add_storey(b, "BG", elevation=0)
    # dummy products
    wall = ifcopenshell.api.run("root.create_entity", m._file, ifc_class="IfcWall", name="W1")
    sys = add_system(m._file, "Verwarming", products=[wall])
    assert sys.is_a("IfcSystem")
    assert sys.Name == "Verwarming"
    rels = [r for r in m._file.by_type("IfcRelAssignsToGroup") if r.RelatingGroup == sys]
    assert len(rels) == 1
    assert wall in rels[0].RelatedObjects


def test_add_distribution_system():
    m = IfcModel()
    sys = add_distribution_system(m._file, "Ventilatie", long_name="Luchtbehandeling")
    assert sys.is_a("IfcDistributionSystem")
    assert sys.LongName == "Luchtbehandeling"
