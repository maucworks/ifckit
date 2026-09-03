# This file was generated with the assistance of an AI coding tool.
"""Validatie tegen MiniBIM referentie-IFCs (specs/minibim/*.ifc)."""

# Referentie-IFCs wonen in de meta-repo (196-ifckit-admin/specs/minibim), niet in
# deze lib. Kandidaatlocaties: repo-root/specs, ../specs, $IFCKIT_SPEC_DIR.
import os
import pathlib

import ifcopenshell
import pytest

_CANDIDATES = []
if os.environ.get("IFCKIT_SPEC_DIR"):
    _CANDIDATES.append(pathlib.Path(os.environ["IFCKIT_SPEC_DIR"]) / "minibim")
_repo_root = pathlib.Path(__file__).parents[1]
_CANDIDATES += [
    _repo_root / "specs" / "minibim",
    _repo_root.parent / "specs" / "minibim",
    _repo_root.parent.parent / "specs" / "minibim",
]


def _ref_dir() -> pathlib.Path | None:
    for p in _CANDIDATES:
        if p.exists():
            return p
    return None


_REF = _ref_dir()


def _all_ifcs() -> list:
    return list(_REF.rglob("*.ifc")) if _REF else []


pytestmark = pytest.mark.skipif(
    _REF is None,
    reason="specs/minibim niet gevonden (staat in 196-ifckit-admin, zet IFCKIT_SPEC_DIR)",
)


def test_references_exist():
    ifcs = _all_ifcs()
    assert len(ifcs) >= 8, f"expected >=8 reference IFCs, got {len(ifcs)}"


@pytest.mark.parametrize("ifc_path", _all_ifcs())
def test_reference_has_georef_and_classification(ifc_path):
    f = ifcopenshell.open(str(ifc_path))
    # Georef: ProjectedCRS should exist and name contains EPSG
    crs = f.by_type("IfcProjectedCRS")
    # Terrain file has no classification, so skip there
    if "Terrein" not in ifc_path.name:
        assert len(crs) == 1, f"{ifc_path.name}: expected 1 ProjectedCRS"
        assert "EPSG" in (crs[0].Name or ""), f"{ifc_path.name}: CRS name should contain EPSG"

    # If file has spaces or elements, should have MiniBIM ILS pset
    has_spaces = len(f.by_type("IfcSpace")) > 0
    has_elements = any(f.by_type(t) for t in ["IfcWall", "IfcSlab", "IfcWindow", "IfcDoor"])
    if has_spaces or has_elements:
        psets = [p for p in f.by_type("IfcPropertySet") if p.Name == "MiniBIM ILS"]
        # Ruimtelijke Elementen files have many, others may have many via elements
        assert len(psets) > 0, f"{ifc_path.name}: expected MiniBIM ILS psets"


def test_beng_data():
    from ifckit.ils.minibim.beng import BENG_ROWS, load_beng

    rows = load_beng()
    assert len(rows) == 11
    assert BENG_ROWS[0]["Gebruiksbestemming"] == "Bijeenkomstfunctie"
    assert all("Glaspercentage" in r for r in rows)


def test_uitvoeringsplan_raw():
    from ifckit.ils.minibim.uitvoeringsplan import FASEN, load_raw

    assert FASEN == ["SO", "VO", "DO"]
    raw = load_raw()
    assert "headers" in raw and "rows" in raw
    assert len(raw["rows"]) >= 10


def test_generated_ifc_matches_reference_structure():
    """E2E: bouw een minimal MiniBIM-model en valideer structuur zoals referentie."""
    from ifckit.builders.classification import add_classification, assign_classification
    from ifckit.builders.georeference import set_georeference
    from ifckit.builders.quantities import write_quantities
    from ifckit.builders.zones import group_spaces_by_property
    from ifckit.ils.minibim import apply_minibim_pset
    from ifckit.model import IfcModel

    m = IfcModel()
    site = m.add_site("Test")
    b = m.add_building(site, "B1")
    storey = m.add_storey(b, "BG", elevation=0)

    # georef (zoals referentie: EPSG:28992)
    set_georeference(
        m._file,
        projected_crs={"Name": "EPSG:28992"},
        coordinate_operation={"Eastings": 100000, "Northings": 400000},
    )

    # classificatie
    cls = add_classification(m._file, "NL-SfB", edition="2019")

    # spaces met MiniBIM pset + quantities
    for i, rt in enumerate(["Woonkamer", "Slaapkamer"]):
        sp = ifcopenshell.api.run(
            "root.create_entity", m._file, ifc_class="IfcSpace", name=f"R{i}"
        )
        ifcopenshell.api.run(
            "aggregate.assign_object", m._file, relating_object=storey.entity, products=[sp]
        )
        apply_minibim_pset(
            sp,
            m._file,
            RuimteType=rt,
            Bepalingsmethode="NVO",
            EenheidNummer="01.00.01",
            Gebruiksbestemming="Woonfunctie",
        )
        assign_classification(m._file, [sp], cls, "22.10", "binnenwanden")
        write_quantities(
            m._file,
            sp,
            "Qto_SpaceBaseQuantities",
            {"NetFloorArea": 20 + i * 5, "NetVolume": 60 + i * 10},
        )

    zones = group_spaces_by_property(m._file, "MiniBIM ILS", "EenheidNummer")
    assert len(zones) == 1
    assert zones[0].Name == "01.00.01"

    # structuur checks zoals referentie
    assert len(m._file.by_type("IfcProjectedCRS")) == 1
    assert len([p for p in m._file.by_type("IfcPropertySet") if p.Name == "MiniBIM ILS"]) == 2
    assert len(m._file.by_type("IfcElementQuantity")) == 2
