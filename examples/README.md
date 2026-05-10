# ifckit Examples

Visual reference for each example.  Click the link to preview in the
[web-ifc-viewer](https://maucworks.github.io/web-ifc-viewer/).

---

## `run_in_blender.py`

Paste into Blender's **Scripting** workspace and press **Run Script**.

Builds the same model as `hello_wall.json` using the Python API:
one wall with four windows and one door (Model B component_graph).
Saves `~/ifckit_blender_demo.ifc`, then imports the geometry into the
active Blender scene.

- If **Bonsai (BlenderBIM)** is installed: imports via `bpy.ops.bim.load_project()`.
- Otherwise: imports directly as meshes via `ifcopenshell.geom.create_shape()`.

The generated IFC is Bonsai-compatible — it can also be opened via
**File → Import → IFC**.

Requires ifckit in Blender's Python:

```python
import subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "ifckit[ifc]"], check=True)
```

---

## `build_hello_wall.py`

JSON-driven build: reads `hello_wall.json` and constructs walls with
openings, lining, and glazing via the JSON build pipeline.

[Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Fhello_wall.ifc)

---

## `build_sectioned_spine.py`

Five tests exercising the SectionedSpineBuilder internals:

- Basic straight spine (rectangular profile)
- Varying profiles along the spine
- I-beam section
- Transport vs fixed-ref frame comparison
- Inline vs core `transport_frames()` consistency

| File | Preview |
|------|---------|
| `test_sectioned_spine_basic.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Ftest_sectioned_spine_basic.ifc) |
| `test_sectioned_spine_varying.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Ftest_sectioned_spine_varying.ifc) |
| `test_sectioned_spine_ibeam.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Ftest_sectioned_spine_ibeam.ifc) |
| `test_sectioned_spine_transport.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Ftest_sectioned_spine_transport.ifc) |
| `test_sectioned_spine_comparison_inline.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Ftest_sectioned_spine_comparison_inline.ifc) |
| `test_sectioned_spine_comparison_core.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Ftest_sectioned_spine_comparison_core.ifc) |

---

## `sectioned_spine_demo.py`

Transport-frame sectioned spine with miter compensation on a 3-point
path.  Two variants: rectangular profile and I-beam.

| File | Preview |
|------|---------|
| `sectioned_spine_demo.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Fsectioned_spine_demo.ifc) |
| `sectioned_spine_demo_ibeam.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Fsectioned_spine_demo_ibeam.ifc) |

---

## `sectioned_spine_auto.py`

One-shot `build_from_spine()` API — auto-computes frames, miter scales,
and cross-sections from a single profile + starter plane.

| File | Preview |
|------|---------|
| `sectioned_spine_auto_rect.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Fsectioned_spine_auto_rect.ifc) |
| `sectioned_spine_auto_ibeam.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Fsectioned_spine_auto_ibeam.ifc) |

---

## `sectioned_spine_arc.py`

`Path.fillet()` API — filleted corners instead of manual arcs.
All spines built from `Path.from_pts([...])` + `fillet(index, radius)`.

| File | Preview |
|------|---------|
| `fillet_single_corner.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Ffillet_single_corner.ifc) |
| `fillet_line_arc_line.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Ffillet_line_arc_line.ifc) |
| `fillet_s_curve.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Ffillet_s_curve.ifc) |
| `fillet_multi_corner.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Ffillet_multi_corner.ifc) |

---

## `sectioned_spine_pipe.py`

Hollow (annular) cross-sections via `HollowCircleProfile`.  Demonstrates
correct inner barrel + annular end-cap tessellation.

| File | Preview |
|------|---------|
| `pipe_straight.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Fpipe_straight.ifc) |
| `pipe_bend.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Fpipe_bend.ifc) |
| `pipe_s_curve.ifc` | [Preview](https://maucworks.github.io/web-ifc-viewer/?ifc=https%3A%2F%2Fraw.githubusercontent.com%2Fmaucworks%2Fifckit%2Frefs%2Fheads%2Fmaster%2Fexamples%2Foutput%2Fpipe_s_curve.ifc) |
