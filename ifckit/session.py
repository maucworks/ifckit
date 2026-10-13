# This file was generated with the assistance of an AI coding tool.
"""
ifckit.session
==============

Small stateful helper for interactive preview ticks
(PLAN-interactive-preview, I-7).

A :class:`ModelSession` holds one :class:`~ifckit.model.IfcModel` and
bundles :meth:`~ifckit.model.IfcModel.apply_delta` with selective
tessellation, caching the geometry settings — so configurators do not
need their own model/dict bookkeeping per tick.
"""

from __future__ import annotations

import json as _json
from typing import Optional

from ifckit.model import IfcModel
from ifckit.schema import IfcSchema


class ModelSession:
    """One in-memory model plus patch + tessellate helpers for preview ticks.

    Args:
        model: Existing ``IfcModel`` to wrap. When omitted, a fresh model
               with a default Site/Building/``Level 0`` storey is created.
        name: Project name for a fresh model.
        schema: IFC schema for a fresh model.
        preset: Default tessellation preset (``"interactive"`` coarse for
                ticks, ``"final"`` for exact output).
        validate: Validate rebuilt elements (default False — preview data
                  is pre-validated; full validation runs at save/export).
    """

    def __init__(
        self,
        model: Optional[IfcModel] = None,
        *,
        name: str = "Preview",
        schema: IfcSchema = IfcSchema.IFC4,
        preset: str = "interactive",
        validate: bool = False,
    ) -> None:
        if model is None:
            model = IfcModel(name=name, schema=schema)
            model.add_site("Site").add_building("Building").add_storey("Level 0")
        self.model = model
        self.preset = preset
        self.validate = validate
        self._settings_cache: dict = {}

    def _settings(self, preset: str, tessellation: Optional[dict]):
        """Return cached geometry settings for (*preset*, *tessellation*)."""
        from ifckit import geom_backend

        key = (preset, _json.dumps(tessellation or {}, sort_keys=True, default=str))
        try:
            return self._settings_cache[key]
        except KeyError:
            settings = geom_backend.make_settings(tessellation, preset=preset)
            self._settings_cache[key] = settings
            return settings

    def tick(
        self,
        elements: list,
        *,
        kind: str = "chunks",
        full: bool = False,
        preset: Optional[str] = None,
        tessellation: Optional[dict] = None,
    ) -> tuple:
        """Apply one preview tick; return ``(changed_guids, payload)``.

        Runs :meth:`~ifckit.model.IfcModel.apply_delta` and tessellates
        only the changed GUIDs (or everything with ``full=True``).

        Args:
            elements: Full element state for this tick (hosts before fills).
            kind: ``"chunks"`` (binary, default) or ``"dicts"`` (JSON).
            full: Tessellate all products instead of just the changed GUIDs.
            preset: Tessellation preset override for this tick.
            tessellation: Explicit deflection overrides for this tick.

        Returns:
            ``(changed, payload)`` — changed ``GlobalId`` strings plus the
            tessellated chunks/dicts (empty when nothing changed).
        """
        if kind not in ("chunks", "dicts"):
            raise ValueError(f"tick: kind must be 'chunks' or 'dicts', got {kind!r}.")
        from ifckit import geom_backend

        changed = self.model.apply_delta(elements, validate=self.validate)
        shapes = geom_backend.iter_shapes(
            self.model.ifc_file,
            self._settings(preset or self.preset, tessellation),
            include_guids=None if full else changed,
        )
        if kind == "chunks":
            payload = list(geom_backend.shapes_to_chunks(shapes))
        else:
            payload = list(geom_backend.shapes_to_mesh_dicts(shapes))
        return changed, payload
