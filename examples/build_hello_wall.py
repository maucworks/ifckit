#!/usr/bin/env python3
"""
Build hello_wall.json example.

Creates a simple IFC model with:
  - 1 wall: 5000 mm long, 3000 mm high, at (0,0,0)
  - 1 window: 1200×1000 mm fixed casement, at center, 1000 mm height
  - Model B: component_graph="fixed_casement" produces opening automatically

Usage:
    python examples/build_hello_wall.py
"""

import json
from pathlib import Path
from ifckit.json_build import build_from_json

def main():
    # Load JSON
    json_path = Path(__file__).parent / "hello_wall.json"
    with open(json_path) as f:
        json_str = f.read()

    print(f"Building from {json_path}...")
    
    # Build model
    model = build_from_json(json_str)
    
    # Save
    output_path = json_path.parent / "output" / "hello_wall.ifc"
    output_path.parent.mkdir(exist_ok=True)
    model.save(str(output_path))
    
    print(f"✓ Saved to {output_path}")
    
    # Summary
    ifc = model._file
    print("\nModel summary:")
    print(f"  Buildings: {len(ifc.by_type('IfcBuilding'))}")
    print(f"  Storeys: {len(ifc.by_type('IfcBuildingStorey'))}")
    print(f"  Walls: {len(ifc.by_type('IfcWall'))}")
    print(f"  Windows: {len(ifc.by_type('IfcWindow'))}")
    print(f"  Openings: {len(ifc.by_type('IfcOpeningElement'))}")

if __name__ == "__main__":
    main()
