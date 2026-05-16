# ifckit Blender Integratie — Routes

## Doel

Python-gedreven IFC authoring vanuit Blender, analoog aan Rhino/Grasshopper.
Blender-objecten (meshes, curves) zijn de geometriebron, ifckit-bouwknechten
genereren er IFC van.

Drie niveau's mogelijk:

---

## Route A — Standalone addon (geen Bonsai)

```
ifckit_blender/
├── __init__.py
├── ui.py            # Panel in 3D View sidebar → IfcKit tab
├── operator.py      # Build from selection, Export IFC
├── prop.py          # Scene/object properties
├── mesh_convert.py  # mesh vertices → Vec[], curves → Path, etc.
└── ops/
    ├── build_from_object.py
    └── export.py
```

**Werkt zonder Bonsai.** ifckit maakt een standalone `IfcModel` en saved `.ifc`
als output. `.blend` is de source of truth (bewaart geometrie + code).

Gebruik:

```python
# Operator "Build IFC from Active"
obj = bpy.context.active_object
verts = [v.co for v in obj.data.vertices]
footprint = [Vec(v.x, v.y, v.z) for v in verts]

wall = PendingWall(footprint=footprint, plane=Plane.world_xy(), height=3.0)
bk.export([wall], output="/tmp/project.ifc")
```

---

## Route B — Bonsai-extensie (tool.Ifc.get())

Zelfde structuur als Route A, maar operators gebruiken `tool.Ifc.get()` om
rechtstreeks in het actieve Bonsai-project te bouwen. Panelen kunnen
aansluiten op Bonsai's bestaande tab-systeem (`bl_parent_id`).

**Vereist:** Bonsai (BlenderBIM) moet geïnstalleerd en actief zijn.

```python
operator.build():
    ifc_file = tool.Ifc.get()
    model = IfcModel.from_file(ifc_file)
    model.add(pending, container=storey_handle)
```

---

## Route C — Geometry Nodes pipeline

```
Mesh + Geometry Nodes modifier
  ├── Genereert footprint via GN nodes (Extrude, Transform, etc.)
  ├── Set Attribute: ifckit_type, ifckit_height, ifckit_global_id
  └── Python operator leest geëvalueerde modifier output
        → named attributes uitlezen
        → mesh verts → Vec[]
        → bk.add_or_replace()
```

**Voordelen:** Blender-native (stabiel), `.blend` persistent, geen extra addons.
**Beperking:** Geen live feedback — operator moet expliciet worden aangeroepen.

---

## Route D — IfcSverchok (bestaand)

Onderdeel van IfcOpenShell (`src/ifcsverchok/`). ~31 nodes voor IFC authoring
in Sverchok. Experimenteel (GSoC 2022), undo kan Blender laten crashen.

**Niet aanbevolen voor productie.** Zie
[docs.ifcopenshell.org/ifcsverchok.html](https://docs.ifcopenshell.org/ifcsverchok.html).

---

## Overzicht

| Route | Bonsai nodig? | Persistente .blend? | Interactief? | Moeite |
|-------|--------------|---------------------|-------------|--------|
| A | Nee | Ja | Beperkt (operator) | Matig |
| B | Ja | Ja (via Bonsai) | Beperkt (operator) | Matig |
| C | Nee | Ja | Beperkt (per frame) | Weinig (GN bestaand) |
| D | Ja | Nee (crasht) | Ja (live Sverchok) | Groot (experimenteel) |

**Aanbevolen:** Route A + C combineren. Standalone `.blend` als source,
Geometry Nodes voor visuele parametriek, `bk.export()` voor `.ifc` output.
