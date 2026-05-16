#!/usr/bin/env python3
"""
Build a tapered extrusion example using IfcExtrudedAreaSolidTapered.

Creates an IFC4 model with a bridge pier that tapers from a 2×2m base
to a 1×1m top over 8 metres height.

Usage:
    python examples/build_tapered_pier.py
"""

from pathlib import Path as FilePath

from ifckit import IfcModel, IfcSchema, PendingTaperedExtrusion
from ifckit.geometry import Path as IfcPath, Plane, Vec


def main():
    model = IfcModel("Tapered Pier", IfcSchema.IFC4)
    site = model.add_site("Bridge Site")
    bldg = model.add_building(site, "Bridge")
    storey = model.add_storey(bldg, "Deck", elevation=0.0)

    # Helper: axis-aligned square centred on origin as a closed IfcPath
    def square(size: float):
        h = size / 2
        return IfcPath.from_pts(
            [Vec(-h, -h, 0), Vec(h, -h, 0), Vec(h, h, 0), Vec(-h, h, 0)],
            closed=True,
        )

    i = square(2)
    o = square(1).move(Vec(0, 2, 0))
    print(f"i={i.to_pts()}  o={o.to_pts()}")
    pier = PendingTaperedExtrusion(
        plane=Plane.world_xy(),
        start_profile=i,
        end_profile=o,
        height=8.0,
        name="Pier_A1",
    )
    storey.add(pier)

    output_dir = FilePath(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    path = output_dir / "tapered_pier.ifc"
    model.save(str(path))
    print(f"Saved to {path}")

    ifc = model._file
    tapered = ifc.by_type("IfcExtrudedAreaSolidTapered")
    print(f"IfcExtrudedAreaSolidTapered: {len(tapered)}")
    print(f"IfcElement: {len(ifc.by_type('IfcElement'))}")
    print(f"IfcBuildingStorey: {len(ifc.by_type('IfcBuildingStorey'))}")
    for s in tapered:
        print(
            f"  depth={s.Depth:g}m  start={s.SweptArea.OuterCurve.Points[0].Coordinates}  "
            f"end={s.EndSweptArea.OuterCurve.Points[0].Coordinates}"
        )


if __name__ == "__main__":
    main()
