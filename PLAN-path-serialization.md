# Plan: Path + PendingWallGraph serialization (to_dict/from_dict)

## Overzicht

`PendingWallGraph` in path-mode (geconstrueerd met `path=Path(...)`) kan niet serializen naar dict.
`to_dict()` raise `NotImplementedError`. `from_dict()` accepteert alleen edge-mode.
Dit blokkeert de dict roundtrip die de A320 configurator gebruikt voor export.

**Oorzaak:** `Line`, `Arc`, en `Path` hebben geen `to_dict()`/`from_dict()` methoden.

---

## 1. `primitives.py` — `Line.to_dict()` + `Arc.to_dict()`

### `Line.to_dict()`

```python
def to_dict(self) -> dict[str, Any]:
    return {"type": "line", "start": self.start.to_dict(), "end": self.end.to_dict()}
```

### `Line.from_dict()`

```python
@classmethod
def from_dict(cls, d: dict[str, Any]) -> Line:
    return cls(Vec.from_dict(d["start"]), Vec.from_dict(d["end"]))
```

### `Arc.to_dict()`

```python
def to_dict(self) -> dict[str, Any]:
    return {
        "type": "arc",
        "center": self.center.to_dict(),
        "normal": self.normal.to_dict(),
        "start": self.start.to_dict(),
        "angle": self.angle,
    }
```

### `Arc.from_dict()`

```python
@classmethod
def from_dict(cls, d: dict[str, Any]) -> Arc:
    return cls(
        Vec.from_dict(d["center"]),
        Vec.from_dict(d["normal"]),
        Vec.from_dict(d["start"]),
        d["angle"],
    )
```

---

## 2. `path.py` — `Path.to_dict()` + `Path.from_dict()`

### `Path.to_dict()`

```python
def to_dict(self) -> dict[str, Any]:
    return {
        "plane": self._plane.to_dict() if self._plane else None,
        "segments": [s.to_dict() for s in self._segments],
        "holes": [h.to_dict() for h in self._holes],
    }
```

### `Path.from_dict()`

```python
@classmethod
def from_dict(cls, d: dict[str, Any]) -> Path:
    from ifckit.geometry.primitives import Line, Arc, Plane

    plane = Plane.from_dict(d["plane"]) if d.get("plane") else None
    path = cls(plane=plane)

    for sd in d.get("segments", []):
        if sd["type"] == "line":
            path._segments.append(Line.from_dict(sd))
        elif sd["type"] == "arc":
            path._segments.append(Arc.from_dict(sd))

    for hd in d.get("holes", []):
        hole = cls.from_dict(hd)
        path._holes.append(hole)

    return path
```

---

## 3. `wall_graph.py` — `PendingWallGraph.to_dict()` + `from_dict()` uitbreiden

### `to_dict()` — path-mode toevoegen

```python
def to_dict(self) -> dict[str, Any]:
    d: dict[str, Any] = {
        "type": self.element_type,
        "name": self.name,
        "thickness": self.thickness,
        "height": self.height,
    }
    if self.from_path and self._path is not None:
        d["mode"] = "path"
        d["path"] = self._path.to_dict()
        d["angle_step_deg"] = self.angle_step_deg
    else:
        d["mode"] = "edge"
        d["vertices"] = [v.to_dict() for v in self.vertices]
        d["edges"] = [(int(a), int(b)) for a, b in self.edges]
        d["plane"] = self.plane.to_dict()
    return d
```

### `from_dict()` — path-mode toevoegen

```python
@classmethod
def from_dict(cls, d: dict[str, Any]) -> PendingWallGraph:
    from ifckit.geometry.path import Path

    if d.get("mode") == "path":
        return cls(
            path=Path.from_dict(d["path"]),
            thickness=float(d.get("thickness", 200)),
            height=float(d.get("height", 3000)),
            name=d.get("name", ""),
            angle_step_deg=float(d.get("angle_step_deg", 5.0)),
        )

    # Fallback: edge mode (backward compat)
    verts = [Vec(*p) for p in d.get("vertices", [])]
    edges = [(int(a), int(b)) for a, b in d.get("edges", [])]
    plane = Plane.from_dict(d.get("plane", {}))
    return cls(
        vertices=verts,
        edges=edges,
        plane=plane,
        thickness=float(d.get("thickness", 200)),
        height=float(d.get("height", 3000)),
        name=d.get("name", ""),
    )
```

### `__init__()` — `_path` als public property

Optioneel: maak `_path` bereikbaar als `path` property zodat serializatie consistent werkt:

```python
@property
def path(self) -> Path | None:
    return self._path
```

---

## 4. Testen

### Roundtrip test (path-mode)

```python
from ifckit.geometry import Vec, Path, Plane
from ifckit.elements.wall_graph import PendingWallGraph

# Build path with fillet + hole
outer = Path.from_pts(
    [Vec(0, 0, 0), Vec(4000, 0, 0), Vec(4000, 3000, 0), Vec(0, 3000, 0)],
    plane=Plane.world_xy(),
    closed=True,
)
outer.fillet([0, 1, 2, 3], 800)

inner = outer.offset(200)
path = outer.with_hole(inner)

# Original
w1 = PendingWallGraph(path=path, thickness=200, height=3000)

# Roundtrip
d = w1.to_dict()          # zou moeten werken
w2 = PendingWallGraph.from_dict(d)  # zou moeten werken

assert w2.thickness == 200
assert w2.height == 3000
assert w2.from_path is True
assert w2._path is not None
assert w2._path.is_closed is True
assert len(w2._path._holes) == 1
```

### Backward compat test (edge-mode)

Bestaande edge-mode dicts (zonder `mode` veld) moeten nog steeds werken via `from_dict()`.

---

## 5. Volgorde

| Stap | Bestand | Wat |
|---|---|---|
| 1 | `primitives.py` | `Line.to_dict()`, `Line.from_dict()`, `Arc.to_dict()`, `Arc.from_dict()` |
| 2 | `path.py` | `Path.to_dict()`, `Path.from_dict()` |
| 3 | `wall_graph.py` | `PendingWallGraph.to_dict()` + `from_dict()` uitbreiden met path-mode |
| 4 | Test | Roundtrip test + backward compat |
| 5 | `../A320-ifc-configurator` | `dispatch.py` `wall_graph` registreren, `_serialize_element` fallback verwijderen |
