# Plan: `to_mesh_dict()` — generieke geometrie visualisatie voor Path/Curve/Surface

## Waarom

ifckit model `model.py` maakt geometrie aan: `Path` voor centerlines, `Curve` voor
NURBS profielen, `Surface` voor vlakken. Deze hulpgeometrie is onzichtbaar in de
3D viewer omdat het alleen via de IFC build pipeline loopt (`storey.add()`).

Doel: een generieke dict-serialisatie voor Path, Curve en Surface die een
willekeurige 3D viewer (Three.js, Babylon, WebGPU) kan consumeren om de
geometrie als hulplijnen/vlakken te renderen — buiten de IFC build loop om.

## Output formaat — `to_mesh_dict()`

Universeel mesh/line formaat, niet gebonden aan een specifieke viewer.

```python
{
    "primitive": "line-loop" | "line-strip" | "triangles",
    "positions": [x, y, z,  x, y, z,  ...],  # flat float array (Vec compat)
    "indices":   [i, j, k,  i, j, k,  ...],  # optioneel, alleen voor triangles
    "closed":    True | False,               # optioneel, alleen voor lines
    "label":     "centerline",               # display naam
    "material":  {                           # optioneel — zie onder
        "color": "#FF6600",
        "opacity": 0.8,
        "line_width": 2,
    },
}
```

| `primitive` | Betekent | Drie.js constructie |
|---|---|---|
| `line-loop` | Gesloten polygoon | `THREE.LineLoop` |
| `line-strip` | Open polylijn | `THREE.Line` |
| `triangles` | Triangle mesh | `THREE.Mesh` met index buffer |

## API

### `Path.to_mesh_dict(angle_step_deg=5.0, label="", material=None)`

```python
def to_mesh_dict(
    self,
    angle_step_deg: float = 5.0,   # sample resolutie
    label: str = "",
    material: dict | None = None,   # visuele eigenschappen
) -> dict:
    poly = self.sample(angle_step_deg)
    pts = poly.points  # List[Vec]
    d: dict = {
        "primitive": "line-loop" if self.is_closed else "line-strip",
        "positions": [v.x, v.y, v.z for v in pts],
        "closed": self.is_closed,
        "label": label or "Path",
    }
    if material:
        d["material"] = material
    return d
```

### `Curve.to_mesh_dict(n_points=50, label="", material=None)`

```python
def to_mesh_dict(
    self,
    n_points: int = 50,       # aantal uniforme samples in [0, 1]
    label: str = "",
    material: dict | None = None,
) -> dict:
    pts = [self.point_at(t) for t in np.linspace(0, 1, n_points)]
    d: dict = {
        "primitive": "line-strip",
        "positions": [v.x, v.y, v.z for v in pts],
        "label": label or "Curve",
    }
    if material:
        d["material"] = material
    return d
```

### `Surface.to_mesh_dict(nu=20, nv=20, label="", material=None)`

Surface heeft nog geen `point_at(u, v)` methode. Die moet eerst toegevoegd worden.

```python
def point_at(self, u: float, v: float) -> Vec:
    """Evaluate point at normalised surface parameters (u, v) ∈ [0, 1]."""
    # NURBS surface evaluatie via tensor product basis
    ...

def to_mesh_dict(
    self,
    nu: int = 20,             # samples in U richting
    nv: int = 20,             # samples in V richting
    label: str = "",
    material: dict | None = None,
) -> dict:
    vertices: list[Vec] = []
    indices: list[int] = []
    for iu in range(nu):
        for iv in range(nv):
            u = iu / (nu - 1)
            v = iv / (nv - 1)
            vertices.append(self.point_at(u, v))
    # Grid indices: 2 triangles per quad
    for iu in range(nu - 1):
        for iv in range(nv - 1):
            i0 = iu * nv + iv
            i1 = iu * nv + iv + 1
            i2 = (iu + 1) * nv + iv
            i3 = (iu + 1) * nv + iv + 1
            indices.extend([i0, i1, i2,  i1, i3, i2])  # 2 triangles
    return {
        "primitive": "triangles",
        "positions": [v.x, v.y, v.z for v in vertices],
        "indices": indices,
        "label": label or "Surface",
        "material": material,
    }
```

## materiaal properties (optioneel)

De `material` dict wordt door de frontend gelezen en toegepast op het Three.js
object. Voorbeeld:

```python
muur.to_mesh_dict(
    label="centerline",
    material={
        "color": "#FF6600",
        "opacity": 0.8,
        "line_width": 2,
        "emissive": "#FF3300",
        "transparent": False,
    },
)
```

Mogelijke properties:

| Key | Type | Default | Werkt op |
|---|---|---|---|
| `color` | str (hex) | `"#FF6600"` | lijn + vlak |
| `opacity` | float 0-1 | `1.0` | lijn + vlak |
| `line_width` | int | `1` | lijn |
| `emissive` | str (hex) | — | vlak |
| `transparent` | bool | `False` | vlak |
| `side` | `"front"` / `"back"` / `"double"` | `"double"` | vlak |
| `dashed` | bool | `False` | lijn |
| `dash_size` | float | `1` | lijn (als dashed) |
| `gap_size` | float | `1` | lijn (als dashed) |

## Gebruik in model.py

```python
def run(breedte, diepte, radius, hoogte, dikte, number):
    centerline = Path.from_pts([...], plane=Plane.world_xy(), closed=True)
    centerline.fillet([0, 1, 2, 3], radius)

    muur = PendingWallGraph(path=centerline, ...)
    res = [{"element": muur, "id": "muur-1"}]

    # Helpers voor visualisatie
    res.append({
        "__type__": "mesh",
        **centerline.to_mesh_dict(label="centerline"),
    })

    return res
```

## Frontend consumptie (geom-vis.ts)

```typescript
type MeshDict = {
  primitive: 'line-loop' | 'line-strip' | 'triangles';
  positions: number[];
  indices?: number[];
  closed?: boolean;
  label?: string;
  material?: {
    color?: string;
    opacity?: number;
    line_width?: number;
    emissive?: string;
    transparent?: boolean;
    side?: 'front' | 'back' | 'double';
    dashed?: boolean;
    dash_size?: number;
    gap_size?: number;
  };
};
```

De Three.js constructie wordt aangestuurd door `primitive`:

```typescript
function meshDictToThree(data: MeshDict): THREE.Object3D {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(data.positions, 3));
  if (data.indices) geo.setIndex(data.indices);

  const mat = materialFromDict(data.material);

  switch (data.primitive) {
    case 'line-loop': return new THREE.LineLoop(geo, mat);
    case 'line-strip': return new THREE.Line(geo, mat);
    case 'triangles': {
      const mesh = new THREE.Mesh(geo, mat);
      // Optioneel wireframe overlay
      return mesh;
    }
  }
}
```

## Volgorde van implementatie in ifckit

| Stap | Bestand | Toevoeging |
|---|---|---|
| 1 | `ifckit/geometry/path.py` | `Path.to_mesh_dict()` |
| 2 | `ifckit/geometry/curve.py` | `Curve.sample(n_points)` + `Curve.to_mesh_dict()` |
| 3 | `ifckit/geometry/surface.py` | `Surface.point_at(u,v)` + `Surface.to_mesh_dict()` |
| 4 | Test | Test roundtrip: `to_mesh_dict()` → dict → Three.js constructie |
| 5 | Metadata | `material:` opties implementeren |
