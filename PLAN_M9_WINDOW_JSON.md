# M9 — Window/Door JSON Component Graph: Implementatieplan (rev 3)

**Status:** IN PROGRESS  
**Target commit:** `feat(builders): JSON component-graph geometry for windows and doors (M9)`

---

## Doel

Window- en deurgeometrie — inclusief de **opening void** — beschrijven als
evalueerbare JSON node-graphs ("component graphs").

Met een component_graph kan een `PendingWindow` of `PendingDoor` direct als
child van een wall of slab worden toegevoegd. De builder genereert automatisch
het `IfcOpeningElement` op basis van de `opening_nodes` sectie in de JSON.

**Model B**: de window/door definieert zijn eigen opening.  
**Model A** (extern `add_opening()` + `add_window()`) blijft volledig intact.

---

## JSON preset formaat (definitief)

### Bestandslocatie

```
ifckit/window_types/fixed_casement.json
ifckit/window_types/door_flush.json
```

### Structuur

```json
{
  "version": 1,
  "parameters": {
    "w": 1000,
    "h": 1000,
    "lining_depth": 0.070,
    "lining_thickness": 55,
    "panel_depth": 0.006,
    "glazing_inset": 20
  },
  "opening_nodes": [ ... ],
  "nodes": [ ... ]
}
```

### Sleutels

| Sleutel | Betekenis |
|---|---|
| `parameters.w` | Referentiebreedte van het canvas (niet null — verplicht) |
| `parameters.h` | Referentiehoogte van het canvas (niet null — verplicht) |
| overige parameters | Absolute maten (meters voor dieptes, reference-units voor 2D) |
| `opening_nodes` | Node-graph die de **opening void** beschrijft |
| `nodes` | Node-graph die de **fill geometrie** beschrijft |

### Schaling

`w` en `h` in parameters zijn de **referentiedimensies** van het 2D tekencanvas.  
Alle 2D-coördinaten in `p0`/`p1` van `rect`-nodes zijn getekend in dit canvas.

Bij evaluate met `actual_w` en `actual_h`:
```
scale_x = actual_w / ref_w
scale_y = actual_h / ref_h
```

Elke 2D-punt `(x, y)` → `(x * scale_x, y * scale_y)`.

Absolute maten (`depth`, `z_offset`) worden **niet** geschaald — die zijn altijd in meters.

**Voorbeeld:** canvas 1000×1000, twee rects `(0,0)-(750,1000)` en `(750,0)-(1000,1000)` → altijd 75%/25% verhouding, ongeacht de werkelijke afmeting.

### opening_nodes vs nodes

- `opening_nodes` — beschrijft de void geometrie. Nodes met `output: true` worden als `IfcOpeningElement` solid gebruikt.
- `nodes` — beschrijft de fill geometrie. Nodes met `output: true` worden als window/door solids gebruikt.
- Nodes met `output: false` (of geen `output`) zijn profielen/helpers — worden niet geëmitteerd maar zijn beschikbaar als input voor andere nodes.
- `opening_nodes` is optioneel: als absent, genereert Model B geen opening (niche/template scenario).

### Ondersteunde node ops (v1)

| Op | Input | Output | Schaalt |
|---|---|---|---|
| `rect` | `p0`, `p1` (2D punten) | `Path` | ja (via scale_x/y) |
| `difference` | `a`, `b` (Path ids) | `Path` met hole | nee (paths al geschaald) |
| `extrude` | `profile` (Path id), `depth`, `z_offset` | `IfcExtrudedAreaSolid` | depth/z_offset niet |

---

## Architectuur

```
Caller:
    m.add(PendingWindow(plane=..., component_graph="fixed_casement"), wall)
                ↓
    model.add() dispatcher detecteert:
        - pending is PendingWindow/PendingDoor
        - pending.component_graph is set
        - container is EntityHandle van wall/slab
        → _add_fill_model_b()

    _add_fill_model_b()
        1. _find_containing_storey(host)
        2. build_window_model_b(pending, host, storey, ctx)

    build_window_model_b()
        1. _extract_wall_thickness(host_entity)
        2. evaluate_opening_nodes(preset, ifc_file, ctx, params)
           → List[EvaluatedComponent] met role="Opening"
        3. IfcOpeningElement aanmaken (uit solid van opening_nodes)
        4. _build_fill_from_graph(...)
           → IfcWindow met fill geometrie

    evaluate_opening_nodes(preset, ifc_file, ctx, params)
        - laadt opening_nodes uit preset
        - berekent scale_x = actual_w / ref_w, scale_y = actual_h / ref_h
        - evalueert nodes via _eval_node_list()

    evaluate_component_graph(preset, ifc_file, ctx, params)
        - laadt nodes uit preset
        - zelfde schaling
        - evalueert via _eval_node_list()

    _eval_node_list(nodes, ..., scale_x, scale_y)
        - evalueert rect/difference/extrude nodes
        - geeft scale_x/y door aan _eval_node_rect/_eval_point
```

---

## Wat klaar is

- [x] `Path.holes`, `Path.with_hole()`, `profile_from_points` met voids
- [x] `component_graph` veld op `PendingWindowType`, `PendingDoorType`
- [x] `component_graph` + `plane` veld op `PendingWindow`, `PendingDoor`
- [x] `_build_fill_from_graph()` in `door_window.py`
- [x] `_build_fill()` graph-pad via `graph_name`
- [x] `build_window()`, `build_door()` — `graph_name` param toegevoegd
- [x] `model.add()` dispatcher Model B pad
- [x] `_add_fill_model_b()`, `_find_containing_storey()` op `IfcModel`
- [x] `build_window_model_b()`, `build_door_model_b()`, `_extract_wall_thickness()`
- [x] JSON presets herschreven: `w`/`h` als ref, `opening_nodes` als node-graph
- [x] `_eval_point()` met `scale_x`/`scale_y` parameters
- [x] `_eval_node_rect()` met `scale_x`/`scale_y` parameters
- [x] `_eval_node_list()` — centrale evaluator voor zowel fill als opening nodes
- [x] `evaluate_component_graph()` — schaling ingebouwd
- [x] `evaluate_opening_nodes()` — vervangt `evaluate_opening_component()`

## Wat nog moet

- [ ] `build_window_model_b()` aanpassen: gebruik `evaluate_opening_nodes()` i.p.v. `evaluate_opening_component()`, bouw opening uit solid in plaats van simpele rect
- [ ] `build_door_model_b()` idem
- [ ] Tests updaten:
  - `test_component_graph.py` — `evaluate_opening_component` tests vervangen door `evaluate_opening_nodes`; schaling testen
  - `test_model_b_window.py` — bestaande tests blijven grotendeels geldig
- [ ] `pytest` volledig groen
- [ ] `ruff check ifckit/` geen fouten

---

## Bestanden gewijzigd (totaal)

| Bestand | Wijziging |
|---|---|
| `ifckit/window_types/fixed_casement.json` | `w`/`h` als ref (1000), `opening_nodes` als node-graph, `lining_thickness`/`glazing_inset` in ref-units |
| `ifckit/window_types/door_flush.json` | Idem |
| `ifckit/elements/opening.py` | `plane` + `component_graph` veld op `PendingWindow` + `PendingDoor` |
| `ifckit/builders/component_graph.py` | `_eval_point` met schaling, `_eval_node_rect` met schaling, `_eval_node_list`, `evaluate_component_graph` (schaling), `evaluate_opening_nodes` (vervangt `evaluate_opening_component`) |
| `ifckit/builders/door_window.py` | `build_window_model_b`, `build_door_model_b` (opening_nodes pad), `_extract_wall_thickness`, `graph_name` param op `build_window`/`build_door` |
| `ifckit/model.py` | `add()` dispatcher, `_add_fill_model_b()`, `_find_containing_storey()` |
| `tests/builders/test_component_graph.py` | Schaling tests, `evaluate_opening_nodes` tests |
| `tests/builders/test_window_graph_ifc.py` | Model A integratie-tests (gecorrigeerd) |
| `tests/builders/test_model_b_window.py` | Model B integratie-tests |

---

## Definition of Done — M9

1. `m.add(PendingWindow(plane=..., component_graph="fixed_casement"), wall)` werkt
2. `IfcOpeningElement` geometrie komt uit `opening_nodes` — volledig evalueerbaar node-graph
3. Geometrie schaalt correct mee: `rect(0,0)-(750,1000)` op canvas 1000×1000 → altijd 75% breedte
4. `opening_nodes` met `output: false` emitteert geen solid (toekomstige niche-scenario's)
5. `IfcWindow` fill met lining + glazing (voids in lining-profiel)
6. Model A ongewijzigd — 1010+ bestaande tests groen
7. `ruff check ifckit/` geen fouten
8. Commit: `feat(builders): JSON component-graph geometry for windows and doors (M9)`
