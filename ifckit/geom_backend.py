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

#: Supported ifcopenshell line (merged settings/serializer API).
#: Floor is the proven point (packaging pins it exactly); ceiling is the
#: next line — a newer minor gets a clean ImportError, never silent breakage.
MIN_VERSION = (0, 9, 0)
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


def require_version() -> str:
    """Return the ifcopenshell version, raising outside the 0.9 line.

    Raises:
        ImportError: If ifcopenshell is missing, older than 0.9.0, or
            0.10+ (untested line — pin or band must move first).
    """
    version = get_version()
    try:
        parts = tuple(int(p) for p in version.split(".")[:3])
    except ValueError:
        parts = (0, 0, 0)
    if len(parts) < 3:
        parts = parts + (0,) * (3 - len(parts))
    if not (MIN_VERSION <= parts < MAX_VERSION):
        raise ImportError(
            f"ifckit requires ifcopenshell >= 0.9, < 0.10, found {version}. "
            "Install a supported line: pip install 'ifcopenshell==0.9.0'"
        )
    return version


def make_settings(tessellation: Optional[dict] = None) -> Any:
    """Create geometry settings with world coordinates and tessellation.

    Args:
        tessellation: Optional overrides, e.g.
            ``{"linear_deflection": 0.01, "angular_deflection": 0.5}``.
            Defaults: 0.05 / 0.8 (ifcopenshell behaviour).
    """
    import ifcopenshell.geom as _geom

    settings = _geom.settings()
    tessellation = tessellation or {}
    linear = float(tessellation.get("linear_deflection", DEFAULT_LINEAR_DEFLECTION))
    angular = float(tessellation.get("angular_deflection", DEFAULT_ANGULAR_DEFLECTION))
    settings.set("mesher-linear-deflection", linear)
    settings.set("mesher-angular-deflection", angular)
    settings.set("use-world-coords", True)
    return settings


def make_serializer(path: Union[str, os.PathLike], settings: Any) -> Any:
    """Create a geometry serializer for ``path`` (format from extension).

    The ``.obj`` serializer gets a ``.mtl`` sidecar next to ``path``.

    Raises:
        ValueError:  If the extension is not recognised.
        ImportError: If the serializer is unavailable in this build.
    """
    import ifcopenshell.geom as _geom

    require_version()
    path_str = os.fspath(path)
    try:
        factory = _geom.serializers.guess_from_extension(path_str)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    if factory is None:  # pragma: no cover - defensive, guess raises instead
        raise ImportError(f"No serializer available for {path_str!r}.")
    try:
        if os.path.splitext(path_str)[1].lower() == ".obj":
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
        if y_up:
            positions = [
                c
                for i in range(0, len(shape.verts), 3)
                for c in (
                    shape.verts[i],
                    shape.verts[i + 2],
                    -shape.verts[i + 1],
                )
            ]
        else:
            positions = list(shape.verts)
        label = shape.entity_type if label_from == "type" else shape.guid
        yield {
            "primitive": "triangles",
            "positions": positions,
            "indices": list(shape.faces),
            "label": label or shape.guid,
            "guid": shape.guid,
        }
