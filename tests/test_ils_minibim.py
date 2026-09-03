"""Tests voor ils/minibim vocabularies en helpers."""

import ifcopenshell.api
from ifckit.model import IfcModel
from ifckit.ils.minibim import (
    MiniBimSpec,
    apply_minibim_pset,
    is_valid_ruimte_type,
    RUIMTE_TYPES,
    GEBIED_TYPES,
    BOUWWERK_TYPES,
)
from ifckit.ils.minibim.pset import PARAMS


def test_ruimte_types():
    assert len(RUIMTE_TYPES) == 64
    assert "Slaapkamer" in RUIMTE_TYPES
    assert "Woonkamer" in RUIMTE_TYPES
    assert is_valid_ruimte_type("Slaapkamer")
    assert not is_valid_ruimte_type("Onzin")


def test_gebied_types():
    assert len(GEBIED_TYPES) == 50
    assert "Appartement" in GEBIED_TYPES


def test_bouwwerk_types():
    assert "Woning" in BOUWWERK_TYPES
    assert len(BOUWWERK_TYPES) == 23


def test_pset_params():
    assert len(PARAMS) == 19
    assert "RuimteType" in PARAMS
    assert "EenheidNummer" in PARAMS


def test_apply_pset():
    m = IfcModel()
    site = m.add_site("S")
    b = m.add_building(site, "B")
    storey = m.add_storey(b, "BG", elevation=0)
    space = ifcopenshell.api.run("root.create_entity", m._file, ifc_class="IfcSpace", name="R")
    ifcopenshell.api.run("aggregate.assign_object", m._file, relating_object=storey.entity, products=[space])
    apply_minibim_pset(space, m._file, RuimteType="Slaapkamer", Bepalingsmethode="NVO", EenheidNummer="01.00.01")
    psets = [p for p in m._file.by_type("IfcPropertySet") if p.Name == "MiniBIM ILS"]
    assert len(psets) == 1
    names = {p.Name for p in psets[0].HasProperties}
    assert names == {"RuimteType", "Bepalingsmethode", "EenheidNummer"}


def test_minibim_spec():
    s = MiniBimSpec()
    assert s.version == "3.1"
    assert s.validate_ruimtetype("Slaapkamer")
    assert not s.validate_ruimtetype("XXX")


def test_naming():
    from ifckit.ils.minibim.naming import format_eenheid_nummer, is_valid_eenheid_nummer

    assert format_eenheid_nummer(1, 0, 1) == "01.00.01"
    assert is_valid_eenheid_nummer("01.00.01")
    assert not is_valid_eenheid_nummer("1.0.1")
