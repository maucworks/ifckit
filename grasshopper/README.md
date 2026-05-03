# ifckit for Grasshopper

ifckit ships a set of Grasshopper Python 3 Script components for Rhino 8.
They let you build IFC files, preview geometry as Rhino meshes, and generate
2-D section drawings — all from a Grasshopper canvas.

## Contents

- [Installation](#installation)
- [Component overview](#component-overview)
- [Typical workflows](#typical-workflows)
  - [Build and export an IFC file](#1-build-and-export-an-ifc-file)
  - [Preview geometry meshes in Rhino](#2-preview-geometry-meshes-in-rhino)
  - [Generate section drawings](#3-generate-section-drawings)
  - [Import IFC spaces](#4-import-ifc-spaces)
- [Component reference](#component-reference)
- [Rebuilding the .gh file from source](#rebuilding-the-gh-file-from-source)
- [Development: live reload](#development-live-reload)

---

## Installation

Rhino 8 ships its own CPython 3.9 environment. Install ifckit into it once
from the **Rhino ScriptEditor** (`EditPythonScript`) or from a one-shot
Script component:

```python
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "ifckit[ifc]"], check=True)
```

`ifcopenshell` is already bundled with Rhino 8, so `[ifc]` will skip it if
it is already present.

To use a local development checkout instead:

```python
import subprocess, sys
subprocess.run(
    [sys.executable, "-m", "pip", "install", "-e", r"C:\path\to\ifckit"],
    check=True,
)
```

Restart Rhino once after installing.

---

## Component overview

All components live in `grasshopper/src/`. They are grouped into four panels
in the `.gh` file.

### Profiles panel

| Component | Nickname | Purpose |
|---|---|---|
| `gh_profile.py` | **ifckit Profile** | Create any supported profile type and output Profile JSON |

### Elements panel

| Component | Nickname | Purpose |
|---|---|---|
| `gh_create_wall.py` | **ifckit Wall** | Wall from a base curve + height + thickness |
| `gh_create_beam.py` | **ifckit Beam** | Beam along a straight line |
| `gh_create_beam_any.py` | **ifckit Beam (Any Path)** | Beam along a line **or** arc (auto-detects) |

### Export panel

| Component | Nickname | Purpose |
|---|---|---|
| `gh_build_json.py` | **ifckit Build JSON** | Merge element JSON strings into a full IFC project JSON |
| `gh_export_json.py` | **ifckit Export IFC** | Build the IFC model, export to file and/or preview meshes in Rhino |

### Drawing panel

| Component | Nickname | Purpose |
|---|---|---|
| `gh_drawing.py` | **ifckit Drawing** | Import one named section drawing as curves + hatches |
| `gh_svg_curves.py` | **ifckit SVG Curves** | Import all drawings from an IFC file or JSON model |

### Import panel

| Component | Nickname | Purpose |
|---|---|---|
| `gh_spaces.py` | **ifckit Spaces** | Import IfcSpace footprints, hatches, labels and/or 3-D meshes |

---

## Typical workflows

### 1. Build and export an IFC file

The standard chain for authoring IFC from Grasshopper geometry:

```
[ifckit Profile] ──────────────────────────────────────┐
                                                        ▼
[base curves] ──▶ [ifckit Wall]  ──▶ [ifckit Build JSON] ──▶ [ifckit Export IFC]
[line curves] ──▶ [ifckit Beam]  ──┘
```

1. **ifckit Profile** — select profile type (`I`, `L`, `rect`, `circle`,
   `hollow_circle`, `steel`) and dimensions. Output is a Profile JSON string.

2. **ifckit Wall / Beam** — connect Rhino geometry (curves/lines) and the
   Profile JSON. Each component outputs a list of element JSON strings.

3. **ifckit Build JSON** — wire all element JSON lists into `json_input`
   (Data Match: Graft). Set `project_name`, `author`, `unit` (`MILLIMETRE` or
   `METRE`), `ifc_version` (`IFC4` or `IFC2X3`). Output is a single project
   JSON string.

4. **ifckit Export IFC** — wire the project JSON into `json_input`. Set
   `ifc_output` to an absolute path. Toggle `run_export = True` to write the
   file.

### 2. Preview geometry meshes in Rhino

The **ifckit Export IFC** component can also tessellate the IFC model and
bake the meshes directly into the Rhino document — no need to round-trip
through a file.

- Set `run_preview = True` on the Export node.
- Meshes are baked onto layers named after the IFC element type
  (e.g. `IfcWall`, `IfcBeam`).
- `mesh_quality` controls tessellation: `"coarse"`, `"default"`, `"fine"`.
- The model is also stored in `sc.sticky` under the key in `sticky_key`
  (default `"ifckit_model"`) and the `model_ready` integer output increments
  on every successful build — use it to trigger downstream drawing nodes.

### 3. Generate section drawings

ifckit can generate 2-D section drawings from an IFC model via
`ifcopenshell.draw`. Drawings are placed as curves and hatches on structured
Rhino layers.

**From an existing .ifc file — use `gh_svg_curves.py`:**

```
[ifc_path] ──▶ [ifckit SVG Curves]
```

Set `ifc_path` to the absolute path of the file, then `run = True`.
All drawings in the file are imported. Curves land on layers:

```
IFC-SVG :: <drawing_name> :: cut          :: <IfcType>
IFC-SVG :: <drawing_name> :: cut_hatch    :: <IfcType>
IFC-SVG :: <drawing_name> :: projection   :: <IfcType>
```

**From a live model — use `gh_drawing.py`:**

```
[ifckit Export IFC] ──model_ready──▶ [ifckit Drawing]
```

Wire `model_ready` from the Export node to `model_ready` here.
Set `drawing_name` to the exact name of the drawing (as defined in the
IFC `IfcAnnotation`). Set `run = True` to generate.

Optional inputs:
- `dest_plane` — a Rhino `Plane` to place the drawing in world space instead
  of at the section plane origin.
- `hatch_pattern` — fallback Rhino hatch pattern for cut fills (default `"Solid"`).
- `clear = True` — removes previously imported curves/hatches for this drawing
  before regenerating.

### 4. Import IFC spaces

The **ifckit Spaces** component reads `IfcSpace` entities from any IFC file
and draws them in Rhino:

```
[ifc_path] ──▶ [ifckit Spaces]
```

Options (all default to `True`):
- `import_fp` — 2-D footprint curves
- `import_hatch` — filled hatch (pattern set by `hatch_pattern`)
- `import_ann` — `TextDot` labels with space name and area
- `import_mesh` — 3-D tessellated body meshes (`import_mesh = False` by default)

Objects land on layers:

```
IFC-Spaces :: <StoreyName> :: <SpaceName>
```

---

## Component reference

### ifckit Profile

| Input | Type | Description |
|---|---|---|
| `profile_type` | str | `"I"`, `"L"`, `"rect"`, `"circle"`, `"hollow_circle"`, `"steel"` |
| `height` | float | Height / leg A |
| `width` | float | Width / leg B |
| `web_thickness` | float | Web thickness (I-beam only) |
| `flange_thickness` | float | Flange / leg thickness |
| `radius` | float | Radius (circle / hollow_circle) |
| `wall_thickness` | float | Wall thickness (hollow_circle) |
| `steel_name` | str | Section name e.g. `"HEA200"` (steel only) |
| `unit` | str | `"m"` (default) or `"mm"` |

Output `json_out` is a Profile JSON string — wire directly into any beam or
column component's `profile_json` input.

---

### ifckit Wall

| Input | Type | Description |
|---|---|---|
| `base_curve` | curve | Base line / polyline of the wall |
| `height` | float | Wall height |
| `thickness` | float | Wall thickness |
| `name` | str | Element name (optional) |

---

### ifckit Beam / ifckit Beam (Any Path)

| Input | Type | Description |
|---|---|---|
| `line_curve` / `path_curve` | curve | Axis curve (line only for Beam; line or arc for Any Path) |
| `profile_pts` | point list | Polygon cross-section as Point3d list (fallback) |
| `profile_json` | str | Profile JSON from ifckit Profile node (preferred) |
| `name` | str | Element name (optional) |

`path_type` output reports `"SINGLE_LINE"` or `"SINGLE_ARC"` — useful for
debugging which solid type will be created.

---

### ifckit Build JSON

| Input | Type | Description |
|---|---|---|
| `json_input` | str list | Element JSON strings from Wall / Beam nodes |
| `project_name` | str | IFC project name |
| `author` | str | Author |
| `unit` | str | `"MILLIMETRE"` (default) or `"METRE"` |
| `ifc_version` | str | `"IFC2X3"` (default) or `"IFC4"` |

---

### ifckit Export IFC

| Input | Type | Description |
|---|---|---|
| `json_input` | str | Project JSON from Build JSON node |
| `ifc_output` | str | Absolute path for the `.ifc` file |
| `run_export` | bool | Write the IFC file |
| `run_preview` | bool | Bake preview meshes into Rhino |
| `mesh_quality` | str | `"coarse"`, `"default"`, `"fine"` |
| `sticky_key` | str | `sc.sticky` key (default `"ifckit_model"`) |

`model_ready` output increments on every successful build — wire to Drawing node.

---

### ifckit Drawing

| Input | Type | Description |
|---|---|---|
| `model_ready` | int | From Export node — triggers re-generation |
| `drawing_name` | str | Exact name of the drawing to generate |
| `run` | bool | Set True to generate |
| `dest_plane` | Plane | Rhino plane to place drawing (optional) |
| `hatch_pattern` | str | Fallback fill pattern (default `"Solid"`) |
| `clear` | bool | Remove existing objects first (default True) |
| `sticky_key` | str | `sc.sticky` key to read model from |

---

### ifckit SVG Curves

| Input | Type | Description |
|---|---|---|
| `ifc_path` | str | Absolute path to an `.ifc` file (takes priority) |
| `json_input` | str | Project JSON from Build JSON node |
| `run` | bool | Set True to import |
| `hlr_poly` | bool | Polygonal HLR (default True) |
| `mesher_defl` | float | OCC mesher linear deflection in metres |

---

### ifckit Spaces

| Input | Type | Description |
|---|---|---|
| `ifc_path` | str | Absolute path to the `.ifc` file |
| `run` | bool | Set True to import |
| `layer_root` | str | Root layer name (default `"IFC-Spaces"`) |
| `hatch_pattern` | str | Rhino hatch pattern (default `"Solid"`) |
| `import_fp` | bool | Draw 2-D footprint curves |
| `import_hatch` | bool | Draw hatch fills |
| `import_ann` | bool | Draw TextDot labels |
| `import_mesh` | bool | Tessellate 3-D bodies (default False) |
| `mesh_quality` | str | `"coarse"`, `"default"`, `"fine"` |
| `clear` | bool | Clear existing objects first (default True) |

---

## Rebuilding the .gh file from source

The `.gh` file (`grasshopper/ifckit-components.gh`) is generated
programmatically from the annotated source files in `grasshopper/src/`.

To rebuild it, open `grasshopper/script/build_gh.py` in the **Rhino
ScriptEditor** with Grasshopper open and run it. The script:

1. Reads each `gh_*.py` file in `grasshopper/src/`
2. Parses `@component` / `@input` / `@output` annotations from the docstring
3. Creates Script components grouped by panel
4. Injects the source code via XML round-trip
5. Saves and reopens `grasshopper/ifckit-components.gh`

---

## Development: live reload

During development, every Script component imports `ifckit_reload` as its
first line:

```python
import ifckit_reload  # noqa: F401 — sets sys.path and reloads all of ifckit
```

`grasshopper/src/ifckit_reload.py` calls `ifckit.rhinokit.reload_all()`,
which reloads all ifckit submodules in dependency order (leaves first, root
last). Set the `IFCKIT_PATH` environment variable to point at your checkout
so the shim can find it:

```
IFCKIT_PATH = C:\path\to\ifckit
```

This means you can edit ifckit source files and re-run a Script component
without restarting Rhino.
