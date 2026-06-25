"""
ifckit.elements.types
=====================

Pending type objects for doors and windows.

Type objects are **not** spatial elements — they carry no placement,
no clips, no style, no containment.  They are ``IfcTypeProduct``
descriptors that describe a family of identical occurrences.

Hierarchy::

    PendingTypeObject          (thin shared base — type_key, name, to_dict, from_dict)
        PendingDoorType        → IfcDoorType
        PendingWindowType      → IfcWindowType

Each type object holds all ``IfcDoorLiningProperties`` /
``IfcDoorPanelProperties`` / ``IfcWindowLiningProperties`` /
``IfcWindowPanelProperties`` fields as optional floats.  A value of
``None`` means "not set" — the pset attribute will be omitted from the
IFC file.

Type-key policy
---------------
- If the caller supplies ``type_key``, that exact string is used.
- Otherwise the key is auto-derived from a canonical signature of the
  non-``None`` parameter values.  The format is::

      door:{operation}:{w:.4f}:{h:.4f}:{lining_hash}:{panel_hash}
      window:{wtype}:{w:.4f}:{h:.4f}:{lining_hash}:{panel_hash}

  where ``{lining_hash}`` and ``{panel_hash}`` are deterministic
  hex digests of the sorted non-``None`` field tuples.

Collision rule: if two callers supply the same ``type_key`` but
different parameters, ``ValueError`` is raised at model-add time
(not here — the type cache in ``IfcModel`` enforces this).
"""

from __future__ import annotations

import hashlib
import json as _json
from typing import Any, Dict, Optional

from ifckit.elements.opening import DOOR_OPERATION_TYPES, WINDOW_TYPES

# ---------------------------------------------------------------------------
# PendingTypeObject — thin shared base
# ---------------------------------------------------------------------------


class PendingTypeObject:
    """
    Lightweight base for IFC type descriptors (``IfcTypeProduct`` subclasses).

    Unlike ``PendingElement``, type objects are not spatial and carry no
    placement, clips, or containment.  They are not registered in
    ``ElementRegistry`` because they are not added via ``model.add()``.

    Subclasses must set ``type_object_type`` as a class variable.
    """

    type_object_type: str  # set by each subclass ("door_type" / "window_type")

    def __init__(self, type_key: Optional[str], name: str = "") -> None:
        self.name = name
        # type_key is resolved in _resolve_key() which subclasses call after
        # their own fields are set.
        self._explicit_key = type_key

    # ------------------------------------------------------------------
    # Key derivation — subclasses call this after setting their fields
    # ------------------------------------------------------------------

    def _resolve_key(self, signature_parts: Dict[str, Any]) -> str:
        """Return the final type_key: explicit if given, else auto-derived."""
        if self._explicit_key:
            return self._explicit_key
        return self._derive_key(signature_parts)

    @classmethod
    def _derive_key(cls, parts: Dict[str, Any]) -> str:
        """Deterministic key from a dict of non-None parameter values."""
        # Sort items for stability, filter None values
        filtered = sorted((k, v) for k, v in parts.items() if v is not None)
        stable = _json.dumps(filtered, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(stable.encode()).hexdigest()[:12]
        return f"{cls.type_object_type}:{digest}"

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "type": self.type_object_type,
            "type_key": self.type_key,
            "name": self.name,
        }

    def to_json(self, **kwargs) -> str:
        """Serialise to a JSON string."""
        return _json.dumps(self.to_dict(), **kwargs)

    @classmethod
    def _require(cls, d: Dict[str, Any], key: str) -> Any:
        if key not in d:
            raise ValueError(f"{cls.__name__}: missing required field '{key}'")
        return d[key]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type_key={self.type_key!r}, name={self.name!r})"


# ---------------------------------------------------------------------------
# PendingDoorType
# ---------------------------------------------------------------------------


class PendingDoorType(PendingTypeObject):
    """
    Descriptor for a reusable door type (``IfcDoorType``).

    Lining parameters map to ``IfcDoorLiningProperties``.
    Panel parameters map to ``IfcDoorPanelProperties``.
    All are optional floats; ``None`` means "omit from IFC pset".

    Args:
        overall_width:          Overall width of instances (metres).
        overall_height:         Overall height of instances (metres).
        operation_type:         One of ``DOOR_OPERATION_TYPES``.
        name:                   Type name (``IfcDoorType.Name``).
        type_key:               Optional explicit key.  Auto-derived if omitted.

        -- IfcDoorLiningProperties --
        lining_depth:           Depth of the lining.
        lining_thickness:       Thickness of the lining.
        threshold_depth:        Depth of the threshold.
        threshold_thickness:    Thickness of the threshold.
        threshold_offset:       Offset of the threshold.
        transom_thickness:      Thickness of the transom.
        transom_offset:         Offset of the transom from bottom.
        lining_offset:          Offset of the lining from wall face.
        casing_thickness:       Thickness of the casing.
        casing_depth:           Depth of the casing.
        lining_to_panel_offset_x: X offset from lining to panel.
        lining_to_panel_offset_y: Y offset from lining to panel.

        -- IfcDoorPanelProperties --
        panel_depth:            Depth (thickness) of the panel.
        panel_width:            Fraction (0–1) of overall width for the panel.
        panel_operation:        Panel operation string (e.g. ``"SWINGING"``).
    """

    type_object_type = "door_type"

    def __init__(
        self,
        overall_width: float,
        overall_height: float,
        operation_type: str = "NOTDEFINED",
        name: str = "",
        type_key: Optional[str] = None,
        # IfcDoorLiningProperties
        lining_depth: Optional[float] = None,
        lining_thickness: Optional[float] = None,
        threshold_depth: Optional[float] = None,
        threshold_thickness: Optional[float] = None,
        threshold_offset: Optional[float] = None,
        transom_thickness: Optional[float] = None,
        transom_offset: Optional[float] = None,
        lining_offset: Optional[float] = None,
        casing_thickness: Optional[float] = None,
        casing_depth: Optional[float] = None,
        lining_to_panel_offset_x: Optional[float] = None,
        lining_to_panel_offset_y: Optional[float] = None,
        # IfcDoorPanelProperties
        panel_depth: Optional[float] = None,
        panel_width: Optional[float] = None,
        panel_operation: Optional[str] = None,
        # JSON component graph for geometry (optional)
        component_graph: Optional[str] = None,
        # Material overrides per role (optional)
        material_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        # Extra user properties
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(type_key=type_key, name=name)
        if overall_width <= 0:
            raise ValueError(
                f"PendingDoorType: overall_width must be positive, got {overall_width!r}"
            )
        if overall_height <= 0:
            raise ValueError(
                f"PendingDoorType: overall_height must be positive, got {overall_height!r}"
            )
        op = operation_type.upper()
        if op not in DOOR_OPERATION_TYPES:
            raise ValueError(
                f"PendingDoorType: unknown operation_type {operation_type!r}. "
                f"Allowed: {sorted(DOOR_OPERATION_TYPES)}"
            )
        self.overall_width = float(overall_width)
        self.overall_height = float(overall_height)
        self.operation_type = op
        # Lining
        self.lining_depth = lining_depth
        self.lining_thickness = lining_thickness
        self.threshold_depth = threshold_depth
        self.threshold_thickness = threshold_thickness
        self.threshold_offset = threshold_offset
        self.transom_thickness = transom_thickness
        self.transom_offset = transom_offset
        self.lining_offset = lining_offset
        self.casing_thickness = casing_thickness
        self.casing_depth = casing_depth
        self.lining_to_panel_offset_x = lining_to_panel_offset_x
        self.lining_to_panel_offset_y = lining_to_panel_offset_y
        # Panel
        self.panel_depth = panel_depth
        self.panel_width = panel_width
        self.panel_operation = panel_operation
        # Component graph
        self.component_graph: Optional[str] = component_graph
        # Material overrides
        self.material_overrides: Dict[str, Dict[str, Any]] = material_overrides or {}
        # Extra
        self.properties: Dict[str, Any] = properties or {}
        # Resolve key now that all fields are set
        self.type_key = self._resolve_key(self._signature_parts())

    def _signature_parts(self) -> Dict[str, Any]:
        return {
            "kind": "door",
            "operation_type": self.operation_type,
            "overall_width": round(self.overall_width, 6),
            "overall_height": round(self.overall_height, 6),
            "lining_depth": self.lining_depth,
            "lining_thickness": self.lining_thickness,
            "threshold_depth": self.threshold_depth,
            "threshold_thickness": self.threshold_thickness,
            "threshold_offset": self.threshold_offset,
            "transom_thickness": self.transom_thickness,
            "transom_offset": self.transom_offset,
            "lining_offset": self.lining_offset,
            "casing_thickness": self.casing_thickness,
            "casing_depth": self.casing_depth,
            "lining_to_panel_offset_x": self.lining_to_panel_offset_x,
            "lining_to_panel_offset_y": self.lining_to_panel_offset_y,
            "panel_depth": self.panel_depth,
            "panel_width": self.panel_width,
            "panel_operation": self.panel_operation,
            "component_graph": self.component_graph,
        }

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        d = super().to_dict()
        d["overall_width"] = self.overall_width
        d["overall_height"] = self.overall_height
        d["operation_type"] = self.operation_type
        # Lining — only include non-None
        for field in (
            "lining_depth",
            "lining_thickness",
            "threshold_depth",
            "threshold_thickness",
            "threshold_offset",
            "transom_thickness",
            "transom_offset",
            "lining_offset",
            "casing_thickness",
            "casing_depth",
            "lining_to_panel_offset_x",
            "lining_to_panel_offset_y",
        ):
            val = getattr(self, field)
            if val is not None:
                d[field] = val
        # Panel
        for field in ("panel_depth", "panel_width", "panel_operation"):
            val = getattr(self, field)
            if val is not None:
                d[field] = val
        if self.component_graph is not None:
            d["component_graph"] = self.component_graph
        if self.material_overrides:
            d["material_overrides"] = self.material_overrides
        if self.properties:
            d["properties"] = self.properties
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingDoorType":
        """Deserialize from a dict."""
        return cls(
            overall_width=cls._require(d, "overall_width"),
            overall_height=cls._require(d, "overall_height"),
            operation_type=d.get("operation_type", "NOTDEFINED"),
            name=d.get("name", ""),
            type_key=d.get("type_key"),
            lining_depth=d.get("lining_depth"),
            lining_thickness=d.get("lining_thickness"),
            threshold_depth=d.get("threshold_depth"),
            threshold_thickness=d.get("threshold_thickness"),
            threshold_offset=d.get("threshold_offset"),
            transom_thickness=d.get("transom_thickness"),
            transom_offset=d.get("transom_offset"),
            lining_offset=d.get("lining_offset"),
            casing_thickness=d.get("casing_thickness"),
            casing_depth=d.get("casing_depth"),
            lining_to_panel_offset_x=d.get("lining_to_panel_offset_x"),
            lining_to_panel_offset_y=d.get("lining_to_panel_offset_y"),
            panel_depth=d.get("panel_depth"),
            panel_width=d.get("panel_width"),
            panel_operation=d.get("panel_operation"),
            component_graph=d.get("component_graph"),
            material_overrides=d.get("material_overrides"),
            properties=d.get("properties") or {},
        )


# ---------------------------------------------------------------------------
# PendingWindowType
# ---------------------------------------------------------------------------


class PendingWindowType(PendingTypeObject):
    """
    Descriptor for a reusable window type (``IfcWindowType``).

    Lining parameters map to ``IfcWindowLiningProperties``.
    Panel parameters map to ``IfcWindowPanelProperties``.
    All are optional floats / strings; ``None`` means "omit from IFC pset".

    Args:
        overall_width:          Overall width of instances (metres).
        overall_height:         Overall height of instances (metres).
        window_type:            One of ``WINDOW_TYPES``.
        name:                   Type name (``IfcWindowType.Name``).
        type_key:               Optional explicit key.  Auto-derived if omitted.

        -- IfcWindowLiningProperties --
        lining_depth:           Depth of the lining.
        lining_thickness:       Thickness of the lining.
        transom_thickness:      Thickness of the transom.
        mullion_thickness:      Thickness of the mullion.
        first_transom_offset:   First transom position (0–1 fraction).
        second_transom_offset:  Second transom position (0–1 fraction).
        first_mullion_offset:   First mullion position (0–1 fraction).
        second_mullion_offset:  Second mullion position (0–1 fraction).
        lining_offset:          Offset of lining from wall face.
        lining_to_panel_offset_x: X offset from lining to panel.
        lining_to_panel_offset_y: Y offset from lining to panel.

        -- IfcWindowPanelProperties --
        panel_depth:            Depth (thickness) of the panel.
        panel_width:            Width fraction for the panel (0–1).
        panel_height:           Height fraction for the panel (0–1).
        panel_operation:        Panel operation string (e.g. ``"SIDEHUNGRIGHTHAND"``).
    """

    type_object_type = "window_type"

    def __init__(
        self,
        overall_width: float,
        overall_height: float,
        window_type: str = "NOTDEFINED",
        name: str = "",
        type_key: Optional[str] = None,
        # IfcWindowLiningProperties
        lining_depth: Optional[float] = None,
        lining_thickness: Optional[float] = None,
        transom_thickness: Optional[float] = None,
        mullion_thickness: Optional[float] = None,
        first_transom_offset: Optional[float] = None,
        second_transom_offset: Optional[float] = None,
        first_mullion_offset: Optional[float] = None,
        second_mullion_offset: Optional[float] = None,
        lining_offset: Optional[float] = None,
        lining_to_panel_offset_x: Optional[float] = None,
        lining_to_panel_offset_y: Optional[float] = None,
        # IfcWindowPanelProperties
        panel_depth: Optional[float] = None,
        panel_width: Optional[float] = None,
        panel_height: Optional[float] = None,
        panel_operation: Optional[str] = None,
        # JSON component graph for geometry (optional)
        component_graph: Optional[str] = None,
        # Material overrides per role (optional)
        material_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        # Extra user properties
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(type_key=type_key, name=name)
        if overall_width <= 0:
            raise ValueError(
                f"PendingWindowType: overall_width must be positive, got {overall_width!r}"
            )
        if overall_height <= 0:
            raise ValueError(
                f"PendingWindowType: overall_height must be positive, got {overall_height!r}"
            )
        wt = window_type.upper()
        if wt not in WINDOW_TYPES:
            raise ValueError(
                f"PendingWindowType: unknown window_type {window_type!r}. "
                f"Allowed: {sorted(WINDOW_TYPES)}"
            )
        self.overall_width = float(overall_width)
        self.overall_height = float(overall_height)
        self.window_type = wt
        # Lining
        self.lining_depth = lining_depth
        self.lining_thickness = lining_thickness
        self.transom_thickness = transom_thickness
        self.mullion_thickness = mullion_thickness
        self.first_transom_offset = first_transom_offset
        self.second_transom_offset = second_transom_offset
        self.first_mullion_offset = first_mullion_offset
        self.second_mullion_offset = second_mullion_offset
        self.lining_offset = lining_offset
        self.lining_to_panel_offset_x = lining_to_panel_offset_x
        self.lining_to_panel_offset_y = lining_to_panel_offset_y
        # Panel
        self.panel_depth = panel_depth
        self.panel_width = panel_width
        self.panel_height = panel_height
        self.panel_operation = panel_operation
        # Component graph
        self.component_graph: Optional[str] = component_graph
        # Material overrides
        self.material_overrides: Dict[str, Dict[str, Any]] = material_overrides or {}
        # Extra
        self.properties: Dict[str, Any] = properties or {}
        # Resolve key now that all fields are set
        self.type_key = self._resolve_key(self._signature_parts())

    def _signature_parts(self) -> Dict[str, Any]:
        return {
            "kind": "window",
            "window_type": self.window_type,
            "overall_width": round(self.overall_width, 6),
            "overall_height": round(self.overall_height, 6),
            "lining_depth": self.lining_depth,
            "lining_thickness": self.lining_thickness,
            "transom_thickness": self.transom_thickness,
            "mullion_thickness": self.mullion_thickness,
            "first_transom_offset": self.first_transom_offset,
            "second_transom_offset": self.second_transom_offset,
            "first_mullion_offset": self.first_mullion_offset,
            "second_mullion_offset": self.second_mullion_offset,
            "lining_offset": self.lining_offset,
            "lining_to_panel_offset_x": self.lining_to_panel_offset_x,
            "lining_to_panel_offset_y": self.lining_to_panel_offset_y,
            "panel_depth": self.panel_depth,
            "panel_width": self.panel_width,
            "panel_height": self.panel_height,
            "panel_operation": self.panel_operation,
            "component_graph": self.component_graph,
        }

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        d = super().to_dict()
        d["overall_width"] = self.overall_width
        d["overall_height"] = self.overall_height
        d["window_type"] = self.window_type
        for field in (
            "lining_depth",
            "lining_thickness",
            "transom_thickness",
            "mullion_thickness",
            "first_transom_offset",
            "second_transom_offset",
            "first_mullion_offset",
            "second_mullion_offset",
            "lining_offset",
            "lining_to_panel_offset_x",
            "lining_to_panel_offset_y",
        ):
            val = getattr(self, field)
            if val is not None:
                d[field] = val
        for field in ("panel_depth", "panel_width", "panel_height", "panel_operation"):
            val = getattr(self, field)
            if val is not None:
                d[field] = val
        if self.component_graph is not None:
            d["component_graph"] = self.component_graph
        if self.material_overrides:
            d["material_overrides"] = self.material_overrides
        if self.properties:
            d["properties"] = self.properties
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PendingWindowType":
        """Deserialize from a dict."""
        return cls(
            overall_width=cls._require(d, "overall_width"),
            overall_height=cls._require(d, "overall_height"),
            window_type=d.get("window_type", "NOTDEFINED"),
            name=d.get("name", ""),
            type_key=d.get("type_key"),
            lining_depth=d.get("lining_depth"),
            lining_thickness=d.get("lining_thickness"),
            transom_thickness=d.get("transom_thickness"),
            mullion_thickness=d.get("mullion_thickness"),
            first_transom_offset=d.get("first_transom_offset"),
            second_transom_offset=d.get("second_transom_offset"),
            first_mullion_offset=d.get("first_mullion_offset"),
            second_mullion_offset=d.get("second_mullion_offset"),
            lining_offset=d.get("lining_offset"),
            lining_to_panel_offset_x=d.get("lining_to_panel_offset_x"),
            lining_to_panel_offset_y=d.get("lining_to_panel_offset_y"),
            panel_depth=d.get("panel_depth"),
            panel_width=d.get("panel_width"),
            panel_height=d.get("panel_height"),
            panel_operation=d.get("panel_operation"),
            component_graph=d.get("component_graph"),
            material_overrides=d.get("material_overrides"),
            properties=d.get("properties") or {},
        )
