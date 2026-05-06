"""
ifckit.builders.component_graph
================================

Evaluator for JSON component-graph presets for windows and doors.

A component graph describes geometry as a DAG of nodes.
Each node has an ``op`` (operation) and produces either a 2D profile
or a 3D solid. Nodes with ``output: true`` are added to the IFC
shape representation.

Supported ops (v1):
    rect        2D rectangle from two corner points
    difference  Boolean 2D difference (a minus b)
    extrude     Extrude a 2D profile to a 3D solid

Expression syntax (v1):
    "$name"           parameter substitution
    "$a OP $b"        binary op: +, -, *, /
    "$a OP literal"   e.g. "$panel_depth / 2"

See ifckit/window_types/*.json for examples.
"""

from __future__ import annotations

import importlib.resources
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import ifcopenshell

from ifckit.builders._geom import (
    axis2placement3d,
    extrude_profile,
    profile_from_points,
)
from ifckit.geometry import Path, Plane, Vec

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class EvaluatedComponent:
    """A single output component produced by the graph evaluator."""

    role: str
    solid: ifcopenshell.entity_instance
    node_id: str
    material: dict  # Optional material definition (color, transparency, name)


# ---------------------------------------------------------------------------
# Expression evaluator
# ---------------------------------------------------------------------------


def _eval_expr(expr: Any, params: Dict[str, float]) -> float:
    """Evaluate a parameter expression to a float.

    Respects operator precedence: * and / before + and -.
    """
    if isinstance(expr, (int, float)):
        return float(expr)

    if not isinstance(expr, str):
        raise ValueError(f"_eval_expr: expected str or number, got {type(expr).__name__!r}")

    expr = expr.strip()

    # Simple substitution: "$name"
    if re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", expr):
        name = expr[1:]
        if name not in params:
            raise KeyError(f"Unknown parameter: {name!r}")
        return float(params[name])

    def _resolve_token(tok: str) -> float:
        """Resolve a single token (variable or literal)."""
        tok = str(tok).strip()
        if tok.startswith("$"):
            name = tok[1:]
            if name not in params:
                raise KeyError(f"Unknown parameter: {name!r}")
            return float(params[name])
        try:
            return float(tok)
        except ValueError:
            raise ValueError(f"_eval_expr: cannot parse token {tok!r}")

    # Tokenize: split by operators but keep them
    tokens = re.split(r"\s*([\+\-\*\/])\s*", expr)

    if len(tokens) == 1:
        return _resolve_token(tokens[0])

    # First pass: resolve all * and / (higher precedence)
    i = 1
    while i < len(tokens):
        if i >= len(tokens) - 1:
            break
        op = tokens[i].strip()
        if op in ("*", "/"):
            lhs = _resolve_token(tokens[i - 1])
            rhs = _resolve_token(tokens[i + 1])
            if op == "*":
                result = lhs * rhs
            else:  # op == "/"
                if abs(rhs) < 1e-15:
                    raise ValueError(f"_eval_expr: division by zero in {expr!r}")
                result = lhs / rhs
            # Replace [lhs, op, rhs] with result
            tokens[i - 1 : i + 2] = [result]
            # Stay at same i to check next operator
        else:
            i += 2

    # Second pass: resolve all + and - (lower precedence)
    result = _resolve_token(tokens[0])
    i = 1
    while i < len(tokens) - 1:
        op = tokens[i].strip()
        rhs = _resolve_token(tokens[i + 1])
        if op == "+":
            result += rhs
        elif op == "-":
            result -= rhs
        else:
            raise ValueError(f"_eval_expr: unexpected operator {op!r}")
        i += 2

    return result


def _contains_literal(expr: Any) -> bool:
    """Check if expression contains any literal numbers (not just variables).

    Returns True only if the expression has at least one numeric literal.
    Variables like "$name" or expressions with only variables return False.

    Args:
        expr: Expression (str, int, float).

    Returns:
        True if contains at least one literal number; False if all tokens are variables.
    """
    # Numeric literals always have literals
    if isinstance(expr, (int, float)):
        return True

    if not isinstance(expr, str):
        return False

    expr = expr.strip()
    # Pure variable: "$name"
    if re.fullmatch(r"\$[A-Za-z_][A-Za-z0-9_]*", expr):
        return False

    # Tokenize and check if any token is a literal (not starting with $)
    tokens = re.split(r"\s*([\+\-\*\/])\s*", expr)
    for tok in tokens:
        tok = tok.strip()
        if not tok:
            continue
        # Skip operators
        if tok in ("+", "-", "*", "/"):
            continue
        # If token doesn't start with $, it's a literal
        if not tok.startswith("$"):
            return True

    # All non-operator tokens are variables
    return False


def _eval_point(
    raw: Any,
    params: Dict[str, float],
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> Tuple[float, float]:
    """Evaluate a 2-element [x, y] array and apply scale factors.

    Scale factors map reference-space coordinates to actual dimensions.
    ``scale_x = actual_w / ref_w``, ``scale_y = actual_h / ref_h``.

    Literals in the array (e.g., 10, 20) are scaled.
    Variables (e.g., "$w", "$h") are NOT scaled (they are occurrence values).
    Expressions with both (e.g., "$w + 10") scale only the literals.
    """
    if not (isinstance(raw, (list, tuple)) and len(raw) == 2):
        raise ValueError(f"Expected [x, y] point, got {raw!r}")

    # Evaluate X: if it has literals, apply scale_x; else don't scale
    x_val = _eval_expr(raw[0], params)
    x = x_val * scale_x if _contains_literal(raw[0]) else x_val

    # Evaluate Y: if it has literals, apply scale_y; else don't scale
    y_val = _eval_expr(raw[1], params)
    y = y_val * scale_y if _contains_literal(raw[1]) else y_val

    return (x, y)


# ---------------------------------------------------------------------------
# Graph loader
# ---------------------------------------------------------------------------


def _load_preset(name: str) -> Dict[str, Any]:
    """Load a JSON preset by name from ifckit.window_types."""
    try:
        pkg = importlib.resources.files("ifckit.window_types")
        data = (pkg / f"{name}.json").read_text(encoding="utf-8")
    except (FileNotFoundError, TypeError) as exc:
        raise FileNotFoundError(
            f"Component graph preset not found: {name!r}. Expected ifckit/window_types/{name}.json"
        ) from exc
    parsed = json.loads(data)
    version = parsed.get("version")
    if version != 1:
        raise ValueError(
            f"Unsupported component graph version {version!r} in preset {name!r}. "
            f"Only version 1 is supported."
        )
    return parsed


def _resolve_parameters(
    preset: Dict[str, Any],
    overrides: Dict[str, float],
) -> Dict[str, float]:
    """Merge preset defaults with caller overrides."""
    defaults = preset.get("parameters", {})
    result: Dict[str, float] = {}
    for name, default in defaults.items():
        if name in overrides:
            result[name] = float(overrides[name])
        elif default is None:
            raise ValueError(f"Required parameter {name!r} not provided for component graph.")
        else:
            result[name] = float(default)
    for name, val in overrides.items():
        if name not in result:
            result[name] = float(val)
    return result


# ---------------------------------------------------------------------------
# Node evaluators
# ---------------------------------------------------------------------------


def _eval_node_rect(
    node: Dict[str, Any],
    params: Dict[str, float],
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> Path:
    """Evaluate a 'rect' node → closed CCW Path in the XY plane.

    Optional ``holes`` key: list of inline node dicts (each with ``op`` and
    geometry fields).  Each hole is evaluated and added via ``Path.with_hole()``,
    producing a ``Path`` that ``profile_from_points`` will convert to
    ``IfcArbitraryProfileDefWithVoids``.

    Holes may themselves carry nested holes (though IFC only supports one level
    of void depth — inner holes of holes are silently ignored by the IFC spec).
    """
    p0 = _eval_point(node["p0"], params, scale_x, scale_y)
    p1 = _eval_point(node["p1"], params, scale_x, scale_y)
    x0, y0 = p0
    x1, y1 = p1
    xy_plane = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    pts = [
        Vec(x0, y0, 0),
        Vec(x1, y0, 0),
        Vec(x1, y1, 0),
        Vec(x0, y1, 0),
    ]
    path = Path.from_pts(pts, plane=xy_plane, closed=True)

    for hole_node in node.get("holes", []):
        hole_op = hole_node.get("op")
        if hole_op == "rect":
            hole_path = _eval_node_rect(hole_node, params, scale_x, scale_y)
        elif hole_op == "offset":
            dist_raw = hole_node.get("dist")
            if dist_raw is None:
                raise ValueError(
                    f"Hole with op='offset' in rect node {node.get('id')!r} missing 'dist'."
                )
            # dist is an occurrence value (e.g., "$lining_thickness"); don't scale it.
            # If it's a literal or expression with literals, it stays as-is because
            # it's meant to be in reference-frame units (mm). Variables like "$lining_thickness"
            # are already in mm, so no scaling.
            dist = _eval_expr(dist_raw, params)
            hole_path = path.offset(dist)
        else:
            raise ValueError(
                f"Unsupported hole op {hole_op!r} in rect node {node.get('id')!r}. "
                "Supported ops: 'rect', 'offset'."
            )
        path = path.with_hole(hole_path)

    return path


def _eval_node_difference(
    node: Dict[str, Any],
    cache: Dict[str, Any],
    params: Dict[str, float],
) -> Path:
    """Evaluate a 'difference' node → Path with one hole (outer minus inner).

    Both operands must be closed Path objects from 'rect' or prior 'difference'
    nodes. The result is a Path whose outer curve is ``a`` and whose holes
    list contains ``b``. ``profile_from_points`` will convert this to
    ``IfcArbitraryProfileDefWithVoids`` automatically.
    """
    a_id = node["a"]
    b_id = node["b"]
    a_val = cache.get(a_id)
    b_val = cache.get(b_id)
    if a_val is None:
        raise ValueError(f"'difference' node references unknown node id: {a_id!r}")
    if b_val is None:
        raise ValueError(f"'difference' node references unknown node id: {b_id!r}")
    if not isinstance(a_val, Path):
        raise ValueError(
            f"'difference' op: operand 'a' ({a_id!r}) must be a Path, got {type(a_val).__name__}"
        )
    if not isinstance(b_val, Path):
        raise ValueError(
            f"'difference' op: operand 'b' ({b_id!r}) must be a Path, got {type(b_val).__name__}"
        )
    return a_val.with_hole(b_val)


# ---------------------------------------------------------------------------
# Internal node list evaluator
# ---------------------------------------------------------------------------


def _eval_node_list(
    nodes: List[Dict[str, Any]],
    preset_name: str,
    ifc_file: ifcopenshell.file,
    context: ifcopenshell.entity_instance,
    resolved: Dict[str, float],
    scale_x: float,
    scale_y: float,
) -> List["EvaluatedComponent"]:
    """
    Evaluate a list of nodes (fill or opening) and return output components.

    Args:
        nodes:        List of node dicts from the JSON preset.
        preset_name:  Name used in error messages.
        ifc_file:     Open ifcopenshell file.
        context:      Body sub-context (used for extrude nodes).
        resolved:     Fully resolved parameter dict (ref values, not scaled).
        scale_x:      Scale factor for X coordinates (actual_w / ref_w).
        scale_y:      Scale factor for Y coordinates (actual_h / ref_h).

    Returns:
        List of EvaluatedComponent for nodes with ``output: true``.
    """
    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)):
        duplicates = [x for x in ids if ids.count(x) > 1]
        raise ValueError(f"Duplicate node ids in preset {preset_name!r}: {duplicates}")

    cache: Dict[str, Any] = {}
    outputs: List[EvaluatedComponent] = []

    for node in nodes:
        node_id = node.get("id")
        if not node_id:
            raise ValueError(f"Node missing 'id' field in preset {preset_name!r}")
        op = node.get("op")
        if not op:
            raise ValueError(f"Node {node_id!r} missing 'op' field")

        if op == "rect":
            result = _eval_node_rect(node, resolved, scale_x, scale_y)
            cache[node_id] = result

        elif op == "extrude":
            profile_id = node.get("profile")
            if profile_id is None:
                raise ValueError(f"'extrude' node {node_id!r} missing 'profile'")
            profile_val = cache.get(profile_id)
            if profile_val is None:
                raise ValueError(
                    f"'extrude' node {node_id!r} references unknown profile: {profile_id!r}"
                )
            # depth and z_offset are in the same units as the project (from params)
            # Extrude direction is always -Z (backward through the wall)
            depth = _eval_expr(node.get("depth", 0.1), resolved)
            z_offset_raw = node.get("z_offset", 0)
            z_offset_param = _eval_expr(z_offset_raw, resolved) if z_offset_raw != 0 else 0.0
            # Apply -Z rule: negate z_offset so geometry goes backward
            z_offset = -z_offset_param

            placement = axis2placement3d(ifc_file, Vec(0, 0, z_offset), Vec(0, 0, 1), Vec(1, 0, 0))

            # profile_val is a Path (from rect or difference)
            ifc_profile = profile_from_points(ifc_file, profile_val)

            solid = extrude_profile(
                ifc_file,
                ifc_profile,
                depth,
                position=placement,
                extrude_direction=(0.0, 0.0, -1.0),
            )
            cache[node_id] = solid

            if node.get("output", False):
                role = node.get("role", node_id)
                material = node.get("material")  # Optional material definition
                outputs.append(
                    EvaluatedComponent(
                        role=role,
                        solid=solid,
                        node_id=node_id,
                        material=material,
                    )
                )

        else:
            raise ValueError(
                f"Unknown op {op!r} in node {node_id!r} of preset {preset_name!r}. "
                f"Supported ops: rect, extrude."
            )

    return outputs


# ---------------------------------------------------------------------------
# Main evaluators
# ---------------------------------------------------------------------------


def evaluate_component_graph(
    preset_name: str,
    ifc_file: ifcopenshell.file,
    context: ifcopenshell.entity_instance,
    params: Dict[str, float],
) -> List[EvaluatedComponent]:
    """
    Evaluate a component graph preset and produce IFC fill geometry.

    Args:
        preset_name: Name of the preset (e.g., "fixed_casement").
        ifc_file:    Open ifcopenshell file.
        context:     Body sub-context.
        params:      Override dict. Must include ``w`` and ``h`` (actual
                     dimensions). Other keys override preset defaults.

    Returns:
        List of EvaluatedComponent for nodes with ``output: true``.
    """
    preset = _load_preset(preset_name)
    resolved = _resolve_parameters(preset, params)
    ref_w = float(preset["parameters"]["w"])
    ref_h = float(preset["parameters"]["h"])
    actual_w = float(params.get("w", ref_w))
    actual_h = float(params.get("h", ref_h))
    scale_x = actual_w / ref_w
    scale_y = actual_h / ref_h

    return _eval_node_list(
        preset.get("nodes", []),
        preset_name,
        ifc_file,
        context,
        resolved,
        scale_x,
        scale_y,
    )


def evaluate_opening_nodes(
    preset_name: str,
    ifc_file: ifcopenshell.file,
    context: ifcopenshell.entity_instance,
    params: Dict[str, float],
) -> List[EvaluatedComponent]:
    """
    Evaluate the ``opening_nodes`` section of a preset and produce IFC void geometry.

    The caller must include ``wall_thickness`` in *params* — this is used as
    the ``$wall_thickness`` parameter in depth expressions.

    Nodes with ``output: false`` are silently skipped (they may still be used
    as profiles by other nodes). This allows future presets to define an opening
    shape without emitting any void solid (e.g., template-only presets).

    Args:
        preset_name: Name of the preset (e.g., "fixed_casement").
        ifc_file:    Open ifcopenshell file.
        context:     Body sub-context.
        params:      Override dict. Must include ``w``, ``h``, and
                     ``wall_thickness``.

    Returns:
        List of EvaluatedComponent for opening_nodes with ``output: true``.

    Raises:
        ValueError: If preset has no ``opening_nodes`` section.
        ValueError: If required parameters are missing.
    """
    preset = _load_preset(preset_name)
    opening_nodes = preset.get("opening_nodes")
    if opening_nodes is None:
        raise ValueError(
            f"Preset {preset_name!r} has no 'opening_nodes' section. "
            "Cannot evaluate opening geometry."
        )

    resolved = _resolve_parameters(preset, params)
    ref_w = float(preset["parameters"]["w"])
    ref_h = float(preset["parameters"]["h"])
    actual_w = float(params.get("w", ref_w))
    actual_h = float(params.get("h", ref_h))
    scale_x = actual_w / ref_w
    scale_y = actual_h / ref_h

    return _eval_node_list(
        opening_nodes,
        preset_name,
        ifc_file,
        context,
        resolved,
        scale_x,
        scale_y,
    )
