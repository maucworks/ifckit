#!/usr/bin/env python3
# This file was generated with the assistance of an AI coding tool.
"""
Build MiniBIM SO voorbeeld — end-to-end ILS-demo.

Genereert een SO-model met:
  - Georeferentie RD New (EPSG:28992)
  - NL-SfB classificatie
  - Terrein / Bouwwerk / Gebied / Ruimte / Buitenruimte als IfcSpace
  - MiniBIM ILS pset per ruimte
  - IfcZone groepering op EenheidNummer
  - Qto_SpaceBaseQuantities

Gebaseerd op specs/minibim referentie-IFCs (SO_00).

Usage:
    python examples/build_minibim_so.py
    # output: examples/output/minibim_so.ifc
"""

import ifcopenshell.api

from ifckit.builders.classification import add_classification, assign_classification
from ifckit.builders.georeference import set_georeference
from ifckit.builders.quantities import write_quantities
from ifckit.builders.zones import group_spaces_by_property
from ifckit.ils.minibim import apply_minibim_pset
from ifckit.ils.minibim.naming import format_eenheid_nummer
from ifckit.model import IfcModel


def main():
    from ifckit.schema import IfcSchema
    m = IfcModel(name="MiniBIM SO voorbeeld", schema=IfcSchema.IFC4)

    # Georeferentie — RD New, false origin ZW perceel
    set_georeference(
        m._file,
        projected_crs={"Name": "EPSG:28992"},
        coordinate_operation={"Eastings": 100000, "Northings": 400000, "OrthogonalHeight": 0},
    )

    # Classificatie
    cls = add_classification(m._file, "NL-SfB", edition="2019")

    site = m.add_site("Terrein", location=(0, 0, 0))
    building = m.add_building(site, "Bouwwerk 00")
    storey = m.add_storey(building, "BG", elevation=0)

    # Helper om een MiniBIM-ruimte te maken
    def add_minibim_space(name, ruimtetype, gebied_soort="Gebruiksfunctie",
                          gebied_type="Appartement", gebruiks="Woonfunctie",
                          orientatie="Zuid", bepalings="NVO",
                          eenheid="01.00.01", bouwnr="00",
                          nlsfb=("22.10", "binnenwanden"), area=20, volume=60):
        sp = ifcopenshell.api.run("root.create_entity", m._file, ifc_class="IfcSpace", name=name)
        ifcopenshell.api.run("aggregate.assign_object", m._file, relating_object=storey.entity, products=[sp])

        apply_minibim_pset(
            sp, m._file,
            RuimteType=ruimtetype,
            GebiedsSoort=gebied_soort,
            GebiedsType=gebied_type,
            Gebruiksbestemming=gebruiks,
            Orientatie=orientatie,
            Bepalingsmethode=bepalings,
            EenheidNummer=eenheid,
            BouwwerkNummer=bouwnr,
            RuimteNummer=eenheid.split(".")[-1],
        )
        assign_classification(m._file, [sp], cls, nlsfb[0], nlsfb[1])
        write_quantities(m._file, sp, "Qto_SpaceBaseQuantities", {"NetFloorArea": area, "NetVolume": volume})
        return sp

    # Terrein (als ruimte)
    add_minibim_space("Terrein", "Onbenoemde ruimte", gebied_soort="Gebruiksfunctie",
                      gebied_type="Gebruiksgebied",
                      area=500, volume=0, nlsfb=("00.00", "terrein"))

    # Gebied: appartement
    add_minibim_space("Gebied 01", "Woonkamer", gebied_soort="Gebruiksfunctie",
                      gebied_type="Appartement", gebruiks="Woonfunctie",
                      orientatie="Zuid", eenheid="01.00.01", area=45, volume=135)

    # Ruimten binnen het gebied (zelfde EenheidNummer)
    eenheid = format_eenheid_nummer(1, 0, 1)
    add_minibim_space("Woonkamer", "Woonkamer", area=25, volume=75, eenheid=eenheid)
    add_minibim_space("Slaapkamer", "Slaapkamer", area=12, volume=36, eenheid=eenheid)
    add_minibim_space("Badruimte", "Badruimte", area=6, volume=18, eenheid=eenheid)

    # Tweede eenheid
    eenheid2 = format_eenheid_nummer(1, 0, 2)
    add_minibim_space("Woonkamer 2", "Woonkamer", area=28, volume=84, eenheid=eenheid2)

    # Buitenruimte
    sp = ifcopenshell.api.run("root.create_entity", m._file, ifc_class="IfcSpace", name="Balkon")
    ifcopenshell.api.run("aggregate.assign_object", m._file, relating_object=storey.entity, products=[sp])
    apply_minibim_pset(sp, m._file, BuitenruimteType="Balkon", Orientatie="Zuid",
                       Bepalingsmethode="NVO", EenheidNummer=eenheid, BouwwerkNummer="00")

    # Zones per EenheidNummer
    zones = group_spaces_by_property(m._file, "MiniBIM ILS", "EenheidNummer")
    print(f"Zones: {len(zones)} — {[z.Name for z in zones]}")

    # Save
    from pathlib import Path
    out = Path(__file__).parent / "output" / "minibim_so.ifc"
    out.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(out))
    print(f"✓ Saved to {out}")
    print(f"  Spaces: {len(m._file.by_type('IfcSpace'))}")
    print(f"  Zones: {len(m._file.by_type('IfcZone'))}")
    print(f"  MiniBIM psets: {len([p for p in m._file.by_type('IfcPropertySet') if p.Name=='MiniBIM ILS'])}")
    print(f"  CRS: {m._file.by_type('IfcProjectedCRS')[0].Name}")
    print(f"  Classifications: {len(m._file.by_type('IfcClassification'))}")


if __name__ == "__main__":
    main()
