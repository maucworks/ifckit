# Plan: IfcSectionedSpine Implementatie

## Doel
Complexe kozijnen maken met `IfcSectionedSpine` die langs een 3D curve (boog/hellend) profielerenn.

## Achtergrond

### Huidige status
- `directrix_from_path(path)` — maakt al `IfcCompositeCurve` met Line + Arc segmenten
- Profiel helpers: `RectangleProfile`, `IShapeProfile`, `LShapeProfile`, etc.
- `IfcExtrudedAreaSolid` — alleen rechte extrusie

### Ontbreekt
- `IfcSectionedSpine` builder functie
- Voorbeeld implementatie (boogkozijn)

## Implementatie

### Stap 1: `sectioned_spine()` functie

**Bestand:** `ifckit/builders/_geom.py`

```python
def sectioned_spine(
    f: ifcopenshell.file,
    spine_curve: ifcopenshell.entity_instance,
    cross_sections: list[ifcopenshell.entity_instance],
    positions: list[ifcopenshell.entity_instance],
) -> ifcopenshell.entity_instance:
    """Create IfcSectionedSpine.

    Args:
        spine_curve: IfcCompositeCurve (3D curve/boog)
        cross_sections: LIST of IfcProfileDef (profielen op elke positie)
        positions: LIST of IfcAxis2Placement3D (posities langs curve)

    Returns:
        IfcSectionedSpine entity
    """
    return f.create_entity(
        "IfcSectionedSpine",
        SpineCurve=spine_curve,
        CrossSections=cross_sections,
        CrossSectionPositions=positions,
    )
```

### Stap 2: `shape_representation()` aanpassen

**Bestand:** `ifckit/builders/_geom.py`

Ondersteun `rep_type="SectionedSpine"` in shape_representation().

```python
def shape_representation(
    f: ifcopenshell.file,
    context: ifcopenshell.entity_instance,
    solid: ifcopenshell.entity_instance,
    rep_type: str = "SweptSolid",
) -> ifcopenshell.entity_instance:
    # ... bestaande code ...
    # Toevoegen: SectionedSpine support
    valid_types = (
        "SweptSolid",
        "SectionedSpine",  # nieuw
        "Brep",
        "Tessellation",
        "MappedRepresentation",
    )
```

### Stap 3: Voorbeeld component - Boogkozijn

**Bestand:** `ifckit/components/pythonic/curved_casement_component.py`

```python
@component("curved_casement")
class CurvedCasementComponent(WindowComponent):
    """Boogkozijn met IfcSectionedSpine."""

    name = "curved_casement"

    def build(self, ifc_file, plane, w, h, params):
        # Maak boog-path (halve cirkel boog)
        # Maak profiel(en) - rechthoek voor kozijn
        # Maak positions langs boog
        # Gebruik sectioned_spine()
        # Return EvaluatedComponent(solid=spine, role="Lining", ...)
```

### Stap 4: Schuine vensterbank (optioneel)

**Bestand:** `ifckit/components/pythonic/sloped_sill_component.py`

Variante met hellend pad:
- `Path` met line segment op hoek
- Zelfde `SectionedSpine` mechanisme

## Voorbeeld gebruik

### Boogkozijn
```python
# Pad: halve cirkel boog
arc_path = Path.from_pts([
    Vec(0, 0, 0),
    Vec(1000, 0, 0),
], curve_type="arc")  # boog met straal

# Profiel: rechthoekig kozijnprofiel
profile = RectangleProfile(width=55, height=70)

# Positions langs boog (2 posities: begin en einde)
pos_start = axis2placement3d(f, Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0))
pos_end = axis2placement3d(f, Vec(1000, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0))

# Maak SectionedSpine
spine = sectioned_spine(f, spine_curve, [profile_def, profile_def], [pos_start, pos_end])
```

### Schuine vensterbank
```python
# Pad: schuine line (hellend onder kozijn)
sloped_path = Path.from_pts([
    Vec(0, 0, 0),
    Vec(1000, -150, 0),  # hellend: -150mm over 1000mm
])

# Profiel: trapezium
profile = ArbitraryProfile(pts=[...])

# SectionedSpine
spine = sectioned_spine(f, sloped_path, [profile], [pos_start, pos_end])
```

## Schema support

| Entiteit | IFC2X3 | IFC4 | IFC4X3 |
|---------|--------|------|--------|
| `IfcSectionedSpine` | ✅ | ✅ | ✅ |
| `IfcCompositeCurve` | ✅ | ✅ | ✅ |
| `IfcCompositeCurveSegment` | ✅ | ✅ | ✅ |

## Test plan

1. Unit test voor `sectioned_spine()`
2. IFC output test met boogkozijn
3. Valideer IFC met ifcvalidate

## Risico's

1. **Viewer support** — niet alle viewers ondersteunen SectionedSpine
2. **Profiel type matching** — alle CrossSections moeten zelfde ProfileType hebben
3. **Posities** — moeten exact 3D zijn (Dim=3)

## Alternatieven als SectionedSpine niet werkt

1. **Meerdere IfcExtrudedAreaSolid** — segment voor segment, aan elkaar gelegd via IfcMappedItem
2. **IfcBooleanResult** — minder elegant maar werkt in alle viewers
3. **Handmatige mesh** — IfcTriangulatedFaceSet (alleen IFC4+)

## Tijdlijn

- Stap 1-2: ~1 uur
- Stap 3: ~2 uur
- Stap 4: ~1 uur (optioneel)

Totaal: ~3-4 uur