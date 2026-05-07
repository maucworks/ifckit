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
    polygon    2D arbitrary polygon from explicit point list
    difference          Boolean 2D difference (a minus b)
    extrude             Extrude a 2D profile to a solid
    boolean_cut         3D solid DIFFERENCE (base minus tool) → IfcBooleanResult
    boolean_union       3D solid UNION (base + tool) → IfcBooleanResult
    boolean_intersection 3D solid INTERSECTION → IfcBooleanResult
    extrude     Extrude a 2D profile to a 3D solid

Expression syntax (v1):
    "$name"           parameter substitution
    "$a OP $b"        binary op: +, -, *, /
    "$a OP literal"   e.g. "$panel_depth / 2"

See ifckit.components.json/*.json for examples.
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

    Supports +, -, *, / with correct precedence, parentheses, and $variables.
    Uses a recursive descent parser: no regex token-list mutation.

    Grammar:
        expr   = term   (('+' | '-') term)*
        term   = factor (('*' | '/') factor)*
        factor = '(' expr ')' | number | '$' name | '-' factor
    """
    if isinstance(expr, (int, float)):
        return float(expr)
    if not isinstance(expr, str):
        raise ValueError(f"_eval_expr: expected str or number, got {type(expr).__name__!r}")

    src = expr.strip()
    pos = [0]  # mutable int so nested functions can advance it

    def peek() -> str:
        while pos[0] < len(src) and src[pos[0]] == " ":
            pos[0] += 1
        return src[pos[0]] if pos[0] < len(src) else ""

    def consume(expected: str | None = None) -> str:
        ch = peek()
        if expected is not None and ch != expected:
            raise ValueError(f"_eval_expr: expected {expected!r} got {ch!r} in {expr!r}")
        pos[0] += 1
        return ch

    def parse_number() -> float:
        start = pos[0]
        while pos[0] < len(src) and src[pos[0]] in "0123456789.":
            pos[0] += 1
        if pos[0] == start:
            raise ValueError(f"_eval_expr: expected number at pos {start} in {expr!r}")
        return float(src[start : pos[0]])

    def parse_variable() -> float:
        pos[0] += 1  # skip '$'
        start = pos[0]
        while pos[0] < len(src) and (src[pos[0]].isalnum() or src[pos[0]] == "_"):
            pos[0] += 1
        name = src[start : pos[0]]
        if name not in params:
            raise KeyError(f"Unknown parameter: {name!r}")
        return float(params[name])

    def parse_factor() -> float:
        ch = peek()
        if ch == "(":
            consume("(")
            val = parse_expr()
            consume(")")
            return val
        if ch == "-":
            consume("-")
            return -parse_factor()
        if ch == "$":
            return parse_variable()
        return parse_number()

    def parse_term() -> float:
        val = parse_factor()
        while peek() in ("*", "/"):
            op = consume()
            rhs = parse_factor()
            if op == "*":
                val *= rhs
            else:
                if abs(rhs) < 1e-15:
                    raise ValueError(f"_eval_expr: division by zero in {expr!r}")
                val /= rhs
        return val

    def parse_expr() -> float:
        val = parse_term()
        while peek() in ("+", "-"):
            op = consume()
            rhs = parse_term()
            if op == "+":
                val += rhs
            else:
                val -= rhs
        return val

    result = parse_expr()
    if pos[0] != len(src) and src[pos[0] :].strip():
        raise ValueError(f"_eval_expr: unexpected trailing input {src[pos[0] :]!r} in {expr!r}")
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
    """Load a JSON preset by name from ifckit.components.json."""
    try:
        pkg = importlib.resources.files("ifckit.components.json")
        data = (pkg / f"{name}.json").read_text(encoding="utf-8")
    except (FileNotFoundError, TypeError) as exc:
        raise FileNotFoundError(
            f"Component graph preset not found: {name!r}. "
            f"Expected ifckit.components.json/{name}.json"
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
            dist = _eval_expr(dist_raw, params)
            # Only inline offset (offset parent) supported in rect holes.
            # For named source offsets, use a standalone offset node.
            if hole_op == "offset" and hole_node.get("source"):
                raise ValueError(
                    "Source reference in rect hole not supported. "
                    "Use standalone offset node instead."
                )
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


def _eval_node_polygon(
    node: Dict[str, Any],
    params: Dict[str, float],
    scale_x: float = 1.0,
    scale_y: float = 1.0,
) -> "Path":
    """Evaluate a 'polygon' node → closed Path from explicit point list.

    Provides more flexibility than 'rect' for creating non-rectangular profiles,
    L-shapes, U-shapes, or any arbitrary polygon outline.
    """
    points_raw = node.get("points")
    if not points_raw:
        raise ValueError(f"'polygon' node {node.get('id')!r} missing 'points'.")

    if len(points_raw) < 3:
        raise ValueError(
            f"'polygon' node {node.get('id')!r} requires at least 3 points, got {len(points_raw)}"
        )

    pts = []
    for pt_raw in points_raw:
        p = _eval_point(pt_raw, params, scale_x, scale_y)
        pts.append(Vec(p[0], p[1], 0.0))

    xy_plane = Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0))
    path = Path.from_pts(pts, plane=xy_plane, closed=True)

    for hole_node in node.get("holes", []):
        hole_op = hole_node.get("op")
        if hole_op == "rect":
            hole_path = _eval_node_rect(hole_node, params, scale_x, scale_y)
        elif hole_op == "polygon":
            hole_path = _eval_node_polygon(hole_node, params, scale_x, scale_y)
        elif hole_op == "offset":
            dist_raw = hole_node.get("dist")
            if dist_raw is None:
                raise ValueError(
                    f"Hole with op='offset' in polygon node {node.get('id')!r} missing 'dist'."
                )
            dist = _eval_expr(dist_raw, params)
            if hole_node.get("source"):
                raise ValueError(
                    "Source reference in polygon hole not supported. "
                    "Use standalone offset node instead."
                )
            hole_path = path.offset(dist)
        else:
            raise ValueError(
                f"Unsupported hole op {hole_op!r} in polygon node {node.get('id')!r}. "
                "Supported ops: 'rect', 'polygon', 'offset'."
            )
        path = path.with_hole(hole_path)

    return path


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
            # Also cache any named holes so extrude nodes can reference them directly.
            for hole_node in node.get("holes", []):
                hole_id = hole_node.get("id")
                if hole_id and hole_id not in cache:
                    hole_result = _eval_node_rect(hole_node, resolved, scale_x, scale_y)
                    cache[hole_id] = hole_result

        elif op == "polygon":
            result = _eval_node_polygon(node, resolved, scale_x, scale_y)
            cache[node_id] = result
            # Also cache any named holes.
            for hole_node in node.get("holes", []):
                hole_id = hole_node.get("id")
                if hole_id and hole_id not in cache:
                    hole_result = _eval_node_rect(hole_node, resolved, scale_x, scale_y)
                    cache[hole_id] = hole_result

        elif op == "difference":
            result = _eval_node_difference(node, cache, resolved)
            cache[node_id] = result

        elif op == "offset":
            # Standalone offset node: retrieve source path and apply offset
            source_id = node.get("source")
            if source_id is None:
                raise ValueError(f"'offset' node {node_id!r} missing 'source'")
            if source_id and isinstance(source_id, str) and source_id.startswith("$"):
                source_id = source_id[1:]
            source_path = cache.get(source_id)
            if source_path is None:
                raise ValueError(
                    f"'offset' node {node_id!r} references unknown source: {source_id!r}"
                )
            dist_raw = node.get("dist")
            if dist_raw is None:
                raise ValueError(f"'offset' node {node_id!r} missing 'dist'")
            dist = _eval_expr(dist_raw, resolved)
            result = source_path.offset(dist)
            cache[node_id] = result

        elif op in ("boolean_cut", "boolean_union", "boolean_intersection"):
            base_id = node.get("base")
            tool_id = node.get("tool")
            if base_id is None:
                raise ValueError(f"{op!r} node {node_id!r} missing 'base'")
            if tool_id is None:
                raise ValueError(f"{op!r} node {node_id!r} missing 'tool'")
            base_solid = cache.get(base_id)
            tool_solid = cache.get(tool_id)
            if base_solid is None:
                raise ValueError(f"{op!r} node {node_id!r} references unknown node: {base_id!r}")
            if tool_solid is None:
                raise ValueError(f"{op!r} node {node_id!r} references unknown node: {tool_id!r}")
            ifc_operator = {
                "boolean_cut": "DIFFERENCE",
                "boolean_union": "UNION",
                "boolean_intersection": "INTERSECTION",
            }[op]
            result = ifc_file.create_entity(
                "IfcBooleanResult",
                Operator=ifc_operator,
                FirstOperand=base_solid,
                SecondOperand=tool_solid,
            )
            cache[node_id] = result
            if node.get("output", False):
                role = node.get("role", node_id)
                material = node.get("material")
                outputs.append(
                    EvaluatedComponent(
                        role=role,
                        solid=result,
                        node_id=node_id,
                        material=material,
                    )
                )

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
            # CONVENTION (DO NOT CHANGE):
            #   - Extrusion direction is ALWAYS -Z (backward through the wall).
            #   - z_offset in JSON is expressed as a positive value meaning
            #     "distance into the wall from the outer face". We negate it here
            #     so the placement origin moves in -Z before extruding further in -Z.
            # Both choices must stay consistent — changing one without the other
            # will silently mis-place all component geometry.
            depth = _eval_expr(node.get("depth", 0.1), resolved)
            z_offset_raw = node.get("z_offset", 0)
            z_offset_param = _eval_expr(z_offset_raw, resolved) if z_offset_raw != 0 else 0.0
            z_offset = -z_offset_param  # negate: positive JSON value → move in -Z

            placement = axis2placement3d(ifc_file, Vec(0, 0, z_offset), Vec(0, 0, 1), Vec(1, 0, 0))

            # profile_val is a Path (from rect or difference)
            ifc_profile = profile_from_points(ifc_file, profile_val)

            solid = extrude_profile(
                ifc_file,
                ifc_profile,
                depth,
                position=placement,
                extrude_direction=(0.0, 0.0, -1.0),  # ALWAYS -Z — see convention above
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
                "Supported ops: rect, difference, extrude, "
                "boolean_cut, boolean_union, boolean_intersection."
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
    plane=None,
) -> List[EvaluatedComponent]:
    """
    Evaluate a component graph preset and produce IFC fill geometry.

    Args:
        preset_name: Name of the preset (e.g., "fixed_casement").
        ifc_file:    Open ifcopenshell file.
        context:     Body sub-context.
        params:      Override dict. Must include ``w`` and ``h`` (actual
                     dimensions). Other keys override preset defaults.
        plane:       Reference plane for Python components.
                    If None, falls back to JSON-only evaluation.

    Returns:
        List of EvaluatedComponent for nodes with ``output: true``.
    """
    # 1. Check JSON preset first (JSON wins on name collision)
    try:
        preset = _load_preset(preset_name)
    except FileNotFoundError:
        # 2. Fall back to Python component if JSON not found
        from ifckit.components import COMPONENT_REGISTRY, get_component

        if preset_name in COMPONENT_REGISTRY and plane is not None:
            component_cls = get_component(preset_name)
            component = component_cls()
            return component.build(
                ifc_file,
                plane,
                params.get("w", 1000),
                params.get("h", 1000),
                params,
            )
        raise  # Re-raise original error

    # JSON preset exists - use it (Python can override by deleting JSON file)
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
    plane=None,
) -> List[EvaluatedComponent]:
    """Evaluate the opening_nodes section — JSON first, then Python fallback."""
    try:
        preset = _load_preset(preset_name)
    except FileNotFoundError:
        from ifckit.components import COMPONENT_REGISTRY, get_component

        if preset_name in COMPONENT_REGISTRY and plane is not None:
            comp_cls = get_component(preset_name)
            comp = comp_cls()
            return comp.build(ifc_file, plane, params.get("w", 1000), params.get("h", 1000), params)
        raise

    opening_nodes = preset.get("opening_nodes")
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
