# M8 — Path Convergentie: Implementatieplan

**Status:** TODO  
**Target commit:** `feat(geometry): Path as central 2D/3D primitive (M8)`  
**Doel:** `Path` wordt de centrale geometrie-primitief. Nieuwe classmethods, mutators, `offset()`, IFC-bridge via `to_profile_points()`.

---

## Leeswijzer voor uitvoerder

Dit document is zelfvoorzienend. Lees het van boven naar beneden. Elk onderdeel heeft:
- Exacte bestandsnaam + regelnummer (huidige staat)
- Wat te schrijven/wijzigen
- Tests die moeten slagen vóór je verder gaat

**Grondregel:** Na elke stap: `pytest tests/geometry/` groen. Nooit doorgaan met rood.

---

## Huidige staat codebase (referentie)

| Bestand | Inhoud relevant voor M8 |
|---|---|
| `ifckit/geometry/__init__.py` | `Path` (r.508–685), `Polyline` (r.436–505), `assemble_path` (r.783), `_polygon_normal`, `_signed_area` |
| `ifckit/builders/_geom.py` | `profile_from_points()`, `directrix_from_path()` |
| `tests/geometry/test_curves.py` | Bestaande Path/Polyline tests — mogen NIET breken |

### Relevante helpers die al bestaan (niet herschrijven)

```
_polygon_normal(pts: List[Vec]) -> Vec        # polygon normaal via cross product
_signed_area(pts: List[Vec], n: Vec) -> float # shoelace signed area
assemble_path(segments, tol=1e-9) -> List[Path]  # r.783
```

### Huidige `Path.__init__` (r.529)

```python
def __init__(self) -> None:
    self._segments: List[Line | Arc] = []
```

### Huidige `Path.is_planar` (r.601)

Heuristische check op Arc normals + collineaire Lines. Werkt goed maar kent
geen autoritatief `_plane` attribuut.

---

## Overzicht wijzigingen

```
Path.__init__          — voeg plane: Optional[Plane] = None toe
Path.is_closed         — nieuwe property
Path.is_planar         — uitbreiden: _plane authoritative check eerst
Path.from_pts()        — nieuwe classmethod
Path.rect()            — nieuwe classmethod  
Path.assemble()        — nieuwe classmethod (wrapper)
Path.close()           — nieuwe mutator
Path.make_planar()     — nieuwe mutator
Path.reverse()         — nieuwe mutator
Path.assert_ccw()      — nieuwe mutator
Path.duplicate()       — nieuwe method (returns new Path)
Path.offset()          — nieuwe method (returns new Path)
Path.to_profile_points() — nieuwe method

Polyline               — deprecated comment toevoegen
profile_from_points()  — Path accepteren als input
```

---

## STAP 1 — `Path.__init__` uitbreiden

**Bestand:** `ifckit/geometry/__init__.py`  
**Regel:** 529

### Wijziging

Vervang:
```python
def __init__(self) -> None:
    self._segments: List[Line | Arc] = []
```

Door:
```python
def __init__(self, plane: Optional["Plane"] = None) -> None:
    self._segments: List[Line | Arc] = []
    self._plane: Optional["Plane"] = plane
```

### Verificatie

`pytest tests/geometry/` moet nog steeds groen zijn — `__init__` signature
verandert maar `Path()` zonder argument werkt nog.

---

## STAP 2 — `is_planar` property uitbreiden

**Bestand:** `ifckit/geometry/__init__.py`  
**Regel:** 600–640 (huidige `is_planar`)

### Wijziging

Voeg vóór de bestaande heuristische logica een authoritative check in:

```python
@property
def is_planar(self) -> bool:
    """Check if all segments lie in the same plane.
    
    If a reference plane was set via __init__ or make_planar(),
    that plane is authoritative and True is returned immediately.
    Otherwise, falls back to heuristic checks on segment geometry.
    """
    # Authoritative: trust explicitly set plane
    if self._plane is not None:
        return True

    # --- rest van bestaande logica ongewijzigd ---
    if len(self._segments) <= 1:
        return True
    # ... (bestaande code)
```

### Verificatie

`pytest tests/geometry/` groen.

---

## STAP 3 — `is_closed` property

**Bestand:** `ifckit/geometry/__init__.py`  
**Locatie:** direct na `is_planar` property (na r.640)

### Code

```python
@property
def is_closed(self) -> bool:
    """True if the path's last endpoint equals its first startpoint."""
    if len(self._segments) < 2:
        return False
    sp = self.start_point()
    ep = self.end_point()
    if sp is None or ep is None:
        return False
    return sp.equals(ep, tol=1e-9)
```

**Let op:** `Vec.equals()` accepteert al een `tol` parameter — check in
`ifckit/geometry/__init__.py` dat de signatuur `equals(self, other, tol=1e-9)`
is. Als de signatuur anders is, pas de aanroep aan.

### Test (schrijf in `tests/geometry/test_path_extended.py`)

```python
def test_is_closed_false_open():
    p = Path()
    p.add_line(Vec(0,0,0), Vec(1,0,0))
    p.add_line(Vec(1,0,0), Vec(2,0,0))
    assert not p.is_closed

def test_is_closed_true():
    p = Path()
    p.add_line(Vec(0,0,0), Vec(1,0,0))
    p.add_line(Vec(1,0,0), Vec(0,0,0))
    assert p.is_closed

def test_is_closed_single_segment():
    p = Path()
    p.add_line(Vec(0,0,0), Vec(1,0,0))
    assert not p.is_closed
```

---

## STAP 4 — `from_pts()` classmethod

**Locatie:** Na `is_closed` property in de `Path` klasse.

### Code

```python
@classmethod
def from_pts(
    cls,
    pts: List["Vec"],
    plane: Optional["Plane"] = None,
    closed: bool = False,
) -> "Path":
    """Build a Path from a list of Vec points as consecutive Line segments.
    
    Args:
        pts:    List of at least 2 Vec points.
        plane:  Optional reference plane stored on the Path.
        closed: If True, appends a closing segment from pts[-1] to pts[0].
    
    Raises:
        ValueError: If fewer than 2 points are provided.
    """
    if len(pts) < 2:
        raise ValueError("from_pts requires at least 2 points")
    path = cls(plane=plane)
    for i in range(len(pts) - 1):
        path._segments.append(Line(pts[i], pts[i + 1]))
    if closed and not pts[-1].equals(pts[0], tol=1e-9):
        path._segments.append(Line(pts[-1], pts[0]))
    return path
```

### Tests

```python
def test_from_pts_open():
    pts = [Vec(0,0,0), Vec(1,0,0), Vec(2,0,0)]
    p = Path.from_pts(pts)
    assert len(p.segments) == 2
    assert not p.is_closed

def test_from_pts_closed():
    pts = [Vec(0,0,0), Vec(1,0,0), Vec(1,1,0), Vec(0,1,0)]
    p = Path.from_pts(pts, closed=True)
    assert len(p.segments) == 4
    assert p.is_closed

def test_from_pts_too_few_raises():
    with pytest.raises(ValueError):
        Path.from_pts([Vec(0,0,0)])

def test_from_pts_stores_plane():
    pl = Plane.world_xy()
    pts = [Vec(0,0,0), Vec(1,0,0)]
    p = Path.from_pts(pts, plane=pl)
    assert p._plane is pl
```

---

## STAP 5 — `rect()` classmethod

**Locatie:** Na `from_pts` classmethod.

### Algoritme

`p0` en `p1` zijn hoekpunten in **lokale plane-coördinaten** (2D, z wordt genegeerd).
De vier hoekpunten worden berekend in world-coördinaten via `plane.transform_point()`.

```
lokaal:        world:
p0 = (u0, v0)  A = plane.origin + u0*plane.x_axis + v0*plane.y_axis
p1 = (u1, v1)  B = plane.origin + u1*plane.x_axis + v0*plane.y_axis
               C = plane.origin + u1*plane.x_axis + v1*plane.y_axis
               D = plane.origin + u0*plane.x_axis + v1*plane.y_axis
```

Winding: A→B→C→D→A is CCW wanneer `plane.z_axis` omhoog wijst (standaard voor `Plane.world_xy()`).

### Code

Vóór implementatie: controleer hoe `Plane` punten transformeert. Zoek in
`ifckit/geometry/__init__.py` naar `class Plane` en verifieer:
- Heeft `Plane` een `x_axis` en `y_axis` attribuut?
- Of heet het `normal`, `x`, `y`?
- Is er een `transform_point()` method?

**Als Plane geen `x_axis`/`y_axis` heeft:** gebruik dan:
```python
# Bouw world-punt uit lokale coords:
world_pt = plane.origin + plane.x_axis * u + plane.y_axis * v
```
Pas de namen aan op wat er werkelijk in `Plane` zit.

```python
@classmethod
def rect(cls, plane: "Plane", p0: "Vec", p1: "Vec") -> "Path":
    """Build a closed rectangular Path in the given plane.
    
    p0 and p1 are corner points in LOCAL plane coordinates (z ignored).
    The result is a closed CCW path with 4 Line segments.
    self._plane is set to the given plane.
    
    Args:
        plane:  The reference plane. x_axis and y_axis define the 2D frame.
        p0:     First corner in local coords (u0, v0).
        p1:     Opposite corner in local coords (u1, v1).
    
    Returns:
        Closed Path with 4 segments, CCW winding relative to plane.z_axis.
    """
    u0, v0 = p0.x, p0.y
    u1, v1 = p1.x, p1.y
    # Build 4 world-space corners
    # Replace x_axis/y_axis with actual Plane attribute names if different
    A = plane.origin + plane.x_axis * u0 + plane.y_axis * v0
    B = plane.origin + plane.x_axis * u1 + plane.y_axis * v0
    C = plane.origin + plane.x_axis * u1 + plane.y_axis * v1
    D = plane.origin + plane.x_axis * u0 + plane.y_axis * v1
    pts = [A, B, C, D]
    path = cls(plane=plane)
    for i in range(4):
        path._segments.append(Line(pts[i], pts[(i + 1) % 4]))
    return path
```

### Tests

```python
def test_rect_is_closed():
    pl = Plane.world_xy()
    p = Path.rect(pl, Vec(0, 0, 0), Vec(4, 3, 0))
    assert p.is_closed
    assert len(p.segments) == 4

def test_rect_stores_plane():
    pl = Plane.world_xy()
    p = Path.rect(pl, Vec(0, 0, 0), Vec(1, 1, 0))
    assert p._plane is pl

def test_rect_world_coords():
    """Corners should be at expected world positions."""
    pl = Plane.world_xy()
    p = Path.rect(pl, Vec(0, 0, 0), Vec(4, 3, 0))
    # Collect unique points
    pts = [seg.start for seg in p.segments]
    xs = sorted(set(round(v.x, 9) for v in pts))
    ys = sorted(set(round(v.y, 9) for v in pts))
    assert xs == [0.0, 4.0]
    assert ys == [0.0, 3.0]

def test_rect_local_coords_offset_plane():
    """Rect on an offset plane — world coords shift accordingly."""
    from ifckit.geometry import Vec, Plane, Path
    pl = Plane(Vec(10, 0, 0), Vec(1, 0, 0), Vec(0, 0, 1))
    p = Path.rect(pl, Vec(0, 0, 0), Vec(2, 2, 0))
    pts = [seg.start for seg in p.segments]
    xs = sorted(set(round(v.x, 9) for v in pts))
    # origin is at x=10, so corners at x=10 and x=12
    assert xs == [10.0, 12.0]
```

---

## STAP 6 — `assemble()` classmethod

**Locatie:** Na `rect` classmethod.

### Code

```python
@classmethod
def assemble(
    cls,
    segments: "Sequence[Line | Arc]",
    tol: float = 1e-9,
) -> "List[Path]":
    """Assemble unordered segments into connected Paths.
    
    Thin wrapper around the module-level assemble_path() function.
    Returns a list because segments may form multiple disconnected paths.
    """
    return assemble_path(list(segments), tol=tol)
```

**Let op:** `assemble_path` is gedefinieerd in dezelfde module op r.783. De
classmethod kan die direct aanroepen — geen import nodig.

### Test

```python
def test_assemble_classmethod_matches_module_function():
    from ifckit.geometry import assemble_path
    segs = [
        Line(Vec(0,0,0), Vec(1,0,0)),
        Line(Vec(1,0,0), Vec(2,0,0)),
    ]
    via_classmethod = Path.assemble(segs)
    via_function = assemble_path(segs)
    assert len(via_classmethod) == len(via_function)
    assert len(via_classmethod[0].segments) == len(via_function[0].segments)
```

---

## STAP 7 — Mutators (return `self`)

**Locatie:** Na de classmethods, vóór `duplicate()`.

### 7a — `close()`

```python
def close(self) -> "Path":
    """Append a closing segment if not already closed. Returns self.
    
    No-op if already closed or fewer than 2 segments.
    """
    if self.is_closed or len(self._segments) < 1:
        return self
    sp = self.start_point()
    ep = self.end_point()
    if sp is not None and ep is not None and not ep.equals(sp, tol=1e-9):
        self._segments.append(Line(ep, sp))
    return self
```

### 7b — `reverse()`

Vóór implementatie: controleer of `Line` en `Arc` een `reverse()` of `reversed()`
method hebben in `ifckit/geometry/__init__.py`. Als ze dat niet hebben, implementeer
de flip inline:

```python
def reverse(self) -> "Path":
    """Reverse the order and direction of all segments. Returns self."""
    reversed_segs = []
    for seg in reversed(self._segments):
        if isinstance(seg, Line):
            reversed_segs.append(Line(seg.end, seg.start))
        else:  # Arc
            # Arc reversed: flip sign of angle, swap start to end
            # Arc(center, normal, start, angle) — start wordt het nieuwe startpunt
            # na flip: startpunt = huidig eindpunt, angle = -angle
            end_pt = seg.end  # Arc moet een .end property hebben
            reversed_segs.append(Arc(seg.center, seg.normal, end_pt, -seg.angle))
    self._segments = reversed_segs
    return self
```

**Let op:** Controleer of `Arc` een `.end` property heeft. Als niet, bereken:
```python
# Arc.end kan berekend worden uit center, normal, start, angle
# Zoek in de Arc class hoe end_point wordt berekend
```

### 7c — `make_planar()`

```python
def make_planar(self, plane: Optional["Plane"] = None) -> "Path":
    """Project all segment points onto the given plane. Returns self.
    
    Args:
        plane: The target plane. Falls back to self._plane if None.
    
    Raises:
        ValueError: If no plane is available.
    """
    target = plane or self._plane
    if target is None:
        raise ValueError(
            "make_planar() requires a plane argument or self._plane to be set"
        )
    new_segs = []
    for seg in self._segments:
        if isinstance(seg, Line):
            new_start = target.closest_point(seg.start)
            new_end = target.closest_point(seg.end)
            new_segs.append(Line(new_start, new_end))
        else:  # Arc — project center and start; keep normal = plane.normal
            new_center = target.closest_point(seg.center)
            new_start = target.closest_point(seg.start)
            new_segs.append(Arc(new_center, target.z_axis, new_start, seg.angle))
    self._segments = new_segs
    self._plane = target
    return self
```

**Let op:** Controleer of `Plane` een `closest_point()` method heeft en hoe
`plane.z_axis` / `plane.normal` heet. Pas namen aan als nodig.

### 7d — `assert_ccw()`

```python
def assert_ccw(self, normal: Optional["Vec"] = None) -> "Path":
    """Ensure CCW winding relative to normal. Reverses if CW. Returns self.
    
    Requires is_closed == True.
    
    Args:
        normal: Reference normal. Defaults to self._plane.z_axis or self.normal.
    
    Raises:
        ValueError: If path is not closed.
    """
    if not self.is_closed:
        raise ValueError("assert_ccw() requires a closed path")
    n = normal
    if n is None and self._plane is not None:
        n = self._plane.z_axis   # of hoe de z-as heet op Plane
    if n is None:
        n = self.normal
    if n is None:
        raise ValueError("Cannot determine normal for CCW check")
    pts = [seg.start for seg in self._segments]
    if _signed_area(pts, n) < 0:
        self.reverse()
    return self
```

**Let op:** `_signed_area` is al aanwezig in de module. `self.normal` is al
geïmplementeerd op de bestaande `Path` klasse (r.643).

### Tests voor mutators

```python
def test_close_appends_segment():
    p = Path.from_pts([Vec(0,0,0), Vec(1,0,0), Vec(1,1,0)])
    assert not p.is_closed
    result = p.close()
    assert result is p  # mutator returns self
    assert p.is_closed

def test_close_noop_if_already_closed():
    p = Path.from_pts([Vec(0,0,0), Vec(1,0,0), Vec(0,0,0)])
    n_before = len(p.segments)
    p.close()
    assert len(p.segments) == n_before

def test_reverse_mutates():
    p = Path.from_pts([Vec(0,0,0), Vec(1,0,0), Vec(2,0,0)])
    p.reverse()
    assert p.start_point().equals(Vec(2,0,0))
    assert p.end_point().equals(Vec(0,0,0))

def test_reverse_returns_self():
    p = Path.from_pts([Vec(0,0,0), Vec(1,0,0)])
    assert p.reverse() is p

def test_make_planar_raises_without_plane():
    p = Path.from_pts([Vec(0,0,0), Vec(1,0,0)])
    with pytest.raises(ValueError):
        p.make_planar()

def test_make_planar_projects_points():
    pl = Plane.world_xy()  # z=0 plane
    p = Path.from_pts([Vec(0,0,5), Vec(1,0,3)])
    p.make_planar(plane=pl)
    for seg in p.segments:
        assert abs(seg.start.z) < 1e-9
        assert abs(seg.end.z) < 1e-9

def test_assert_ccw_noop_on_ccw():
    pl = Plane.world_xy()
    # CCW rect: A(0,0)→B(1,0)→C(1,1)→D(0,1)→A
    p = Path.rect(pl, Vec(0,0,0), Vec(1,1,0))
    pts_before = [seg.start for seg in p.segments]
    p.assert_ccw()
    pts_after = [seg.start for seg in p.segments]
    for a, b in zip(pts_before, pts_after):
        assert a.equals(b)

def test_assert_ccw_flips_cw():
    pl = Plane.world_xy()
    # CW: reverse a CCW rect
    p = Path.rect(pl, Vec(0,0,0), Vec(1,1,0))
    p.reverse()  # now CW
    p.assert_ccw()
    # After assert_ccw, should be CCW again
    pts = [seg.start for seg in p.segments]
    from ifckit.geometry import _signed_area, _polygon_normal
    n = _polygon_normal(pts)
    area = _signed_area(pts, n)
    assert area > 0

def test_assert_ccw_raises_on_open():
    p = Path.from_pts([Vec(0,0,0), Vec(1,0,0)])
    with pytest.raises(ValueError):
        p.assert_ccw()
```

---

## STAP 8 — `duplicate()` method

**Locatie:** Na mutators.

### Code

```python
def duplicate(self) -> "Path":
    """Return a deep copy of this Path. Changes to the copy do not affect the original."""
    import copy
    new_path = Path(plane=self._plane)  # _plane is immutable Plane, shallow ok
    new_path._segments = [copy.copy(seg) for seg in self._segments]
    return new_path
```

**Let op:** `Line` en `Arc` zijn value-types (immutable). `copy.copy()` is
voldoende. Als ze mutable zijn, gebruik `copy.deepcopy()`.

### Test

```python
def test_duplicate_is_independent():
    p = Path.from_pts([Vec(0,0,0), Vec(1,0,0), Vec(2,0,0)])
    q = p.duplicate()
    q.add_line(Vec(2,0,0), Vec(3,0,0))
    assert len(p.segments) == 2
    assert len(q.segments) == 3
```

---

## STAP 9 — `offset()` method

**Locatie:** Na `duplicate()`.

### Preconditions

- `is_closed == True`
- Alle segmenten zijn `Line` (geen `Arc`)
- `dist > 0` (inward offset)

### Algoritme

```
Input: gesloten convex polygoon, dist > 0

1. Bepaal inward normaal per zijde:
   seg_dir = (B - A).normalized()
   pad_normal = self._plane.z_axis of self.normal
   inward_n = (pad_normal ** seg_dir).normalized()
   
   ** = cross product (Vec heeft ** operator voor cross)
   
2. Verschuif elke lijn inward:
   A' = A + inward_n * dist
   B' = B + inward_n * dist
   (opslaan als lijst van (A', direction) per zijde)
   
3. Bereken nieuwe hoekpunten als lijn-lijn intersecties:
   Voor hoekpunt i: intersectie van verschoven lijn[i-1] en verschoven lijn[i]
   
   Lijn-lijn intersectie in 3D (coplanaire lijnen):
   P = A'_prev + t * dir_prev
   Q = A'_curr + s * dir_curr
   Oplossen voor t: gebruik kleinste-kwadraten of analytisch voor 2D
   
4. Bouw nieuwe Path.from_pts(nieuwe_punten, plane=self._plane, closed=True)
```

### Lijn-lijn intersectie helper (privé, in module)

Voeg toe onder de `Path` klasse definitie, vóór `assemble_path`:

```python
def _line_line_intersect_2d(
    p1: "Vec", d1: "Vec", p2: "Vec", d2: "Vec"
) -> Optional["Vec"]:
    """Find intersection of two lines in the XY plane.
    
    Lines defined as P = p1 + t*d1 and Q = p2 + s*d2.
    Returns the intersection point, or None if lines are parallel.
    Works in 2D (x,y) — z of result is taken from p1.
    """
    # Solve: p1 + t*d1 = p2 + s*d2
    # d1.x * t - d2.x * s = p2.x - p1.x
    # d1.y * t - d2.y * s = p2.y - p1.y
    denom = d1.x * (-d2.y) - d1.y * (-d2.x)
    if abs(denom) < 1e-12:
        return None  # parallel
    dx = p2.x - p1.x
    dy = p2.y - p1.y
    t = (dx * (-d2.y) - dy * (-d2.x)) / denom
    return Vec(p1.x + t * d1.x, p1.y + t * d1.y, p1.z + t * d1.z)
```

### `offset()` code

```python
def offset(self, dist: float) -> "Path":
    """Return a new inward-offset Path at distance dist.
    
    Only works for closed paths made entirely of Line segments.
    Only correct for convex polygons in v1.
    
    Args:
        dist: Offset distance (positive = inward).
    
    Returns:
        New Path with offset geometry. self is not modified.
    
    Raises:
        ValueError: If path is not closed.
        ValueError: If any segment is an Arc.
        ValueError: If offset causes degenerate geometry (non-convex).
    """
    if not self.is_closed:
        raise ValueError("offset() requires a closed path")
    for seg in self._segments:
        if isinstance(seg, Arc):
            raise ValueError("offset() does not support Arc segments in v1")
    
    # Determine plane normal for inward direction
    n = None
    if self._plane is not None:
        n = self._plane.z_axis  # of hoe z_axis heet op Plane — controleer!
    if n is None:
        n = self.normal
    if n is None:
        raise ValueError("Cannot determine plane normal for offset")
    
    # Collect directed lines (all Lines guaranteed by check above)
    segs = self._segments  # all Line
    
    # Step 1: compute inward normal and shifted line anchor per segment
    shifted = []  # list of (anchor_point, direction)
    for seg in segs:
        direction = (seg.end - seg.start).normalized()
        inward_n = (n ** direction).normalized()  # cross product
        anchor = Vec(
            seg.start.x + inward_n.x * dist,
            seg.start.y + inward_n.y * dist,
            seg.start.z + inward_n.z * dist,
        )
        shifted.append((anchor, direction))
    
    # Step 2: compute new corner points as intersections of adjacent shifted lines
    new_pts = []
    n_segs = len(shifted)
    for i in range(n_segs):
        prev_i = (i - 1) % n_segs
        p1, d1 = shifted[prev_i]
        p2, d2 = shifted[i]
        pt = _line_line_intersect_2d(p1, d1, p2, d2)
        if pt is None:
            raise ValueError(
                f"offset(): parallel adjacent edges at corner {i} — "
                "path may be degenerate or dist too large"
            )
        new_pts.append(pt)
    
    return Path.from_pts(new_pts, plane=self._plane, closed=True)
```

### Tests

```python
def test_offset_rect():
    """1000x1000 rect offset 55 → 890x890."""
    pl = Plane.world_xy()
    p = Path.rect(pl, Vec(0, 0, 0), Vec(1000, 1000, 0))
    q = p.offset(55)
    assert q.is_closed
    pts = [seg.start for seg in q.segments]
    xs = sorted(set(round(v.x, 6) for v in pts))
    ys = sorted(set(round(v.y, 6) for v in pts))
    assert abs(xs[0] - 55) < 1e-6
    assert abs(xs[1] - 945) < 1e-6
    assert abs(ys[0] - 55) < 1e-6
    assert abs(ys[1] - 945) < 1e-6

def test_offset_raises_open():
    p = Path.from_pts([Vec(0,0,0), Vec(1,0,0), Vec(2,0,0)])
    with pytest.raises(ValueError, match="closed"):
        p.offset(10)

def test_offset_raises_arc():
    p = Path()
    from ifckit.geometry import Arc
    p._segments.append(Arc(Vec(0,0,0), Vec(0,0,1), Vec(1,0,0), 90))
    # Manually close by adding line
    p._segments.append(Line(p.end_point(), p.start_point()))
    with pytest.raises(ValueError, match="Arc"):
        p.offset(10)

def test_offset_does_not_mutate_original():
    pl = Plane.world_xy()
    p = Path.rect(pl, Vec(0, 0, 0), Vec(100, 100, 0))
    pts_before = [seg.start for seg in p.segments]
    p.offset(10)
    pts_after = [seg.start for seg in p.segments]
    for a, b in zip(pts_before, pts_after):
        assert a.equals(b)
```

---

## STAP 10 — `to_profile_points()` method

**Locatie:** Na `offset()` in de `Path` klasse.

### Doel

Converteert een gesloten, planaire `Path` naar een lijst van 2D tuples
`(x, y)` in lokale plane-coördinaten — klaar voor `profile_from_points()`.

### Code

```python
def to_profile_points(
    self,
    plane: Optional["Plane"] = None,
) -> "List[Tuple[float, float]]":
    """Convert a closed planar Path to 2D profile points in local plane coords.
    
    Arc segments are sampled to polyline approximation before projection.
    
    Args:
        plane: Reference plane for 2D projection.
               Falls back to self._plane if not provided.
    
    Returns:
        List of (x, y) tuples in local plane coordinates.
    
    Raises:
        ValueError: If path is not closed.
        ValueError: If no plane is available.
    """
    if not self.is_closed:
        raise ValueError("to_profile_points() requires a closed path")
    target = plane or self._plane
    if target is None:
        raise ValueError(
            "to_profile_points() requires a plane argument or self._plane to be set"
        )
    
    # Collect world-space points (deduplicated at joints)
    world_pts: List["Vec"] = []
    for seg in self._segments:
        if isinstance(seg, Arc):
            seg_pts = seg.sample()  # sample() returns list of Vec
        else:
            seg_pts = [seg.start, seg.end]
        if world_pts and world_pts[-1].equals(seg_pts[0], tol=1e-9):
            seg_pts = seg_pts[1:]
        world_pts.extend(seg_pts)
    
    # Remove duplicate closing point if present
    if len(world_pts) >= 2 and world_pts[0].equals(world_pts[-1], tol=1e-9):
        world_pts = world_pts[:-1]
    
    # Project to local 2D coords via plane
    # plane.to_local(pt) -> (u, v) or plane.project_point(pt) -> (u, v)
    # CONTROLEER welke method Plane heeft voor 2D projectie.
    # Alternatief: handmatige projectie:
    #   u = (pt - plane.origin) . plane.x_axis
    #   v = (pt - plane.origin) . plane.y_axis
    result = []
    for pt in world_pts:
        delta = pt - target.origin
        u = delta @ target.x_axis   # dot product — controleer operator
        v = delta @ target.y_axis
        result.append((u, v))
    
    return result
```

**Let op:** Controleer in de `Plane` klasse:
- Attribuutnamen: `origin`, `x_axis`, `y_axis`, `z_axis`
- Of `Vec` de `@` operator heeft voor dot product (`__matmul__`)
- Of `Vec` de `-` operator heeft (`__sub__`)

### Tests

```python
def test_to_profile_points_square():
    pl = Plane.world_xy()
    p = Path.rect(pl, Vec(0, 0, 0), Vec(4, 3, 0))
    pts = p.to_profile_points()
    assert len(pts) == 4
    xs = sorted(set(round(x, 6) for x, y in pts))
    ys = sorted(set(round(y, 6) for x, y in pts))
    assert xs == [0.0, 4.0]
    assert ys == [0.0, 3.0]

def test_to_profile_points_raises_open():
    p = Path.from_pts([Vec(0,0,0), Vec(1,0,0)])
    with pytest.raises(ValueError, match="closed"):
        p.to_profile_points(plane=Plane.world_xy())

def test_to_profile_points_raises_no_plane():
    pts = [Vec(0,0,0), Vec(1,0,0), Vec(1,1,0), Vec(0,1,0)]
    p = Path.from_pts(pts, closed=True)
    with pytest.raises(ValueError):
        p.to_profile_points()
```

---

## STAP 11 — `Polyline` deprecated comment

**Bestand:** `ifckit/geometry/__init__.py`  
**Regel:** 436

### Wijziging

Vervang de bestaande docstring:
```python
class Polyline:
    """An ordered sequence of "Vec" points forming a polyline."""
```

Door:
```python
class Polyline:
    """An ordered sequence of "Vec" points forming a polyline.

    .. deprecated::
        Use :class:`Path` instead. ``Polyline`` is retained for backward
        compatibility with existing callers (``sample()``, bridge builder, etc.)
        and will be removed in a future version.
    """
```

---

## STAP 12 — `profile_from_points()` aanpassen

**Bestand:** `ifckit/builders/_geom.py`

### Eerst: lees de huidige signature

Zoek `def profile_from_points` in `ifckit/builders/_geom.py` en noteer de
exacte signature en body vóór je wijzigt.

### Wijziging

Voeg bovenin de functie-body een `isinstance` check toe:

```python
def profile_from_points(f, points_2d_or_path, ...):  # signature ongewijzigd
    # NEW: accept Path as input
    from ifckit.geometry import Path
    if isinstance(points_2d_or_path, Path):
        points_2d_or_path = points_2d_or_path.to_profile_points()
    # rest van body ongewijzigd
    ...
```

### Test

```python
def test_profile_from_path_gives_ifc_profile(ifc4_model):
    """Path → profile_from_points → IfcArbitraryClosedProfileDef."""
    import ifcopenshell
    from ifckit.geometry import Vec, Plane, Path
    from ifckit.builders._geom import profile_from_points
    
    f = ifc4_model._f  # of hoe je aan het ifcopenshell File object komt
    pl = Plane.world_xy()
    path = Path.rect(pl, Vec(0, 0, 0), Vec(0.3, 3.0, 0))
    
    profile = profile_from_points(f, path)
    assert profile.is_a("IfcArbitraryClosedProfileDef")
```

**Let op:** Pas `ifc4_model._f` aan naar de werkelijke API van `IfcModel` om
aan het ifcopenshell file-object te komen. Zoek dit op in `ifckit/model.py`.

---

## STAP 13 — Testbestand aanmaken

**Bestand:** `tests/geometry/test_path_extended.py`

Schrijf alle tests uit Stap 3 t/m 12 in dit bestand. Structuur:

```python
"""Tests for extended Path functionality (M8)."""
import pytest
from ifckit.geometry import Vec, Plane, Path, Line, Arc

# --- is_closed ---
# (tests uit stap 3)

# --- from_pts ---
# (tests uit stap 4)

# --- rect ---
# (tests uit stap 5)

# --- assemble classmethod ---
# (tests uit stap 6)

# --- mutators ---
# (tests uit stap 7)

# --- duplicate ---
# (tests uit stap 8)

# --- offset ---
# (tests uit stap 9)

# --- to_profile_points ---
# (tests uit stap 10)
```

---

## STAP 14 — Integratie-test IFC profile

**Bestand:** `tests/builders/test_path_to_profile.py` (nieuw)

```python
"""Integration test: Path → IFC profile."""
import pytest

def test_path_rect_to_ifc_profile():
    """Full chain: Path.rect() → profile_from_points() → IfcArbitraryClosedProfileDef."""
    import ifcopenshell
    from ifckit.geometry import Vec, Plane, Path
    from ifckit.builders._geom import profile_from_points
    
    f = ifcopenshell.file(schema="IFC4")
    pl = Plane.world_xy()
    path = Path.rect(pl, Vec(0, 0, 0), Vec(0.3, 3.0, 0))
    
    profile = profile_from_points(f, path)
    
    assert profile.is_a("IfcArbitraryClosedProfileDef")
    outer = profile.OuterCurve
    assert outer is not None
```

---

## Checklist (uitvoerder)

Werk deze lijst af van boven naar beneden. Markeer elke stap met `[x]` als klaar.

- [ ] **STAP 1** — `Path.__init__` plane arg
- [ ] **STAP 2** — `is_planar` authoritative check
- [ ] **STAP 3** — `is_closed` property + tests
- [ ] **STAP 4** — `from_pts()` classmethod + tests
- [ ] **STAP 5** — `rect()` classmethod + tests (controleer Plane attrs eerst!)
- [ ] **STAP 6** — `assemble()` classmethod + test
- [ ] **STAP 7** — mutators (`close`, `reverse`, `make_planar`, `assert_ccw`) + tests
- [ ] **STAP 8** — `duplicate()` + test
- [ ] **STAP 9** — `_line_line_intersect_2d()` helper + `offset()` + tests
- [ ] **STAP 10** — `to_profile_points()` + tests (controleer Plane attrs!)
- [ ] **STAP 11** — `Polyline` deprecated comment
- [ ] **STAP 12** — `profile_from_points()` aanpassen + test
- [ ] **STAP 13** — Testbestand `tests/geometry/test_path_extended.py` compleet
- [ ] **STAP 14** — Integratie-test `tests/builders/test_path_to_profile.py`
- [ ] **FINAL** — `pytest` volledig groen, geen regressies in bestaande tests

---

## Valkuilen & Aandachtspunten

### Plane attribuutnamen
Vóór Stap 5 en 10: lees de `Plane` class in `ifckit/geometry/__init__.py` en
noteer exact:
- Hoe heet de x-as? (`x_axis`? `x`? `basis_x`?)
- Hoe heet de y-as?
- Hoe heet de z-as / normaal?
- Is er een `closest_point()` method?
- Is er een `z_axis` property of is het `normal`?

### Vec operators
- Cross product: `Vec.__xor__` (`**`) of `Vec.cross()`?
- Dot product: `Vec.__matmul__` (`@`) of `Vec.dot()`?
- Subtractie: `Vec.__sub__` (`-`)?

Zoek dit op vóór je Stap 9 en 10 implementeert.

### `Arc.end` property
`offset()` en `reverse()` hebben `Arc.end` nodig. Controleer of die bestaat.
Als `Arc` alleen `.start` en `.angle` heeft, bereken `end` uit de Arc-wiskunde
of gebruik `seg.sample()[-1]`.

### `Vec.equals()` tol parameter
Controleer de exacte signature: `equals(self, other, tol=1e-9)` of
`equals(self, other)` met vaste tolerantie. Pas aanroepen aan.

### Bestaande tests mogen NIET breken
`tests/geometry/test_curves.py` bevat bestaande Path tests. Run deze na elke
stap. Als ze breken, herstel vóór je doorgaat.

---

## Definition of Done — M8

1. Alle 14 stappen afgevinkt
2. `pytest tests/` volledig groen (0 failures, 0 errors)
3. `pytest tests/geometry/test_curves.py` groen (geen regressies)
4. `ruff check ifckit/` geen fouten
5. Coverage `tests/geometry/` ≥ 100%
6. Commit: `feat(geometry): Path as central 2D/3D primitive (M8)`
