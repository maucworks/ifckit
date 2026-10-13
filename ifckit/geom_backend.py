"""
ifckit.geom_backend
===================

Single touchpoint for ``ifcopenshell.geom`` (requires ifcopenshell >= 0.9.0).

All geometry consumers (``IfcModel.export()``, preview tooling, Rhino/Grasshopper
importers, web configurator backends) build on this facade instead of importing
``ifcopenshell.geom`` directly, so the 0.9 serializer-API (merged settings, no
``serializer_settings``) only has to be handled in one place.

Shapes are streamed as :class:`IterShape` records carrying the element GUID, so
callers can diff and selectively update meshes (configurator, rhinokit) instead
of re-tessellating everything.
"""

# This file was generated with the assistance of an AI coding tool.

from __future__ import annotations

import os
from typing import Any, Collection, Iterator, NamedTuple, Optional, Union

#: Default tessellation, matching ifcopenshell behaviour.
DEFAULT_LINEAR_DEFLECTION = 0.05
DEFAULT_ANGULAR_DEFLECTION = 0.8

#: Tessellation presets (PLAN-interactive-preview, I-3). ``final`` is the
#: status-quo default; ``interactive`` is coarse for preview ticks.
#: Measured on this machine (ifcopenshell 0.9.0): a 270° revolved beam
#: tessellates in ~44 ms / 128 tris (final) vs ~0.6 ms / 60 tris
#: (interactive); 3 walls with boolean openings in ~53 ms vs ~9.5 ms.
#: Opening booleans dominate: the same 3 walls without openings cost
#: ~1.1 ms at either preset.
PRESETS = {
    "final": {
        "linear_deflection": DEFAULT_LINEAR_DEFLECTION,
        "angular_deflection": DEFAULT_ANGULAR_DEFLECTION,
    },
    "interactive": {"linear_deflection": 0.5, "angular_deflection": 1.5},
}

#: Supported ifcopenshell lines, oldest first.
#: Floor is 0.8.4: the last line with Python 3.9 wheels (Rhino 8) and the
#: oldest proven point. The 0.8 serializer API (separate serializer_settings)
#: is handled via capability detection in make_serializer, not version
#: sniffing. Ceiling is the next line — a newer minor gets a clean
#: ImportError, never silent breakage.
MIN_VERSION = (0, 8, 4)
MAX_VERSION = (0, 10)

#: Entity types skipped with ``skip_openings=True``.
_OPENING_TYPES = frozenset({"IfcOpeningElement"})


class IterShape(NamedTuple):
    """One tessellated product: GUID, type, and world-space mesh data."""

    guid: str
    entity_type: str
    verts: list
    faces: list


def get_version() -> str:
    """Return the installed ifcopenshell version string (``"?"`` on failure)."""
    try:
        import ifcopenshell

        return str(ifcopenshell.version)
    except Exception:
        return "?"


def _version_tuple(version: str) -> tuple:
    """Parse ``(major, minor, patch)``; tolerates suffixes like ``-dev``."""
    import re

    match = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?", version)
    if not match:
        return (0, 0, 0)
    return tuple(int(group) if group is not None else 0 for group in match.groups())


def require_version() -> str:
    """Return the ifcopenshell version, raising outside the 0.8.4–0.9 lines.

    Raises:
        ImportError: If ifcopenshell is missing, older than 0.8.4, or
            0.10+ (untested line — pin or band must move first).
    """
    version = get_version()
    parts = _version_tuple(version)
    if not (MIN_VERSION <= parts < MAX_VERSION):
        raise ImportError(
            f"ifckit requires ifcopenshell >= 0.8.4, < 0.10, found {version}. "
            "Install a supported line: pip install 'ifcopenshell==0.9.0' "
            "(or 'ifcopenshell==0.8.4.post1' on Python 3.9 / Rhino 8)"
        )
    return version


def make_settings(tessellation: Optional[Union[dict, str]] = None, *, preset: str = "final") -> Any:
    """Create geometry settings with world coordinates and tessellation.

    Args:
        tessellation: Optional overrides, e.g.
            ``{"linear_deflection": 0.01, "angular_deflection": 0.5}``.
            A preset name (``"interactive"``) may be passed positionally
            instead, overriding *preset*.
        preset: ``"final"`` (default, 0.05 / 0.8) or ``"interactive"``
            (coarse, 0.5 / 1.5) — see :data:`PRESETS`. Explicit
            *tessellation* keys win over the preset base.

    Raises:
        ValueError: If *preset* (or a positional preset name) is unknown.
    """
    import ifcopenshell.geom as _geom

    if isinstance(tessellation, str):
        preset, tessellation = tessellation, None
    try:
        base = PRESETS[preset]
    except KeyError:
        raise ValueError(
            f"Unknown tessellation preset {preset!r}. Available: {sorted(PRESETS)}."
        ) from None
    merged = {**base, **(tessellation or {})}
    settings = _geom.settings()
    settings.set("mesher-linear-deflection", float(merged["linear_deflection"]))
    settings.set("mesher-angular-deflection", float(merged["angular_deflection"]))
    settings.set("use-world-coords", True)
    return settings


def make_serializer(path: Union[str, os.PathLike], settings: Any) -> Any:
    """Create a geometry serializer for ``path`` (format from extension).

    The ``.obj`` serializer gets a ``.mtl`` sidecar next to ``path``.

    Supports both serializer APIs via capability detection: ifcopenshell
    0.8 takes a separate ``serializer_settings`` object (extra factory
    argument), 0.9+ merged those options into ``settings``.

    Raises:
        ValueError:  If the extension is not recognised.
        ImportError: If the serializer is unavailable in this build.
    """
    import ifcopenshell.geom as _geom

    path_str = os.fspath(path)
    try:
        factory = _geom.serializers.guess_from_extension(path_str)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    require_version()
    if factory is None:  # pragma: no cover - defensive, guess raises instead
        raise ImportError(f"No serializer available for {path_str!r}.")
    try:
        is_obj = os.path.splitext(path_str)[1].lower() == ".obj"
        if hasattr(_geom, "serializer_settings"):
            # ifcopenshell 0.8 (e.g. Rhino 8 line): separate settings object.
            s_settings = _geom.serializer_settings()
            if is_obj:
                mtl_path = os.path.splitext(path_str)[0] + ".mtl"
                return factory(path_str, mtl_path, settings, s_settings)
            return factory(path_str, settings, s_settings)
        if is_obj:
            mtl_path = os.path.splitext(path_str)[0] + ".mtl"
            return factory(path_str, mtl_path, settings)
        return factory(path_str, settings)
    except AttributeError as exc:
        raise ImportError(
            f"The serializer for {path_str!r} is not available in this ifcopenshell build."
        ) from exc


def serialize_to_file(
    source: Any,
    dest: Union[str, os.PathLike],
    settings: Any,
    *,
    skip_openings: bool = True,
    num_threads: int = 1,
) -> None:
    """Run the geometry iterator over ``source`` into the serializer for ``dest``.

    Args:
        source:        An open ``ifcopenshell.file`` or a path to an ``.ifc`` file.
        dest:          Destination path; format inferred from the extension.
        settings:      Geometry settings, e.g. from :func:`make_settings`.
        skip_openings: Skip ``IfcOpeningElement`` shapes — void boxes never render
                       as solid in a viewer file (default True).
        num_threads:   Iterator thread count (default 1, status quo). Pass
                       ``os.cpu_count()`` for large models.

    Raises:
        ValueError:  If the extension is not recognised.
        ImportError: If the serializer is unavailable in this build.
    """
    import ifcopenshell.geom as _geom

    serializer = make_serializer(dest, settings)
    iterator = _geom.iterator(settings, source, num_threads)
    # Same upstream quirk as in iter_shapes: only trust iterator.file when
    # constructed from a path; a file object can be passed directly.
    if hasattr(source, "by_guid"):
        ifc_file = source
        serializer.setFile(source)
    else:
        import ifcopenshell

        ifc_file = ifcopenshell.open(os.fspath(source))
        serializer.setFile(iterator.file)
    serializer.writeHeader()
    if iterator.initialize():
        while True:
            shape = iterator.get()
            if skip_openings:
                guid = getattr(shape, "guid", "") or ""
                entity_type = ""
                if guid:
                    try:
                        entity = ifc_file.by_guid(guid)
                        entity_type = entity.is_a() if entity is not None else ""
                    except Exception:
                        entity_type = ""
                if entity_type in _OPENING_TYPES:
                    if not iterator.next():
                        break
                    continue
            serializer.write(shape)
            if not iterator.next():
                break
    serializer.finalize()


def guid_for_id(stable_id: str) -> str:
    """Derive a deterministic 22-char IFC GlobalId from a stable element id.

    ``uuid5``-hash (``ifckit:``-namespaced) compressed to the IFC base64
    alphabet, so the same ``id`` always maps to the same ``GlobalId`` across
    builds. Lets clients (e.g. a web configurator) diff on ``id`` and only
    re-tessellate changed GUIDs via ``include_guids``.
    """
    import uuid

    from ifcopenshell.guid import compress

    return compress(str(uuid.uuid5(uuid.NAMESPACE_URL, f"ifckit:{stable_id}")))


def iter_shapes(
    source: Any,
    settings: Any,
    *,
    skip_openings: bool = True,
    include_guids: Optional[Collection[str]] = None,
) -> Iterator[IterShape]:
    """Yield :class:`IterShape` records for every product in ``source``.

    Args:
        source:         An open ``ifcopenshell.file`` or a path to an ``.ifc`` file.
        settings:       Geometry settings, e.g. from :func:`make_settings`.
        skip_openings:  Skip ``IfcOpeningElement`` shapes (voids), on by default.
        include_guids:  Only yield these GUIDs (selective re-tessellation).
    """
    import ifcopenshell.geom as _geom

    wanted = set(include_guids) if include_guids is not None else None
    iterator = _geom.iterator(settings, source)
    # NOTE: ``iterator.file`` is unreliable (upstream keeps the ``file`` class
    # instead of the instance when constructed from a file object), so resolve
    # the lookup file from ``source`` directly.
    if hasattr(source, "by_guid"):
        ifc_file = source
    else:
        import ifcopenshell

        ifc_file = ifcopenshell.open(os.fspath(source))
    if not iterator.initialize():
        return
    while True:
        shape = iterator.get()
        guid = getattr(shape, "guid", "") or ""
        if wanted is None or guid in wanted:
            entity_type = ""
            if guid:
                try:
                    entity = ifc_file.by_guid(guid)
                    entity_type = entity.is_a() if entity is not None else ""
                except Exception:
                    entity_type = ""
            if not (skip_openings and entity_type in _OPENING_TYPES):
                geometry = shape.geometry
                yield IterShape(
                    guid=guid,
                    entity_type=entity_type,
                    verts=list(geometry.verts),
                    faces=list(geometry.faces),
                )
        if not iterator.next():
            break


def shapes_to_mesh_dicts(
    shapes: Iterator[IterShape],
    *,
    y_up: bool = True,
    label_from: str = "type",
) -> Iterator[dict]:
    """Convert shapes to viewer mesh dicts (``triangles`` primitive).

    Output matches the ``Path``/``Surface.to_mesh_dict()`` viewer format:
    ``{"primitive", "positions", "indices", "label", "guid"}``, with the same
    Z-up to Y-up conversion ``(x, z, -y)``.
    """
    for shape in shapes:
        positions = _convert_positions(shape.verts, y_up=y_up)
        label = shape.entity_type if label_from == "type" else shape.guid
        yield {
            "primitive": "triangles",
            "positions": positions,
            "indices": list(shape.faces),
            "label": label or shape.guid,
            "guid": shape.guid,
        }


def _convert_positions(verts: list, *, y_up: bool) -> list:
    """Flatten shape verts, optionally converting Z-up to Y-up ``(x, z, -y)``."""
    if y_up:
        return [c for i in range(0, len(verts), 3) for c in (verts[i], verts[i + 2], -verts[i + 1])]
    return list(verts)


def shapes_to_chunks(
    shapes: Iterator[IterShape],
    *,
    y_up: bool = True,
) -> Iterator[dict]:
    """Convert shapes to compact binary chunks for instancing viewers.

    A second serialization of the same shapes (no new geometry): per
    product ``{"guid", "label", "profile_key", "offset", "positions",
    "index", "vertex_count", "index_count"}``. ``positions``/``index``
    are little-endian float32/uint32 bytes (a viewer wraps them in
    ``Float32Array``/``Uint32Array`` directly); positions are
    translation-normalized, add ``offset`` to restore world coords.
    ``profile_key`` is the sha1 of the normalized positions, so identically
    shaped products at different translations share a key and the viewer
    can instance them. Translation-only: rotated copies hash differently.
    """
    import hashlib
    import struct

    for mesh in shapes_to_mesh_dicts(shapes, y_up=y_up):
        positions = mesh["positions"]
        if positions:
            offset = [
                min(positions[0::3]),
                min(positions[1::3]),
                min(positions[2::3]),
            ]
        else:
            offset = [0.0, 0.0, 0.0]
        normalized = [c - offset[i % 3] for i, c in enumerate(positions)]
        indices = mesh["indices"]
        pos_bytes = struct.pack("<%df" % len(normalized), *normalized)
        yield {
            "guid": mesh["guid"],
            "label": mesh["label"],
            "profile_key": hashlib.sha1(pos_bytes).hexdigest(),
            "offset": offset,
            "positions": pos_bytes,
            "index": struct.pack("<%dI" % len(indices), *indices),
            "vertex_count": len(positions) // 3,
            "index_count": len(indices),
        }
