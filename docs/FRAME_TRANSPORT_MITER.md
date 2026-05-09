# Frame Transport & Miter Scaling

*Algorithms for consistent cross-section orientation and miter compensation along a 3D spine path.*

## Core Pattern

The frame+scaling pipeline has three independent concerns that can be mixed and matched:

```
points → frame_strategy(points, direction) → FrameField(.frames, .scales)
  ├── .frames:  List[Plane] — one per vertex, Z = path tangent/bisector
  └── .scales:  List[(float, str)] — (scale, axis) per vertex;  axis is "x", "y", or ""
```

Then:

```
frames → _unflip_frames(points, frames) → corrected List[Plane]
frames + scales → build profiles with miter scaling → PendingSectionedSpine → IFC
```

All three frame strategies share this return type. Any geometry function that needs
consistent orientation along a path can use `FrameField` and the unflip pass.

---

## Frame Strategies

### 1. `transport_frames(points, ref_direction)` — Parallel transport

The initial X-axis is the projection of `ref_direction` onto the plane ⟂ the first
segment tangent.  At each subsequent vertex, X is rotated by the minimal angle
around the axis perpendicular to both the previous and current Z.  This is a
Bishop / rotation-minimising frame — no axial spin accumulates beyond what the
path forces.

```
Arguments:   points: list[Vec] | Path
             ref_direction: Vec
             miter_scale: bool = True

Z at corners:  bisector of incoming and outgoing segments
X at P0:       ref_direction projected onto plane ⟂ Z0
X at Pi:       rotate X_{i-1} by minimal angle around Z_{i-1} × Z_i
Y:             Z × X
```

**Use when:** you want the cross-section to turn smoothly at corners,
even if the path has corners in multiple planes.  X will rotate to stay
⟂ Z — the amount depends on accumulated corner geometry (holonomy).

### 2. `fixed_ref_frames(points, ref_direction)` — Fixed reference direction

At every vertex, X is the projection of `ref_direction` onto the plane ⟂ Z,
computed independently.  X does not rotate due to previous corners — it only
changes because Z changes.

```
Arguments:   points: list[Vec] | Path
             ref_direction: Vec
             miter_scale: bool = True

X at Pi:     project ref_direction onto plane ⟂ Z_i
Y:           Z × X
```

**Use when:** you want X to stay as close as possible to a fixed world
direction.  Can flip abruptly when Z becomes parallel to `ref_direction`
(fallback uses previous X projected onto the current plane, then world axes).

### 3. `upvector_frames(points, world_up)` — World-up reference direction

The inverse of fixed-ref: Y is kept near a "world-up" direction, and X is computed
from `Y × Z`.  The profile "up" direction stays as constant as the path allows,
spreading Y rotation evenly across consecutive corners.

```
Arguments:   points: list[Vec] | Path
             world_up: Vec
             miter_scale: bool = True

Y at Pi:     project world_up onto plane ⟂ Z_i
X:           Y × Z (right-handed: Z = X × Y)
```

**Use when:** the profile has a meaningful "up" direction (I-beam web
direction, rectangle height) that should stay near a world direction.
Avoids the 90° Y-axis flip that fixed-ref can produce at orthogonal-plane
corners.  The default for `build_from_spine()`.

---

### Degenerate-case fallback (all three strategies)

When the reference / up direction is parallel to Z (projection is zero-length):

1. Try the previous frame's X or Y (whichever the strategy projects)
   projected onto the current plane.
2. Fall back to projecting a world axis (Vec(1,0,0) then Vec(0,1,0))
   onto the plane.

---

## FrameField — Return type

```python
class FrameField(NamedTuple):
    frames: List[Plane]   # one per vertex
    scales: List[Tuple[float, str]]   # (scale, axis) per vertex
```

Backward compatible: all existing code that iterates over the result as
a `List[Plane]` must add `.frames`:

```python
# old (bare list):
frames = transport_frames(pts, ref)

# new:
result = transport_frames(pts, ref)
frames = result.frames
```

---

## Miter Scaling

### Algorithm (`_compute_miter_scales`)

At each interior vertex:

1. Compute the **interior angle** θ between BA and BC (vectors *from* the
   corner back to the previous point and forward to the next).

   ```
   ba = points[i-1] - points[i]
   bc = points[i+1] - points[i]
   θ = ba.angle_to(bc)          # interior angle in radians
   ```

2. The **scale factor** S = 1 / sin(θ/2).  At a right-angle corner θ=90°,
   S ≈ 1.414.  At a straight path θ=180°, S=1.0 (no scaling).

3. Compute the **corner-plane normal** N = BA × BC.  This is the normal
   of the plane containing both segments at the corner (derotated from
   the bisector — it points purely in/out of the corner plane).

4. Determine which profile axis is in the corner plane:

   ```
   dot_x = |N · X_i|        X_i = frame.x_axis at vertex i
   dot_y = |N · Y_i|        Y_i = frame.y_axis at vertex i
   axis = "x" if dot_x >= dot_y else "y"
   ```

   The axis NOT aligned with N is the one that lies in the corner plane
   and needs scaling.

5. Apply the scale to that axis:

   | axis label | N aligns with | corner plane contains | scale this profile dim |
   |------------|---------------|----------------------|-----------------------|
   | `"x"`      | X             | Y                    | Y (height / web)      |
   | `"y"`      | Y             | X                    | X (width / flange)    |

### Why the segment cross product, not the bisector rotation axis

The bisector rotation axis `Z_{i-1} × Z_i` carries history from previous
corners.  For a four-point path with 90° corners in XY then YZ:

```
P0 → P1 (+X)  → P2 (+Y)  → P3 (+Z)
```

At P2, Z₁ = bisector of seg₀ (+X) and seg₁ (+Y) = (0.707, 0.707, 0).
Z₂ = bisector of seg₁ (+Y) and seg₂ (+Z) = (0, 0.707, 0.707).
Z₁ × Z₂ = (0.5, -0.5, 0.5), which points **through** the corner rather
than purely perpendicular to it.

The segment cross product BA × BC at P2 = seg₁ × seg₂ = (0,1,0) × (0,0,1)
= (1,0,0) — the true corner-plane normal.  Using this guarantees the miter
axis is correct regardless of how many previous corners affected the bisector.

### Miter scaling with DerivedProfile

`SectionedSpineBuilder.build_from_spine()` uses `DerivedProfile` to apply
miter scaling, which works for **all profile types** without type-specific code:

```python
for i, (scale, axis) in enumerate(field.scales):
    if scale == 1.0:
        profiles.append(profile)
    elif axis == "y":
        # N aligns with Y → miter along X → scale X (flange / width)
        profiles.append(DerivedProfile(profile, scale_x=scale))
    else:
        # N aligns with X → miter along Y → scale Y (web / height)
        profiles.append(DerivedProfile(profile, scale_y=scale))
```

---

## Flip Prevention (`_unflip_frames`)

### Problem

The Z-axis at a vertex is the bisector of incoming and outgoing segments.
When the bisector changes abruptly (e.g., from (0, 0.707, 0.707) to
(0, -0.707, 0.707) between P2 and P3 of a 90°-corner path), the frame's
X-axis can rotate 180° even though the *unflipped* orientation gives
shorter vertex-to-vertex connections between the two sections.

A 180° flip makes the profile appear twisted — the "top" of the profile
swaps to the "bottom" at the corner.

### Solution

After computing all frames, do a greedy left-to-right pass that tests
both the current X/Y and their negations at each interior frame:

```python
for i in range(1, n):
    d_current = connection_length(frames[i-1], frames[i], profiles, origin_shift)
    d_flipped = connection_length(frames[i-1], flipped(frames[i]), profiles, origin_shift)
    if d_flipped < d_current:
        frames[i] = flipped(frames[i])
```

The connection length is the sum of Euclidean distances between corresponding
vertices of a unit-square cross-section at positions i-1 and i.  The candidate
with shorter connections keeps the same "side" of the profile facing the same
direction along the spine.

### Key properties

- **Profile-independent**: uses a unit square for measurement; the
  relative ordering is the same for any convex profile (the profile
  dimensions cancel out as a uniform scale factor).
- **Greedy**: each frame is tested against the previous (already-corrected)
  frame.  No global optimisation.
- **Local only**: corrects 180° flips but leaves rotations < 90° alone.

### Limitations

The greedy pass can cascade: if P3 is flipped, P4 stays consistent with P3
(even though P4's orientation is now "inverted" relative to the starter plane).
The last frame may point opposite to the intended world-up direction.

This is acceptable for the sectioned-spine use case because the profile is
symmetric (a correctly-oriented rectangle and a 180°-flipped one look the
same to the tessellator), but should be noted if the frames are used for
something direction-dependent (e.g., window opening direction).

---

## Build integration

### `SectionedSpineBuilder.build_from_spine()` — one-shot workflow

```python
builder = SectionedSpineBuilder()
element = builder.build_from_spine(
    ifc_file,
    spine=Path.from_pts(pts),
    profile=RectangleProfile(150, 300),
    starter_plane=Plane(pts[0], Vec(0, 1, 0), Vec(0, 0, 1)),
    storey=storey,
    context=context,
    name="my_spine",
)
```

Pipeline inside `build_from_spine`:

```
1. pts = extract control points from path
2. world_up = starter_plane.y_axis         (upvector strategy)
3. field = upvector_frames(pts, world_up)  → FrameField(.frames, .scales)
4. frames = _unflip_frames(pts, field.frames)
5. for each (scale, axis) in field.scales:
       apply DerivedProfile(profile, scale_x/scale_y)  (miter scaling)
6. PendingSectionedSpine(spine, profiles, frames)
7. BaseBuilder.build() → IfcBuildingElementProxy
```

The starter plane serves double duty:

| attribute | role |
|-----------|------|
| `.origin` | must match `pts[0]` (validated implicitly) |
| `.x_axis` | initial X direction (when using fixed-ref) |
| `.y_axis` | world-up direction for upvector strategy |
| `.z_axis` | should match first segment tangent |

When using `upvector_frames` (default), only `.y_axis` matters for
orientation; `.x_axis` is ignored and `.z_axis` is derived from the path.

---

## API Reference

All functions in `ifckit.geometry`:

```python
FrameField(frames, scales)        # NamedTuple

transport_frames(points, ref_direction, angle_step_deg=5, miter_scale=True)
fixed_ref_frames(points, ref_direction, angle_step_deg=5, miter_scale=True)
upvector_frames(points, world_up, angle_step_deg=5, miter_scale=True)

# Internal (available for reuse):
# _unflip_frames(pts, frames) → List[Plane]
# _compute_miter_scales(pts, frames) → List[(float, str)]
```

On `SectionedSpineBuilder`:

```python
SectionedSpineBuilder()
  .build(ifc_file, pending, storey, context)       # via PendingSectionedSpine
  .build_shape_rep(ifc_file, pending, context)      # shape-rep only
  .build_from_spine(ifc_file, spine, profile,       # one-shot
                    starter_plane, storey, context,
                    name="")
```

---

## When to use which strategy

| Strategy | Profile Y stays near… | X derived from… | Best for… |
|----------|-----------------------|-----------------|-----------|
| `transport_frames` | nothing (transports X) | transport of previous X | smooth curves, beam axes |
| `fixed_ref_frames` | Z×project(ref, ⟂Z) | project(ref, ⟂Z) | panorama paths where ref ∥ all segments |
| `upvector_frames` | project(world_up, ⟂Z) | Y × Z | building elements with clear up direction |

`upvector_frames` is the default for `build_from_spine()` and is
recommended for most building geometry.

---

## Reusing these components

The frame+scaling pipeline is not tied to sectioned spine.  Any geometry
function that needs to:

- place frames along a polyline path (`transport_frames` / `fixed_ref_frames`
  / `upvector_frames`)
- detect and correct 180° flips (`_unflip_frames`)
- compute miter compensation for corners (`_compute_miter_scales`)

can import these functions directly from `ifckit.geometry`.  `FrameField`
provides a uniform return type that other geometry generators can rely on.

Example — frames+sweep for a beam with custom tessellation:

```python
from ifckit.geometry import upvector_frames, _unflip_frames

field = upvector_frames(pts, Vec(0, 0, 1))
frames = _unflip_frames(pts, field.frames)
# use frames as orientation references for your own sweep algorithm
```
