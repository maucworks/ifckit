# Changelog

All notable changes to this project will be documented in this file.
Format: [Conventional Commits](https://www.conventionalcommits.org/) — `type(scope): description`

## [Unreleased]

### Added — doors, windows, openings (M1–M6)

**Elements**
- `ifckit/elements/opening.py`: `PendingOpening`, `PendingDoor`, `PendingWindow`
  with full `to_dict`/`from_dict`, enum validation, and auto-registration.
  Constants: `DOOR_OPERATION_TYPES`, `WINDOW_TYPES`, `OPENING_HOST_IFC_CLASSES`.
- `ifckit/elements/types.py`: `PendingTypeObject`, `PendingDoorType`,
  `PendingWindowType` with all IFC lining/panel pset fields as optional floats
  and deterministic SHA-256 `type_key`.

**Builders**
- `ifckit/builders/opening.py`: `build_opening()` — creates `IfcOpeningElement`
  + `IfcRelVoidsElement` + spatial containment.
- `ifckit/builders/door_window.py`: `build_door()`, `build_window()` — creates
  fill entities, `IfcRelFillsElement`, containment, optional `IfcRelDefinesByType`.
  `_assign_type()` reuses an existing relation rather than creating duplicates.
- `ifckit/builders/types.py`: `build_door_type()`, `build_window_type()` —
  IFC4 `IfcDoorType`/`IfcWindowType`; IFC2X3 `IfcDoorStyle`/`IfcWindowStyle`;
  all lining + panel psets written via `IfcRelDefinesByProperties`.

**Model API**
- `IfcModel.add_opening(pending, host, container)` — validated, host-class-
  checked, returns `EntityHandle`.
- `IfcModel.add_door(pending, opening, container, door_type=None)`.
- `IfcModel.add_window(pending, opening, container, window_type=None)`.
- `IfcModel.add_door_type(pending)` / `add_window_type(pending)` — model-local
  type cache keyed by `type_key`; collision detection on mismatched parameters.

**JSON build (3-pass)**
- `validate_json()` extended: validates `door_types`, `window_types`,
  per-storey `openings`, `doors`, `windows` sections.
- `build()` now runs a 3-pass build:
  1. Spatial hierarchy + host elements (unchanged); elements with an `"id"`
     field are registered in a flat `id_map`.
  2. Door/window types (root-level) + openings (per-storey, `host_ref` →
     host `id`).
  3. Doors + windows (per-storey, `opening_ref` → opening `id`, optional
     `type_ref` → type name/key).
- `build_from_json()` unchanged.

**Grasshopper components**
- `gh_create_opening.py` — insert plane + width/height + host_id → opening JSON.
- `gh_create_door.py` — opening_id + dimensions + operation_type + type_ref → door JSON.
- `gh_create_window.py` — opening_id + dimensions + window_type + type_ref → window JSON.
- `gh_create_door_type.py` — type parameters → door type JSON (root `door_types`).
- `gh_create_window_type.py` — type parameters → window type JSON (root `window_types`).
- `gh_build_json.py` extended: new inputs `openings_in`, `doors_in`, `windows_in`,
  `door_types_in`, `window_types_in`; flat inputs merged into first storey.

**Tests** — 887 tests total (up from 801):
- `tests/elements/test_opening.py` (64 tests)
- `tests/elements/test_doors_windows_types.py` (48 tests)
- `tests/builders/test_opening_builder.py`
- `tests/builders/test_door_window_builder.py`
- `tests/builders/test_type_builders.py`
- `tests/test_model_doors_windows.py`
- `tests/test_json_build_openings.py` (24 tests)

### Added — earlier milestones
- `ifckit/geometry`: `Vec`, `Plane`, `Line`, `Arc`, `Polyline`, `Path`,
  `parallel_transport_frames` — framework-agnostic geometry primitives
- `pyproject.toml` with `ifcopenshell` dependency and dev extras
- `PLAN.md` — full milestone-based implementation plan
